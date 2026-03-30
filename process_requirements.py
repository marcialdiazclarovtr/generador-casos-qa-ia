"""
Módulo integrador: procesa documentos de requerimientos y genera casos de prueba.
"""
from pathlib import Path
from typing import Optional, Dict, List, Any
import json
import re

from pdf_processor import PDFProcessor
from requirement_extractor import RequirementExtractor

CONTENT_FIELDS = [
    "contexto",
    "que_piden",
    "causa_raiz",
    "solucion",
    "validaciones_errores",
    "impacto_sistemas_bd",
    "flujo",
    "casos_prueba",
    "minimo_certificable",
]


def process_requirements_folder(
    requirements_folder: Path,
    output_folder: Path = None,
    use_ocr: bool = False,
    pdf_method: str = "auto",
    input_files: Optional[List[Path]] = None,
    ocr_provider: str = "auto",
    nanonets_api_key: Optional[str] = None,
    nanonets_model_id: Optional[str] = None,
) -> tuple[Dict[str, List[str]], Path, Path]:
    """
    Procesa documentos de requerimientos (PDF/PPTX/imagenes).

    Args:
        requirements_folder: Carpeta con documentos de requerimientos
        output_folder: Carpeta para salidas (default: requirements_folder/processed)
        use_ocr: Si usar OCR para PDFs escaneados e imágenes
        pdf_method: Método de extracción de PDF ("auto", "pypdf2", "pdfplumber", "ocr")
        input_files: Lista opcional de archivos específicos a procesar
        ocr_provider: Proveedor OCR ("auto", "tesseract", "nanonets", "llm")
        nanonets_api_key: API key de Nanonets (opcional; usa env si no se entrega)
        nanonets_model_id: Model ID de Nanonets (opcional; usa env si no se entrega)

    Returns:
        (merged_data, report_path, json_path)
    """
    if output_folder is None:
        output_folder = requirements_folder / "processed"

    output_folder.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("📄 PROCESAMIENTO DE REQUERIMIENTOS")
    print("=" * 70)
    print()

    # 1. Convertir documentos a TXT
    print("FASE 1: Conversión Documentos → TXT")
    print("-" * 70)

    txt_folder = output_folder / "txt"
    txt_folder.mkdir(parents=True, exist_ok=True)

    pdf_processor = PDFProcessor(
        use_ocr=use_ocr,
        ocr_provider=ocr_provider,
        nanonets_api_key=nanonets_api_key,
        nanonets_model_id=nanonets_model_id
    )

    # Evitar duplicar subcarpeta en salida:
    # si todos los documentos vienen de una misma carpeta de 1er nivel,
    # usar esa carpeta como raíz de relativización.
    processing_root = requirements_folder
    if input_files:
        top_levels = set()
        for p in input_files:
            rel = p.relative_to(requirements_folder)
            if len(rel.parts) >= 2:
                top_levels.add(rel.parts[0])
            else:
                top_levels.add("")
        if len(top_levels) == 1:
            only = next(iter(top_levels))
            if only:
                processing_root = requirements_folder / only

    txt_files = pdf_processor.process_folder(
        folder=processing_root,
        output_folder=txt_folder,
        method=pdf_method,
        recursive=True,
        input_files=input_files
    )

    if not txt_files:
        raise ValueError(f"No se encontraron documentos soportados en {requirements_folder}")

    print(f"\n✅ Convertidos {len(txt_files)} documento(s) a TXT")
    print()

    # 2. Extraer información estructurada
    print("FASE 2: Extracción de Información")
    print("-" * 70)

    extractor = RequirementExtractor()
    merged_data, report_path, json_path = extractor.process_documents(
        txt_files=txt_files,
        output_dir=output_folder
    )

    # Fallback: si extracción LLM quedó inválida, construir merged útil desde TXT
    if not is_valid_processed_requirements(merged_data):
        print("⚠️  Extracción con LLM inválida (EXTRACT_FAIL). Aplicando fallback desde TXT...")
        merged_data = build_fallback_requirements_from_txt(txt_files)
        fallback_report = build_requirements_report_md(
            merged_data,
            title="Informe de Requerimientos Procesados (Fallback TXT)"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(fallback_report)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        print("✅ Fallback TXT aplicado y guardado en reporte/json.")

    # ── FASE 2.5: Validación FAISS ──────────────────────────────────────────
    print()
    print("FASE 2.5: Validación FAISS — verificando contra documentos fuente")
    print("-" * 70)
    try:
        from faiss_validator import FAISSValidator
        from llm_client import get_embedding_client

        validator = FAISSValidator(get_embedding_client(), similarity_threshold=0.35)
        validator.index_source_texts(txt_files)
        merged_data = validator.validate_json(merged_data)
        validator.cleanup()

        # Guardar JSON validado
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        print("✅ JSON validado con FAISS guardado")

    except ImportError:
        print("⚠️ faiss-cpu no instalado — saltando validación FAISS")
    except Exception as e:
        print(f"⚠️ Error en validación FAISS: {e} — continuando sin validar")

    print()
    print("=" * 70)
    print("✅ PROCESAMIENTO COMPLETADO")
    print("=" * 70)
    print(f"\n📊 Información extraída:")
    for field, items in merged_data.items():
        if field.startswith("_"):
            continue
        count = len(items)
        if count > 0:
            print(f"  • {field}: {count} item(s)")

    print(f"\n📁 Archivos generados:")
    print(f"  • Reporte: {report_path}")
    print(f"  • JSON:    {json_path}")
    print()

    return merged_data, report_path, json_path


def load_processed_requirements(json_path: Path) -> Optional[Dict[str, Any]]:
    """
    Carga un JSON de requerimientos ya procesado.

    Args:
        json_path: Ruta al JSON procesado

    Returns:
        Diccionario con la información extraída o None si no existe
    """
    if not json_path.exists():
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_valid_processed_requirements(data: Optional[Dict[str, Any]]) -> bool:
    """
    Determina si un JSON procesado tiene contenido útil.
    Inválido típico: todos los campos vacíos y evidencia solo con EXTRACT_FAIL.
    """
    if not isinstance(data, dict):
        return False

    # Señal útil real (excluye "contexto" porque puede venir con 1 línea genérica).
    strong_fields = [
        "que_piden",
        "causa_raiz",
        "solucion",
        "validaciones_errores",
        "impacto_sistemas_bd",
        "flujo",
        "casos_prueba",
        "minimo_certificable",
    ]
    useful_items = 0
    for k in strong_fields:
        v = data.get(k) or []
        if isinstance(v, list):
            useful_items += sum(1 for x in v if str(x).strip())
        elif str(v).strip():
            useful_items += 1

    evidencia = data.get("evidencia") or []
    if not isinstance(evidencia, list) or not evidencia:
        # Sin evidencia solo es válido si tiene suficiente contenido estructurado.
        return useful_items >= 5

    # Medir ratio de fallos en evidencia.
    extract_fail_count = 0
    non_fail_evidence = 0
    for item in evidencia:
        txt = str(item).strip()
        if not txt:
            continue
        if txt.startswith("[EXTRACT_FAIL]"):
            extract_fail_count += 1
        else:
            non_fail_evidence += 1

    total_ev = max(1, extract_fail_count + non_fail_evidence)
    fail_ratio = extract_fail_count / total_ev

    # Criterio de invalidez para casos como Netflix_iva_NF:
    # mucha evidencia de fallo + casi sin contenido estructurado.
    if useful_items < 4 and fail_ratio >= 0.6:
        return False

    # Válido si tiene suficiente estructura o evidencia no fallida razonable.
    return useful_items >= 4 or non_fail_evidence >= 4


def get_latest_processed_requirements(json_folder: Path) -> Optional[Path]:
    """
    Encuentra el JSON procesado más reciente.

    Args:
        json_folder: Carpeta donde están los JSONs procesados

    Returns:
        Ruta al JSON más reciente o None si no existe
    """
    if not json_folder.exists():
        return None

    json_files = list(json_folder.glob("merged_*.json"))
    if not json_files:
        return None

    # Ordenar por fecha de modificación (más reciente primero)
    json_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Preferir el más reciente que sea válido
    for jf in json_files:
        try:
            data = load_processed_requirements(jf)
            if is_valid_processed_requirements(data):
                return jf
        except Exception:
            continue

    # Si ninguno es válido, retornar None para forzar reproceso/continuar sin contexto
    return None


def requirements_to_context(merged_data: Dict[str, List[str]]) -> str:
    """
    Convierte la información de requerimientos en contexto para el generador.

    Args:
        merged_data: Datos procesados de requerimientos

    Returns:
        String con contexto formateado
    """
    context_parts = []

    # Contexto y qué piden
    if merged_data.get("contexto"):
        context_parts.append("CONTEXTO DEL PROYECTO:")
        context_parts.extend([f"• {x}" for x in merged_data["contexto"]])
        context_parts.append("")

    if merged_data.get("que_piden"):
        context_parts.append("REQUERIMIENTOS:")
        context_parts.extend([f"• {x}" for x in merged_data["que_piden"]])
        context_parts.append("")

    if merged_data.get("causa_raiz"):
        context_parts.append("CAUSA RAÍZ:")
        context_parts.extend([f"• {x}" for x in merged_data["causa_raiz"]])
        context_parts.append("")

    # Solución y flujo
    if merged_data.get("solucion"):
        context_parts.append("SOLUCIÓN IMPLEMENTADA:")
        context_parts.extend([f"• {x}" for x in merged_data["solucion"]])
        context_parts.append("")

    if merged_data.get("flujo"):
        context_parts.append("FLUJO DE PROCESO:")
        context_parts.extend([f"• {x}" for x in merged_data["flujo"]])
        context_parts.append("")

    # Validaciones y sistemas impactados
    if merged_data.get("validaciones_errores"):
        context_parts.append("VALIDACIONES Y ERRORES:")
        context_parts.extend([f"• {x}" for x in merged_data["validaciones_errores"]])
        context_parts.append("")

    if merged_data.get("impacto_sistemas_bd"):
        context_parts.append("SISTEMAS Y BD IMPACTADOS:")
        context_parts.extend([f"• {x}" for x in merged_data["impacto_sistemas_bd"]])
        context_parts.append("")

    # Casos de prueba sugeridos
    if merged_data.get("casos_prueba"):
        context_parts.append("CASOS DE PRUEBA SUGERIDOS EN REQUERIMIENTOS:")
        context_parts.extend([f"• {x}" for x in merged_data["casos_prueba"]])
        context_parts.append("")

    # Mínimo certificable
    if merged_data.get("minimo_certificable"):
        context_parts.append("MÍNIMO CERTIFICABLE:")
        context_parts.extend([f"• {x}" for x in merged_data["minimo_certificable"]])
        context_parts.append("")

    if merged_data.get("evidencia"):
        context_parts.append("EVIDENCIA RELEVANTE DEL DOCUMENTO:")
        context_parts.extend([f"• {x}" for x in (merged_data["evidencia"][:40])])
        context_parts.append("")

    return "\n".join(context_parts)


def _dedupe_keep_order(items: List[str], limit: int = 120) -> List[str]:
    seen = set()
    out = []
    for it in items:
        s = str(it).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _collect_matching_lines(text: str, patterns: List[str], max_items: int = 20) -> List[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    matched = []
    for ln in lines:
        low = ln.lower()
        if any(p in low for p in patterns):
            matched.append(ln)
            if len(matched) >= max_items:
                break
    return matched


def _first_nonempty_paragraphs(text: str, max_items: int = 8) -> List[str]:
    parts = re.split(r"\n\s*\n", text)
    out = []
    for p in parts:
        s = " ".join(p.split())
        if len(s) >= 40:
            out.append(s[:400])
        if len(out) >= max_items:
            break
    return out


def build_fallback_requirements_from_txt(txt_files: List[Path]) -> Dict[str, List[str]]:
    """
    Construye un merged mínimo útil usando solo texto de los .txt,
    sin depender del proveedor LLM (Ollama/OpenAI-compatible).
    """
    merged = {k: [] for k in CONTENT_FIELDS}
    merged["evidencia"] = []

    all_texts = []
    for p in txt_files:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            # Limpiar headers de página para mejorar señal
            raw = re.sub(r"---\s*P[ÁA]GINA.*?---", "", raw, flags=re.I)
            all_texts.append((p.name, raw))
        except Exception:
            continue

    if not all_texts:
        merged["evidencia"] = ["[FALLBACK_TXT] No se pudieron leer archivos TXT."]
        return merged

    combined = "\n\n".join(t for _, t in all_texts)

    # Contexto general
    merged["contexto"].extend(_first_nonempty_paragraphs(combined, max_items=12))

    # Heurísticas por campo
    merged["que_piden"].extend(_collect_matching_lines(
        combined,
        ["se requiere", "debe", "deberá", "objetivo", "alcance", "solicita"],
        max_items=40
    ))
    merged["causa_raiz"].extend(_collect_matching_lines(
        combined,
        ["causa raíz", "problema", "incidente", "error detectado", "origen"],
        max_items=20
    ))
    merged["solucion"].extend(_collect_matching_lines(
        combined,
        ["se implementa", "se modifica", "modificar", "ajuste", "corregir", "policy", "librería"],
        max_items=40
    ))
    merged["validaciones_errores"].extend(_collect_matching_lines(
        combined,
        ["valid", "error", "restric", "rechazar", "no permitir", "debe mostrar", "resultado esperado"],
        max_items=40
    ))
    merged["impacto_sistemas_bd"].extend(_collect_matching_lines(
        combined,
        ["brm", "siebel", "osm", "uim", "toa", "giap", "ams", "bbms", "ebs", "campo", "vtr_", "iva_nfa", "netflix"],
        max_items=60
    ))
    merged["flujo"].extend(_collect_matching_lines(
        combined,
        ["flujo", "paso", "proceso", "venta", "postventa", "factur", "cobranza", "nota de crédito", "modificación"],
        max_items=60
    ))
    merged["casos_prueba"].extend(_collect_matching_lines(
        combined,
        ["caso de prueba", "precondición", "precondicion", "paso a paso", "resultado esperado", "datos de prueba"],
        max_items=40
    ))
    merged["minimo_certificable"].extend(_collect_matching_lines(
        combined,
        ["mínimo certificable", "minimo certificable", "criterio de aceptación", "aceptación", "done"],
        max_items=20
    ))

    # Evidencia compacta
    for name, raw in all_texts:
        snippets = _first_nonempty_paragraphs(raw, max_items=4)
        for s in snippets:
            merged["evidencia"].append(f"[FALLBACK_TXT] {name}: {s[:220]}")

    # Si algún campo sigue vacío, relleno mínimo desde contexto
    if not merged["que_piden"] and merged["contexto"]:
        merged["que_piden"] = merged["contexto"][:6]
    if not merged["solucion"] and merged["impacto_sistemas_bd"]:
        merged["solucion"] = merged["impacto_sistemas_bd"][:8]

    # Deduplicar
    for k in list(merged.keys()):
        if isinstance(merged[k], list):
            merged[k] = _dedupe_keep_order(merged[k], limit=120)

    return merged


def build_requirements_report_md(merged_data: Dict[str, List[str]], title: str) -> str:
    """Genera reporte markdown legible desde merged_data."""
    sections = [
        ("contexto", "Contexto"),
        ("que_piden", "Qué piden"),
        ("causa_raiz", "Causa raíz"),
        ("solucion", "Solución"),
        ("validaciones_errores", "Validaciones / errores"),
        ("impacto_sistemas_bd", "Impacto (sistemas/BD)"),
        ("flujo", "Flujo"),
        ("casos_prueba", "Casos de prueba (propuestos/encontrados)"),
        ("minimo_certificable", "Mínimo certificable"),
        ("evidencia", "Evidencia (citas cortas)"),
    ]

    lines = [f"# {title}", ""]
    for key, label in sections:
        lines.append(f"## {label}")
        vals = merged_data.get(key) or []
        if vals:
            for v in vals:
                lines.append(f"- {v}")
        else:
            lines.append("No especificado en los documentos.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    # Test del flujo completo
    base_dir = Path(__file__).parent
    req_folder = base_dir / "requerimientos"

    if not req_folder.exists():
        print(f"Crear carpeta: {req_folder}")
        req_folder.mkdir(parents=True)
        print(f"Coloca tus documentos en: {req_folder}")
    else:
        # Verificar si hay documentos soportados
        docs = [
            p for p in req_folder.rglob("*")
            if p.is_file() and p.suffix.lower() in {
                ".pdf", ".pptx", ".docx", ".xlsx",
                ".doc", ".ppt", ".xls", ".odt", ".odp", ".ods",
                ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".log", ".ini", ".cfg", ".sql",
                ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"
            }
        ]
        if not docs:
            print(f"⚠️  No hay documentos soportados en {req_folder}")
            print("Coloca documentos de requerimientos (PDF/Office/texto/imagenes) ahí.")
        else:
            print(f"Encontrados {len(docs)} documento(s) en {req_folder}")
            print("\nProcesando...")

            try:
                merged_data, report_path, json_path = process_requirements_folder(
                    requirements_folder=req_folder
                )

                print("\n" + "=" * 70)
                print("CONTEXTO GENERADO PARA CASOS DE PRUEBA:")
                print("=" * 70)
                print()
                context = requirements_to_context(merged_data)
                print(context)

            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
