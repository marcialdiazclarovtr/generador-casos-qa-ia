"""
API Endpoints — Capa genérica que conecta el frontend con el pipeline.

Endpoints:
- POST /api/upload         → Sube archivos a requerimientos/<session>/
- POST /api/process-docs   → Solo Fase 1: documentos → JSON (para Agente 0)
- POST /api/enhance-json   → Agente 0: mejorar JSON con LLM
- POST /api/generate       → Fase completa: JSON → casos de prueba
- GET  /api/status         → Estado actual del proceso (por sesion)
- POST /api/cancel         → Cancela tarea de una sesion especifica
- GET  /api/files          → Lista archivos generados (todas las sesiones)
- GET  /api/files/{session}→ Lista archivos de una sesión
- GET  /api/matriz         → Obtiene matriz.json (datos base desde backend)
"""
import hashlib
import json
import time
import secrets
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from schemas.request import GenerateRequest, EnhanceJsonRequest
from pipeline import run_pipeline, run_doc_processing, enhance_json_with_llm
from task_queue import TaskQueue, SessionManager

from fastapi import Body

router = APIRouter()

# ── Instancias del sistema de cola (importadas desde app.py via lifespan) ──
session_manager = SessionManager()
task_queue = TaskQueue(session_manager)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_FOLDER = BASE_DIR / "requerimientos"
OUTPUT_FOLDER = BASE_DIR / "output"
JSON_FOLDER = BASE_DIR / "json"
JSON_MATRIX_FOLDER = BASE_DIR / "Datos" / "matriz"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
JSON_FOLDER.mkdir(parents=True, exist_ok=True)

# Extensiones válidas para upload (incluye imágenes)
VALID_EXTENSIONS = (
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp",
    ".txt", ".md",
)


# ── Helpers ──────────────────────────────────────────────

def _file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_hash_path(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(4096), b""):
            sha.update(block)
    return sha.hexdigest()


def _make_status_callback(session_id: str):
    """Retorna un callback update_status(state, message) bound a una sesion."""
    def callback(state: str, message: str = ""):
        session_manager.update_status(session_id, state, message)
    return callback


# ── Upload ───────────────────────────────────────────────

