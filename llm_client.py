"""
Módulo de conexión con Ollama (API OpenAI-compatible) para embeddings y generación de texto.
Incluye manejo de errores y reintentos.
"""
import requests
import json
import re
import time
import gc
import hashlib
import threading
from typing import List, Dict, Any, Optional
from functools import lru_cache
import numpy as np

from config import config


class TokenTracker:
    """Acumulador thread-safe de tokens consumidos por el LLM."""

    def __init__(self):
        self._lock = threading.Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def add(self, usage: dict):
        if not usage:
            return
        with self._lock:
            self.prompt_tokens += usage.get("prompt_tokens", 0)
            self.completion_tokens += usage.get("completion_tokens", 0)
            self.total_tokens += usage.get("total_tokens", 0)

    def reset(self):
        with self._lock:
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.total_tokens = 0

    def get(self) -> dict:
        with self._lock:
            return {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            }


_token_tracker = TokenTracker()

# ── Contexto de sesion per-thread (para cola de tareas) ──
_current_session = threading.local()


def set_current_session(session_id: str, session_manager=None):
    """Llamado desde el worker de la cola antes de ejecutar una tarea."""
    _current_session.session_id = session_id
    _current_session.session_manager = session_manager


def clear_current_session():
    """Llamado al terminar la tarea."""
    _current_session.session_id = None
    _current_session.session_manager = None


def _route_token_usage(usage: dict):
    """Rutea tokens a la sesion activa, o al tracker global como fallback."""
    if not usage:
        return
    sid = getattr(_current_session, 'session_id', None)
    mgr = getattr(_current_session, 'session_manager', None)
    if sid and mgr:
        mgr.add_tokens(sid, usage)
    else:
        _token_tracker.add(usage)


class LMStudioClient:
    """Cliente para comunicación con Ollama (OpenAI-compatible)."""
    
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or config.base_url
        self.model = model or config.model
        self._session = None
    
    @property
    def session(self) -> requests.Session:
        """Sesión HTTP reutilizable."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({"Content-Type": "application/json"})
        return self._session
    
    def check_connection(self) -> bool:
        """Verifica conexión con Ollama/OpenAI-compatible."""
        try:
            r = self.session.get(f"{self.base_url}/models", timeout=10)
            return r.status_code == 200
        except Exception:
            return False
    
    def get_models(self) -> Dict:
        """Obtiene modelos disponibles."""
        r = self.session.get(f"{self.base_url}/models", timeout=10)
        r.raise_for_status()
        return r.json()
    
    def chat(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
        response_format: Dict[str, Any] = None
    ) -> str:
        """Genera respuesta de chat."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or config.temperature,
            "max_tokens": max_tokens or config.max_tokens
        }
        if response_format:
            payload["response_format"] = response_format
        
        r = self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=timeout or config.timeout
        )
        # Algunos modelos OpenAI-compatible no soportan response_format.
        # Si falla 400, reintenta una vez sin ese campo.
        if r.status_code == 400 and "response_format" in payload:
            payload.pop("response_format", None)
            r = self.session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=timeout or config.timeout
            )
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage")
        if usage:
            _route_token_usage(usage)
        return data["choices"][0]["message"]["content"]

    def chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 3,
        **kwargs
    ) -> str:
        """Chat con reintentos en caso de fallo."""
        last_error = None
        for attempt in range(max_retries):
            try:
                return self.chat(messages, **kwargs)
            except Exception as e:
                last_error = e
                wait_time = 2 ** attempt
                print(f"⚠️ Intento {attempt + 1} fallido, esperando {wait_time}s...")
                time.sleep(wait_time)
                gc.collect()  # Liberar memoria
        
        raise last_error
    
    def close(self):
        """Cierra la sesión."""
        if self._session:
            self._session.close()
            self._session = None


