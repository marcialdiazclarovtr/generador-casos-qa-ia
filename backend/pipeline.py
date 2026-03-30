"""
Pipeline adapter: puente entre el API y el sistema multi-agente.

Contrato:
    - run_pipeline(upload_folder, output_folder, json_folder, config_request, status_callback)
    - process_docs_only(upload_folder, json_folder, config_request) -> dict
    - enhance_json_with_llm(json_data, instructions) -> dict
    - status_callback(state: str, message: str)
"""
import sys
import io
import json
from pathlib import Path
from datetime import datetime

# Agregar raíz del proyecto al path para importar los scripts del modelo
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


class _StatusCapture(io.TextIOBase):
    """
    Intercepta stdout para capturar los prints del modelo
    y reenviarlos como status_callback al frontend.
    """
    def __init__(self, callback, original_stdout):
        self._callback = callback
        self._original = original_stdout
        self._buffer = ""

    def write(self, text):
        # Escribir también al stdout original (para logs del servidor)
        self._original.write(text)
        self._original.flush()

        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                self._callback("processing", line)
        return len(text)

    def flush(self):
        self._original.flush()


def _configure_llm(config_request: dict):
    """Configura el modelo LLM según el request."""
    from config import config
    config.base_url = config_request.get("lm_url", config.base_url)
    if config_request.get("model"):
        config.model = config_request["model"]

    # Reset LLM client para que tome la nueva config
    try:
        from llm_client import cleanup
        cleanup()
    except (ImportError, Exception):
        pass


def _process_documents(upload_folder: Path, json_folder: Path, config_request: dict) -> tuple:
    """
    Fase 1: Procesa documentos y genera JSON.
    Retorna (merged_data, json_path) o (None, None) si falla.
    """
    from process_requirements import (
        process_requirements_folder,
        get_latest_processed_requirements,
        load_processed_requirements,
        is_valid_processed_requirements,
        build_fallback_requirements_from_txt,
    )

    # Extensiones soportadas
    supported_exts = (
        "*.pdf", "*.docx", "*.doc", "*.pptx", "*.ppt",
        "*.xlsx", "*.xls", "*.png", "*.jpg", "*.jpeg",
        "*.bmp", "*.tif", "*.tiff", "*.webp",
        "*.txt", "*.md",
    )
    input_files = []
    for ext in supported_exts:
        input_files.extend(upload_folder.glob(ext))

    latest_json = get_latest_processed_requirements(json_folder)
    should_process = config_request.get("process_requirements", True)

    # ¿Necesitamos reprocesar?
    real_process = False
    if should_process and input_files:
        if not latest_json:
            real_process = True
        else:
            try:
                input_mtime = max(p.stat().st_mtime for p in input_files)
                json_mtime = latest_json.stat().st_mtime
                if input_mtime > json_mtime:
                    real_process = True
                else:
                    print("ℹ️ Requerimientos ya procesados — usando caché...")
            except Exception:
                real_process = True

    if real_process:
        n_files = len(input_files)
        print(f"📄 FASE 1 — Procesando {n_files} documento(s)...")
        merged_data, _, json_path = process_requirements_folder(
            requirements_folder=upload_folder,
            output_folder=json_folder,
            use_ocr=config_request.get("use_ocr", False),
        )
        if is_valid_processed_requirements(merged_data):
            print(f"✅ JSON generado: {json_path.name}")
            return merged_data, json_path
        else:
            # Intentar fallback
            txt_dir = json_folder / "txt"
            if txt_dir.exists():
                txt_files = sorted(txt_dir.glob("*.txt"))
                if txt_files:
                    fallback = build_fallback_requirements_from_txt(txt_files)
                    if fallback:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        fallback_path = json_folder / f"merged_{ts}.json"
                        with open(fallback_path, "w", encoding="utf-8") as f:
                            json.dump(fallback, f, ensure_ascii=False, indent=2)
                        print(f"✅ Fallback JSON generado: {fallback_path.name}")
                        return fallback, fallback_path

    # Usar JSON existente
    if latest_json:
        merged_data = load_processed_requirements(latest_json)
        return merged_data, latest_json

    return None, None