@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Sube archivos y los organiza en una subcarpeta con timestamp.
    Todos los archivos de una misma sesión quedan juntos en:
        requerimientos/YYYYMMDD_HHMMSS/
    """
    session_name = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(3)
    session_folder = UPLOAD_FOLDER / session_name
    session_folder.mkdir(parents=True, exist_ok=True)

    saved_files = []

    for file in files:
        ext = file.filename[file.filename.rfind('.'):].lower() if '.' in file.filename else ''
        if ext in VALID_EXTENSIONS:
            file_path = session_folder / file.filename
            try:
                content = await file.read()
                incoming_hash = _file_hash(content)

                should_save = True
                if file_path.exists():
                    if incoming_hash == _file_hash_path(file_path):
                        should_save = False

                if should_save:
                    with open(file_path, "wb") as f:
                        f.write(content)

                saved_files.append(file.filename)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing file {file.filename}: {str(e)}"
                )

    if not saved_files:
        try:
            session_folder.rmdir()
        except OSError:
            pass
        raise HTTPException(
            status_code=400,
            detail=f"No valid files uploaded. Supported: {', '.join(VALID_EXTENSIONS)}"
        )

    return {
        "message": f"Successfully uploaded {len(saved_files)} files",
        "files": saved_files,
        "session_folder": session_name
    }


# ── Process Documents (cola serial) ─────────────────────

@router.post("/process-docs")
async def process_documents(request: GenerateRequest):
    """
    Encola procesamiento de documentos. El frontend hace polling de /api/status?session=XXX.
    Cuando state='doc_ready', el frontend llama a /api/doc-result para obtener el JSON.
    """
    if not request.session_folder:
        raise HTTPException(status_code=400, detail="session_folder is required")

    upload_target = UPLOAD_FOLDER / request.session_folder
    if not upload_target.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Session folder '{request.session_folder}' not found"
        )

    session_json = JSON_FOLDER / request.session_folder
    session_json.mkdir(parents=True, exist_ok=True)

    session_id = request.session_folder
    session = session_manager.get_or_create(session_id)
    session.tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    session.task_type = "process-docs"

    callback = _make_status_callback(session_id)
    cancel_event = session.cancel_event

    await task_queue.enqueue(
        session_id,
        run_doc_processing,
        upload_target,
        session_json,
        request.dict(),
        callback,
        cancel_event,
    )
    return {"message": "Document processing queued", "status": "queued"}


@router.get("/doc-result")
async def get_doc_result(session: str = Query(...)):
    """
    Retorna el JSON generado por process-docs (una vez que state='doc_ready').
    """
    result_file = JSON_FOLDER / session / "_last_result.json"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="No result available yet")

    with open(result_file, "r", encoding="utf-8") as f:
        result = json.load(f)

    return {
        "status": "success",
        "json_data": result.get("json_data"),
        "json_path": result.get("json_path"),
    }


# ── Enhance JSON (Agente 0 — encolado) ──────────────────

def _run_enhance(json_data, instructions, session_id, status_callback):
    """Wrapper sync para encolar enhance_json_with_llm."""
    status_callback("processing", "Agente 0 mejorando JSON con IA...")
    try:
        enhanced = enhance_json_with_llm(json_data, instructions)
        session = session_manager.get(session_id)
        if session:
            session.result_data = enhanced
            # Persistir instrucciones del usuario para la generación
            if instructions and instructions.strip():
                session.user_focus = instructions.strip()
        status_callback("enhance_ready", "JSON mejorado con exito.")
    except Exception as e:
        status_callback("error", f"Error en Agente 0: {e}")


@router.post("/enhance-json")
async def enhance_json(request: EnhanceJsonRequest):
    """
    Agente 0: Encola mejora de JSON con LLM.
    El frontend hace polling de /api/status?session=XXX.
    Cuando state='enhance_ready', llama a /api/enhance-result?session=XXX.
    """
    session_id = request.session_folder
    if not session_id:
        raise HTTPException(status_code=400, detail="session_folder is required")

    session = session_manager.get_or_create(session_id)
    session.task_type = "enhance-json"
    session.result_data = None

    callback = _make_status_callback(session_id)

    await task_queue.enqueue(
        session_id,
        _run_enhance,
        request.json_data,
        request.instructions,
        session_id,
        callback,
    )
    return {"message": "Enhance queued", "status": "queued"}


@router.get("/enhance-result")
async def get_enhance_result(session: str = Query(...)):
    """Retorna el JSON mejorado por el Agente 0."""
    state = session_manager.get(session)
    if not state or state.result_data is None:
        raise HTTPException(status_code=404, detail="No enhance result available")
    return {"status": "success", "json_data": state.result_data}


# ── Generate (Fase completa → casos de prueba, encolado) ──

@router.post("/generate")
async def trigger_generation(request: GenerateRequest):
    """
    Encola la generación de casos de prueba.
    Puede recibir json_data editado del frontend.
    """
    if request.session_folder:
        upload_target = UPLOAD_FOLDER / request.session_folder
        if not upload_target.exists() or not upload_target.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Session folder '{request.session_folder}' not found"
            )
    else:
        upload_target = UPLOAD_FOLDER

    session_id = request.session_folder or "default"
    session = session_manager.get_or_create(session_id)
    # No resetear tokens — preservar acumulados de Fase 1
    session.log = []
    session.task_type = "generate"

    # Propagar user_focus: puede venir del request o de la sesión (guardado por Agente 0)
    config = request.dict()
    if not config.get("user_focus") and hasattr(session, "user_focus") and session.user_focus:
        config["user_focus"] = session.user_focus

    callback = _make_status_callback(session_id)
    cancel_event = session.cancel_event

    await task_queue.enqueue(
        session_id,
        run_pipeline,
        upload_target,
        OUTPUT_FOLDER,
        JSON_FOLDER,
        config,
        callback,
        cancel_event,
    )
    return {"message": "Generation queued", "status": "queued"}


# ── Status (por sesion) ──────────────────────────────────

@router.get("/status")
async def get_status(session: Optional[str] = Query(None)):
    """Retorna estado de una sesion especifica, o idle si no se especifica."""
    if not session:
        return {"state": "idle", "message": "", "queue_position": 0}
    return session_manager.get_status_dict(session)


# ── Cancel (por sesion) ──────────────────────────────────

@router.post("/cancel")
async def cancel_execution(session: Optional[str] = Query(None)):
    """Cancela la tarea de una sesion especifica."""
    if not session:
        return {"message": "No session specified"}
    state = session_manager.get(session)
    if state:
        state.cancel_event.set()
        session_manager.update_status(session, "cancelled", "Proceso cancelado por el usuario.")
    return {"message": "Cancelled"}


# ── Files (solo CSV/XLSX — sin MD) ───────────────────────

@router.get("/files")
async def list_files(session: Optional[str] = Query(None)):
    """Lista archivos descargables (CSV/XLSX). Filtra .md del listado."""
    target = OUTPUT_FOLDER / session if session else OUTPUT_FOLDER
    files = []
    if target.exists():
        for f in target.rglob("*"):
            if (f.is_file()
                and not f.name.startswith(".")
                and f.suffix.lower() in (".csv", ".xlsx")):
                rel = f.relative_to(OUTPUT_FOLDER)
                files.append({
                    "name": f.name,
                    "path": f"/download/{rel}",
                    "folder": str(rel.parent) if str(rel.parent) != "." else "",
                    "size": f.stat().st_size,
                    "mtime": f.stat().st_mtime,
                })
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files


# ── Cases (tabla de casos de prueba desde CSV) ───────────

@router.get("/cases")
async def get_cases(session: str = Query(...)):
    """Parsea el CSV de casos de prueba y retorna como JSON para tabla."""
    import csv as csv_mod

    csv_file = OUTPUT_FOLDER / session / "casos_prueba.csv"
    if not csv_file.exists():
        raise HTTPException(status_code=404, detail="CSV not found for this session")

    rows = []
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                rows.append(dict(row))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading CSV: {e}")

    return {
        "session": session,
        "total": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "cases": rows,
    }


# ── Sessions (historial de generaciones) ─────────────────

@router.get("/sessions")
async def list_sessions():
    """Lista todas las sesiones de generación con metadata."""
    sessions = []
    if OUTPUT_FOLDER.exists():
        for folder in OUTPUT_FOLDER.iterdir():
            if folder.is_dir() and not folder.name.startswith("."):
                csv_file = folder / "casos_prueba.csv"
                xlsx_file = folder / "casos_prueba.xlsx"
                resumen_files = list(folder.glob("resumen_*.md"))

                if csv_file.exists() or xlsx_file.exists():
                    # Contar casos
                    case_count = 0
                    if csv_file.exists():
                        try:
                            import csv as csv_mod
                            with open(csv_file, "r", encoding="utf-8") as f:
                                case_count = sum(1 for _ in csv_mod.reader(f)) - 1  # -1 header
                        except Exception:
                            pass

                    # Timestamp más reciente
                    files_in_folder = list(folder.iterdir())
                    latest_mtime = max(
                        (f.stat().st_mtime for f in files_in_folder if f.is_file()),
                        default=0
                    )

                    sessions.append({
                        "name": folder.name,
                        "case_count": max(case_count, 0),
                        "has_csv": csv_file.exists(),
                        "has_xlsx": xlsx_file.exists(),
                        "has_resumen": len(resumen_files) > 0,
                        "mtime": latest_mtime,
                        "csv_path": f"/download/{folder.name}/casos_prueba.csv" if csv_file.exists() else None,
                        "xlsx_path": f"/download/{folder.name}/casos_prueba.xlsx" if xlsx_file.exists() else None,
                    })

    sessions.sort(key=lambda x: x["mtime"], reverse=True)
    return sessions


# ── Exponer matriz.json desde el backend ─────────────────

@router.get("/matriz")
async def get_matriz():
    file_path = JSON_MATRIX_FOLDER / "matriz.json"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

@router.put("/matriz")
async def update_matriz(payload: dict = Body(...)):
    file_path = JSON_MATRIX_FOLDER / "matriz.json"
    with open(file_path, "r", encoding="utf-8") as f:
        current = json.load(f)
    current["procesos"] = payload["procesos"]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return {"status": "ok"}