class EmbeddingClient:
    """Cliente para generación de embeddings con Ollama/OpenAI-compatible."""
    
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or config.base_url
        self.model = model or config.embedding_model
        self._session = None
        self._cache = {}
        self._chat_embedding_dims = 128
        self._vector_dim = 768
        self._max_embed_words = 180
        self._max_embed_chars = 3500

    def _ollama_base_url(self) -> str:
        """Devuelve base URL sin sufijo /v1 para endpoints nativos de Ollama."""
        return self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url

    def _prepare_text_for_embedding(self, text: str) -> str:
        """
        Normaliza y recorta texto para evitar errores de contexto en modelos embedding.
        """
        t = re.sub(r"\s+", " ", str(text or " ").strip())
        if not t:
            return " "
        words = t.split(" ")
        if len(words) > self._max_embed_words:
            t = " ".join(words[: self._max_embed_words])
        if len(t) > self._max_embed_chars:
            t = t[: self._max_embed_chars]
        return t or " "
    
    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
        return self._session
    
    def embed(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """
        Genera embeddings para una lista de textos.
        Procesa en lotes para evitar problemas de memoria.
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Verificar cache
            batch_embeddings = []
            texts_to_embed = []
            text_indices = []
            
            for j, text in enumerate(batch):
                text_hash = hash(text)
                if text_hash in self._cache:
                    batch_embeddings.append((j, self._cache[text_hash]))
                else:
                    texts_to_embed.append(text)
                    text_indices.append(j)
            
            # Generar embeddings para textos no cacheados
            if texts_to_embed:
                new_embeddings = self._embed_batch(texts_to_embed)
                for text, emb in zip(texts_to_embed, new_embeddings):
                    self._cache[hash(text)] = emb
                
                for idx, emb in zip(text_indices, new_embeddings):
                    batch_embeddings.append((idx, emb))
            
            # Ordenar por índice original
            batch_embeddings.sort(key=lambda x: x[0])
            all_embeddings.extend([emb for _, emb in batch_embeddings])
            
            # Liberar memoria periódicamente
            if i % 50 == 0 and i > 0:
                gc.collect()
        
        return all_embeddings
    
    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings para un lote."""
        if not texts:
            return []

        # Sanitizar vacíos para no gatillar 400 en algunos endpoints.
        sanitized = [self._prepare_text_for_embedding(t) for t in texts]
        native_url = f"{self._ollama_base_url()}/api/embed"

        # 1) Intentar endpoint nativo de Ollama (/api/embed) en lote.
        try:
            r_native = self.session.post(
                native_url,
                json={"model": self.model, "input": sanitized},
                timeout=60
            )
            if r_native.status_code < 400:
                data = r_native.json()
                embeddings = data.get("embeddings")
                if isinstance(embeddings, list) and embeddings:
                    self._vector_dim = len(embeddings[0])
                    return embeddings
        except Exception:
            pass

        # 2) Compatibilidad OpenAI (/v1/embeddings).
        try:
            r_v1 = self.session.post(
                f"{self.base_url}/embeddings",
                json={"model": self.model, "input": sanitized},
                timeout=60
            )
            if r_v1.status_code < 400:
                data = r_v1.json()
                rows = data.get("data")
                if isinstance(rows, list) and rows:
                    embeddings = [item["embedding"] for item in rows]
                    self._vector_dim = len(embeddings[0])
                    return embeddings
        except Exception:
            pass

        # 3) Reintento nativo por texto individual.
        embeddings: List[List[float]] = []
        any_success = False
        for t in sanitized:
            try:
                r_one = self.session.post(
                    native_url,
                    json={"model": self.model, "input": t},
                    timeout=60
                )
                if r_one.status_code == 400:
                    # Reintento ultra-corto para textos que aún exceden contexto.
                    t_short = self._prepare_text_for_embedding(t[:1200])
                    r_one = self.session.post(
                        native_url,
                        json={"model": self.model, "input": t_short},
                        timeout=60
                    )
                if r_one.status_code < 400:
                    data = r_one.json()
                    rows = data.get("embeddings")
                    if isinstance(rows, list) and rows:
                        vec = rows[0]
                        if isinstance(vec, list) and vec:
                            self._vector_dim = len(vec)
                            embeddings.append(vec)
                            any_success = True
                            continue
                embeddings.append(self._deterministic_embedding(t, self._vector_dim))
            except Exception:
                embeddings.append(self._deterministic_embedding(t, self._vector_dim))

        if any_success:
            return embeddings

        # 4) Último fallback: chat/completions (si está disponible),
        # y si falla, vector determinístico local.
        out: List[List[float]] = []
        for t in sanitized:
            try:
                vec = self._embed_single_via_chat(t)
                if vec:
                    self._vector_dim = len(vec)
                    out.append(vec)
                else:
                    out.append(self._deterministic_embedding(t, self._vector_dim))
            except Exception:
                out.append(self._deterministic_embedding(t, self._vector_dim))
        return out

    def _embed_single_via_chat(self, text: str) -> List[float]:
        """Genera un embedding numérico usando chat/completions con el modelo de embeddings."""
        prompt = (
            "Devuelve SOLO JSON valido en una linea con esta forma exacta: "
            '{"embedding":[f1,f2,...,f128]}. '
            "Deben ser 128 numeros decimales entre -1 y 1, sin texto adicional.\n\n"
            f"TEXTO:\n{text[:2000]}"
        )
        payload = {
            # Para chat fallback usar modelo de chat, no el embedding-only.
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 900,
        }
        r = self.session.post(f"{self.base_url}/chat/completions", json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage")
        if usage:
            _route_token_usage(usage)
        content = data["choices"][0]["message"]["content"]

        try:
            parsed = JSONExtractor.extract(content)
            vec = parsed.get("embedding", [])
        except Exception:
            vec = []

        if not isinstance(vec, list):
            vec = []
        cleaned = []
        for v in vec[: self._chat_embedding_dims]:
            try:
                cleaned.append(float(v))
            except Exception:
                cleaned.append(0.0)
        if len(cleaned) < self._chat_embedding_dims:
            cleaned.extend([0.0] * (self._chat_embedding_dims - len(cleaned)))
        return cleaned

    @staticmethod
    def _deterministic_embedding(text: str, dim: int) -> List[float]:
        """Embedding estable local para no interrumpir RAG cuando la API no responde."""
        dim = max(32, int(dim or 768))
        vals: List[float] = []
        for i in range(dim):
            digest = hashlib.sha256(f"{i}:{text}".encode("utf-8")).digest()
            n = int.from_bytes(digest[:4], "big", signed=False)
            vals.append((n / 2147483648.0) - 1.0)  # rango aprox [-1, 1)
        return vals
    
    def embed_single(self, text: str) -> List[float]:
        """Genera embedding para un solo texto."""
        return self.embed([text])[0]
    
    def clear_cache(self):
        """Limpia el cache de embeddings."""
        self._cache.clear()
        gc.collect()
    
    def close(self):
        if self._session:
            self._session.close()
            self._session = None


class JSONExtractor:
    """Extrae y repara JSON de respuestas del LLM."""

    @staticmethod
    def _normalize_json_text(text: str) -> str:
        """Normaliza artefactos comunes antes de parsear."""
        # Limpiar tags de razonamiento de modelos como gpt-oss
        # Soporta <think>...</think>, <reasoning>...</reasoning>, etc.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Limpiar tags parciales (sin cierre) — quedarse con lo que viene después
        text = re.sub(r"<think>.*", lambda m: m.group(0).split("</think>")[-1] if "</think>" in m.group(0) else "", text, flags=re.DOTALL | re.IGNORECASE)

        # Limpiar fences de markdown
        text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
        text = text.replace("```", "").strip()

        # Comillas Unicode frecuentes
        text = (
            text.replace("\u201c", '"')
            .replace("\u201d", '"')
            .replace("\u2018", "'")
            .replace("\u2019", "'")
        )

        # Remover caracteres de control no válidos
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
        return text

    @staticmethod
    def _extract_first_json_block(text: str):
        """
        Extrae el primer bloque JSON válido aunque venga con texto antes/después
        o múltiples objetos concatenados.
        """
        decoder = json.JSONDecoder()
        starts = [m.start() for m in re.finditer(r"[\{\[]", text)]
        for start in starts:
            try:
                obj, _end = decoder.raw_decode(text, idx=start)
                return obj
            except json.JSONDecodeError:
                continue
        raise ValueError("No se encontró bloque JSON válido en la respuesta")
    
    @staticmethod
    def extract(text: str) -> Dict:
        """Extrae JSON de texto, limpiando artefactos."""
        text = JSONExtractor._normalize_json_text(text)

        # 1) Intentar extraer primer bloque JSON válido directamente.
        try:
            return JSONExtractor._extract_first_json_block(text)
        except Exception:
            pass

        # 2) Reparaciones adicionales y reintento.
        repaired = re.sub(r",\s*([}\]])", r"\1", text)  # trailing commas
        repaired = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", repaired)  # backslashes sueltos

        # Si viene JSON con comillas simples y sin comillas dobles, intentar normalizar.
        if '"' not in repaired and "'" in repaired:
            repaired = repaired.replace("'", '"')

        return JSONExtractor._extract_first_json_block(repaired)
    
    @staticmethod
    def repair_with_llm(bad_json: str, client: LMStudioClient) -> Dict:
        """Repara JSON usando el LLM."""
        prompt = f"""Repara este JSON para que sea válido.
Devuelve SOLO el JSON reparado, sin markdown ni explicaciones.

JSON a reparar:
{bad_json}
"""
        response = client.chat_with_retry(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1500
        )
        return JSONExtractor.extract(response)


def get_json_response(
    prompt: str, 
    client: LMStudioClient = None,
    max_retries: int = 2,
    max_tokens: int = None,
    return_meta: bool = False
) -> Dict:
    """
    Obtiene respuesta JSON del LLM con manejo de errores.
    """
    if client is None:
        client = LMStudioClient()
    
    raw = client.chat_with_retry(
        [{"role": "user", "content": prompt}],
        temperature=config.temperature,
        max_tokens=max_tokens or config.max_tokens,
        response_format={"type": "json_object"}
    )
    
    try:
        parsed = JSONExtractor.extract(raw)
        if return_meta:
            return parsed, {"repaired": False}
        return parsed
    except Exception as e:
        if max_retries > 0:
            print(f"⚠️ Error extrayendo JSON, intentando reparar...")
            try:
                repaired = JSONExtractor.repair_with_llm(raw, client)
                if return_meta:
                    return repaired, {"repaired": True}
                return repaired
            except Exception:
                pass
        raise ValueError(f"No se pudo obtener JSON válido: {e}")


# Instancias globales (lazy loading)
_llm_client: Optional[LMStudioClient] = None
_embedding_client: Optional[EmbeddingClient] = None


def get_llm_client() -> LMStudioClient:
    """Obtiene el cliente LLM global."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LMStudioClient()
    return _llm_client


def get_embedding_client() -> EmbeddingClient:
    """Obtiene el cliente de embeddings global."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


def cleanup():
    """Limpia recursos globales."""
    global _llm_client, _embedding_client
    if _llm_client:
        _llm_client.close()
        _llm_client = None
    if _embedding_client:
        _embedding_client.close()
        _embedding_client = None
    gc.collect()


def get_token_usage() -> dict:
    """Retorna los tokens acumulados."""
    return _token_tracker.get()


def reset_token_usage():
    """Resetea el contador de tokens."""
    _token_tracker.reset()