def run_doc_processing(
    upload_folder: Path,
    json_folder: Path,
    config_request: dict,
    status_callback,
    cancel_event=None,
):
    """
    Procesa documentos en background con captura de stdout.
    Cuando termina, pone state='doc_ready' y guarda el JSON en status.
    """
    original_stdout = sys.stdout
    try:
        sys.stdout = _StatusCapture(status_callback, original_stdout)

        status_callback("processing", "📄 Iniciando procesamiento de documentos...")
        _configure_llm(config_request)
        json_folder.mkdir(parents=True, exist_ok=True)

        if cancel_event and cancel_event.is_set():
            status_callback("cancelled", "Proceso cancelado por el usuario.")
            return

        merged_data, json_path = _process_documents(upload_folder, json_folder, config_request)

        if merged_data and json_path:
            # Guardar resultado para que el frontend lo recoja
            result_file = json_folder / "_last_result.json"
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump({
                    "json_data": merged_data,
                    "json_path": str(json_path),
                }, f, ensure_ascii=False, indent=2)

            status_callback("doc_ready", "✅ Documentos procesados y validados con FAISS. Listo para revisión.")
        else:
            status_callback("error", "No se pudo generar JSON de los documentos.")

    except Exception as e:
        status_callback("error", f"Error procesando documentos: {e}")
    finally:
        sys.stdout = original_stdout


