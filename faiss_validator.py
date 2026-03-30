"""
Validador FAISS: verifica que el JSON extraído tenga respaldo
en los documentos fuente usando similitud de vectores.

Flujo:
    1. Chunkea los TXT fuente en fragmentos de ~500 chars
    2. Genera embeddings con nomic-embed-text
    3. Indexa en FAISS (IndexFlatIP — cosine similarity)
    4. Para cada item del JSON, busca evidencia en el índice
    5. Marca items sin respaldo como "baja confianza"
"""
import re
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any


# ── Chunking ────────────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """Divide texto en chunks con overlap."""
    text = re.sub(r"---\s*P[ÁA]GINA.*?---", "\n", text, flags=re.I)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Cortar en salto de línea cercano al final
        if end < len(text):
            nl = text.rfind("\n", start + chunk_size // 2, end + 50)
            if nl > start:
                end = nl

        chunk = text[start:end].strip()
        if len(chunk) >= 50:  # Mínimo útil
            chunks.append(chunk)

        start = end - overlap
        if start >= len(text):
            break

    return chunks


def _load_and_chunk_files(txt_files: List[Path], chunk_size: int = 500) -> List[str]:
    """Lee TXTs y los chunkea."""
    all_chunks = []
    for path in txt_files:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            chunks = _chunk_text(raw, chunk_size=chunk_size)
            all_chunks.extend(chunks)
            print(f"  📄 {path.name}: {len(chunks)} chunks")
        except Exception as e:
            print(f"  ⚠️ Error leyendo {path.name}: {e}")
    return all_chunks


# ── FAISSValidator ──────────────────────────────────────────────────────────────

class FAISSValidator:
    """
    Valida un JSON extraído contra los documentos fuente usando FAISS.
    No usa LLM para validar — solo embeddings + cosine similarity.
    """

    def __init__(self, embedding_client, similarity_threshold: float = 0.35):
        self.embedder = embedding_client
        self.threshold = similarity_threshold
        self.index = None
        self.chunks: List[str] = []
        self._dim: int = 0

    def index_source_texts(self, txt_files: List[Path], chunk_size: int = 500):
        """
        Chunkea los TXTs fuente y los indexa en FAISS.
        """
        import faiss

        print("  🔤 Chunkeando documentos fuente...")
        self.chunks = _load_and_chunk_files(txt_files, chunk_size=chunk_size)

        if not self.chunks:
            print("  ⚠️ No se encontraron chunks — validación deshabilitada")
            return

        print(f"  📊 Total: {len(self.chunks)} chunks a indexar")
        print("  🧮 Generando embeddings...")

        # Generar embeddings en batch
        embeddings = self.embedder.embed_texts(self.chunks)

        if not embeddings or len(embeddings) != len(self.chunks):
            print("  ⚠️ Error generando embeddings — validación deshabilitada")
            self.chunks = []
            return

        # Normalizar para que inner product = cosine similarity
        matrix = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms

        self._dim = matrix.shape[1]

        # Crear índice FAISS (inner product = cosine sim con vectores normalizados)
        self.index = faiss.IndexFlatIP(self._dim)
        self.index.add(matrix)

        print(f"  ✅ Índice FAISS creado: {self.index.ntotal} vectores, dim={self._dim}")

    def _find_evidence(self, text: str, top_k: int = 3) -> Tuple[float, List[str]]:
        """
        Busca los chunks más similares a un texto dado.

        Returns:
            (max_score, [chunks más similares])
        """
        if not self.index or not text.strip():
            return 0.0, []

        # Generar embedding del query
        query_emb = self.embedder.embed_texts([text])
        if not query_emb:
            return 0.0, []

        query_vec = np.array(query_emb, dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm

        # Buscar en FAISS
        scores, indices = self.index.search(query_vec, min(top_k, self.index.ntotal))

        results = []
        max_score = 0.0
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.chunks):
                max_score = max(max_score, float(score))
                results.append(self.chunks[idx])

        return max_score, results

    def validate_json(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida cada item de cada campo del JSON contra los documentos fuente.

        Items con score >= threshold pasan limpios.
        Items con score < threshold se marcan con ⚠️.

        Agrega campo "_validacion" con estadísticas.
        """
        if not self.index:
            print("  ⚠️ Sin índice FAISS — retornando JSON sin validar")
            return json_data

        # Campos a validar (excluir campos internos)
        fields_to_validate = [
            "contexto", "que_piden", "causa_raiz", "solucion",
            "validaciones_errores", "impacto_sistemas_bd", "flujo",
            "casos_prueba", "minimo_certificable",
        ]

        validated = dict(json_data)  # Copia
        stats = {
            "total_items": 0,
            "respaldados": 0,
            "baja_confianza": 0,
            "threshold": self.threshold,
            "scores_por_campo": {},
        }

        for field in fields_to_validate:
            items = json_data.get(field)
            if not isinstance(items, list) or not items:
                continue

            field_scores = []
            validated_items = []

            for item in items:
                text = str(item).strip()
                if not text or len(text) < 10:
                    validated_items.append(text)
                    continue

                score, evidence = self._find_evidence(text)
                field_scores.append(round(score, 3))
                stats["total_items"] += 1

                if score >= self.threshold:
                    validated_items.append(text)
                    stats["respaldados"] += 1
                else:
                    validated_items.append(f"⚠️ [Confianza: {score:.0%}] {text}")
                    stats["baja_confianza"] += 1

            validated[field] = validated_items

            if field_scores:
                avg = sum(field_scores) / len(field_scores)
                stats["scores_por_campo"][field] = {
                    "promedio": round(avg, 3),
                    "min": round(min(field_scores), 3),
                    "max": round(max(field_scores), 3),
                    "items": len(field_scores),
                }
                estado = "✅" if avg >= self.threshold else "⚠️"
                print(f"  {estado} {field}: score promedio {avg:.2f} ({len(field_scores)} items)")

        validated["_validacion"] = stats

        total = stats["total_items"]
        ok = stats["respaldados"]
        warn = stats["baja_confianza"]
        if total > 0:
            print(f"\n  📊 Resumen validación: {ok}/{total} respaldados ({ok/total:.0%}), "
                  f"{warn} con baja confianza")

        return validated

    def cleanup(self):
        """Libera memoria del índice FAISS."""
        self.index = None
        self.chunks = []