def enhance_json_with_llm(json_data: dict, instructions: str = "") -> dict:
    """
    Agente 0: Usa el LLM para mejorar/enriquecer el JSON de requerimientos.
    Ahora con razonamiento de enfoque: si el usuario da instrucciones,
    el LLM analiza qué campos modificar sin romper el resto.
    """
    from llm_client import get_llm_client, JSONExtractor

    llm = get_llm_client()

    # Serializar los campos actuales
    json_text = json.dumps(json_data, ensure_ascii=False, indent=2)

    # Construir sección de enfoque según si hay instrucciones o no
    if instructions and instructions.strip():
        focus_section = f"""=== INSTRUCCIONES DE ENFOQUE DEL USUARIO ===
El usuario ha pedido lo siguiente:
"{instructions}"

RAZONAMIENTO DE ENFOQUE — Antes de modificar el JSON, analiza:
1. ¿Qué campos del JSON se relacionan con la petición del usuario?
   (ej: si dice "enfócate en red NEUTRA", los campos de flujo, impacto_sistemas_bd y solucion
   probablemente necesiten ajustes para reflejar esa tecnología)
2. ¿Qué campos NO deben cambiar? (ej: contexto general del proyecto normalmente se mantiene)
3. ¿Cómo puedes reenfocar el JSON sin eliminar información válida?
   - Si el requerimiento menciona múltiples tecnologías, PRIORIZA la que el usuario pide
   - Si hay flujos genéricos, ESPECÍFICALOS para la tecnología/red/marca solicitada
   - Si hay información contradictoria con el enfoque, MANTÉN ambas pero DESTACA la del enfoque

REGLA CRÍTICA: NO elimines información válida. REORDÉNALA y ENRIQUÉCELA para que
el enfoque del usuario esté prominente pero el contexto completo se preserve."""
    else:
        focus_section = """=== INSTRUCCIONES ===
No hay instrucciones específicas del usuario. Mejorar la estructura general
y completar campos incompletos."""

    prompt = f"""Eres un experto en análisis de requerimientos de telecomunicaciones (Claro/VTR Chile).
Se te proporciona un JSON con la información extraída de los documentos de un requerimiento.

Tu tarea es MEJORAR y COMPLETAR este JSON para que sea más útil para generar casos de prueba QA.

=== JSON ACTUAL ===
{json_text[:6000]}

{focus_section}

=== QUÉ DEBES HACER ===
1. Mantener TODOS los campos existentes (contexto, que_piden, solucion, impacto_sistemas_bd, flujo, etc.)
2. Completar información faltante si se puede inferir del contexto
3. Estructurar mejor los textos largos en puntos concretos
4. Corregir errores de OCR o texto mal extraído si los detectas
5. Agregar detalles técnicos implícitos (sistemas, plataformas, etc.)
6. NO inventar información que no esté en el texto original
7. Si el usuario dio instrucciones de enfoque, ASEGÚRATE de que el JSON refleje ese enfoque
   en los campos relevantes (que_piden, solucion, flujo, impacto_sistemas_bd)

IMPORTANTE: Responde SOLO con el JSON mejorado, sin texto adicional.
El JSON debe tener la misma estructura (mismos campos) pero con contenido mejorado.
Cada campo debe ser una lista de strings.
Si el usuario dio instrucciones de enfoque, agrega un campo "_user_focus" con el texto del enfoque."""

    try:
        raw = llm.chat_with_retry(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        enhanced = JSONExtractor.extract(raw)

        # Asegurar que _user_focus se propague incluso si el LLM no lo incluyó
        if instructions and instructions.strip():
            enhanced["_user_focus"] = instructions.strip()

        return enhanced
    except Exception as e:
        print(f"⚠️ Error mejorando JSON con LLM: {e}")
        return json_data  # Retornar original si falla


def run_pipeline(
    upload_folder: Path,
    output_folder: Path,
    json_folder: Path,
    config_request: dict,
    status_callback,
    cancel_event=None,
):
    """
    Ejecuta el pipeline completo de generación de casos de prueba.

    Args:
        upload_folder: Carpeta con documentos subidos (requerimientos/<session>)
        output_folder: Carpeta para output (output/)
        json_folder:   Carpeta para JSONs intermedios (json/)
        config_request: Dict con model, lm_url, max_casos, session_folder, etc.
        status_callback: Función(state, message) para reportar progreso
    """
    original_stdout = sys.stdout
    try:
        # Interceptar stdout para capturar prints del modelo
        sys.stdout = _StatusCapture(status_callback, original_stdout)

        status_callback("processing", "Iniciando proceso...")
        _configure_llm(config_request)

        # Subcarpeta por sesión
        session_name = config_request.get("session_folder", "")
        if session_name:
            session_json_folder = json_folder / session_name
        else:
            session_json_folder = json_folder
        session_json_folder.mkdir(parents=True, exist_ok=True)

        # ── FASE 1: Procesar documentos ──
        if cancel_event and cancel_event.is_set():
            status_callback("cancelled", "Proceso cancelado por el usuario.")
            return

        status_callback("processing", "FASE 1 — Procesando documentos...")
        merged_data, json_path = _process_documents(
            upload_folder, session_json_folder, config_request
        )

        if not merged_data or not json_path:
            status_callback("error", "No se pudo generar JSON de los documentos.")
            return

        # Si viene json_data editado en el request, usarlo en vez del procesado
        edited_json = config_request.get("json_data")
        if edited_json:
            merged_data = edited_json
            # Guardar el JSON editado
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            edited_path = session_json_folder / f"merged_edited_{ts}.json"
            with open(edited_path, "w", encoding="utf-8") as f:
                json.dump(edited_json, f, ensure_ascii=False, indent=2)
            json_path = edited_path
            status_callback("processing", "Usando JSON editado por el usuario.")

        # Cargar el JSON final
        with open(json_path, encoding="utf-8") as f:
            json_req = json.load(f)

        # ── FASE 2: Generar casos de prueba ──
        if cancel_event and cancel_event.is_set():
            status_callback("cancelled", "Proceso cancelado por el usuario.")
            return

        status_callback("processing", "FASE 2 — Cargando base de conocimiento...")

        from knowledge_loader import load_all
        from agente_maestro import AgenteMaestro
        from llm_client import get_llm_client, cleanup

        datos_dir = _PROJECT_ROOT / "Datos"
        kb = load_all(datos_dir)

        llm = get_llm_client()
        if not llm.check_connection():
            status_callback("error", "No se pudo conectar al servidor LLM.")
            return

        max_casos = config_request.get("max_casos", 20)
        session_output = output_folder / session_name if session_name else output_folder
        session_output.mkdir(parents=True, exist_ok=True)

        # Extraer user_focus: puede venir del config_request o del JSON mejorado por Agente 0
        user_focus = config_request.get("user_focus", "") or json_req.get("_user_focus", "")
        if user_focus:
            print(f"📌 Enfoque del usuario: {user_focus}")

        status_callback("processing", f"FASE 2 — Generando hasta {max_casos} casos de prueba...")

        maestro = AgenteMaestro(kb, llm, user_focus=user_focus)
        casos = maestro.ejecutar(json_req, max_casos=max_casos, output_dir=session_output, cancel_event=cancel_event)

        if casos:
            # Guardar resumen
            resumen = maestro.get_resumen()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            resumen_path = session_output / f"resumen_{ts}.md"
            with open(resumen_path, "w", encoding="utf-8") as f:
                f.write(resumen)

            status_callback(
                "success",
                f"✅ ¡Generación completada! {len(casos)} casos de prueba listos para descargar."
            )
        else:
            status_callback("error", "No se generaron casos de prueba.")

    except Exception as e:
        status_callback("error", str(e))

    finally:
        sys.stdout = original_stdout
        try:
            from llm_client import cleanup
            cleanup()
        except Exception:
            pass
