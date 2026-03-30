#!/usr/bin/env python3
"""
Flujo Nuevo: Procesamiento de Requerimientos → JSON

Convierte documentos de la carpeta requerimientos/ (PDF, PPTX, DOCX, XLSX,
imágenes, texto) en JSON estructurado + reporte Markdown.

Uso:
    python main.py
    python main.py --requirements-folder ruta/a/docs
    python main.py --use-ocr --pdf-method pdfplumber
    python main.py --force
"""
import argparse
import sys
import re
from pathlib import Path
from datetime import datetime

# Agregar directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from process_requirements import (
    process_requirements_folder,
    load_processed_requirements,
    get_latest_processed_requirements,
    requirements_to_context,
    is_valid_processed_requirements,
    build_requirements_report_md,
)

# Extensiones soportadas
REQUIREMENT_EXTENSIONS = {
    ".pdf", ".pptx", ".docx", ".xlsx",
    ".doc", ".ppt", ".xls", ".odt", ".odp", ".ods",
    ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".log", ".ini", ".cfg", ".sql",
    ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_args():
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Flujo Nuevo: Procesamiento de Requerimientos → JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Procesar carpeta requerimientos/ (auto-detecta documentos)
  python main.py

  # Forzar reprocesamiento
  python main.py --force

  # Usar OCR para documentos escaneados
  python main.py --use-ocr

  # Especificar carpeta de entrada
  python main.py --requirements-folder ruta/a/docs

  # Usar un método específico de extracción de PDF
  python main.py --pdf-method pdfplumber
        """
    )

    # Entrada
    parser.add_argument(
        "--requirements-folder", "-rf",
        type=Path,
        default=Path("requerimientos"),
        help="Carpeta con documentos de requerimientos"
    )
    parser.add_argument(
        "--output-folder", "-o",
        type=Path,
        default=Path("json"),
        help="Carpeta base para salida JSON/TXT (default: json/)"
    )

    # PDF / OCR
    parser.add_argument(
        "--use-ocr",
        action="store_true",
        help="Usar OCR para PDFs escaneados e imágenes"
    )
    parser.add_argument(
        "--ocr-provider",
        type=str,
        default="auto",
        choices=["auto", "tesseract", "nanonets"],
        help="Proveedor OCR: auto (nanonets→tesseract), tesseract o nanonets"
    )
    parser.add_argument(
        "--pdf-method",
        type=str,
        default="auto",
        choices=["auto", "pypdf2", "pdfplumber", "ocr"],
        help="Método de extracción de PDF"
    )
    parser.add_argument(
        "--nanonets-api-key",
        type=str,
        default=None,
        help="API key de Nanonets OCR"
    )
    parser.add_argument(
        "--nanonets-model-id",
        type=str,
        default=None,
        help="Model ID de Nanonets OCR"
    )

    # Ollama
    parser.add_argument(
        "--lm-url",
        type=str,
        default="http://127.0.0.1:11434/v1",
        help="URL de Ollama API (OpenAI-compatible)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-oss:20b",
        help="Modelo de Ollama a usar"
    )

    # Control
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forzar reprocesamiento aunque ya exista JSON"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Modo verbose"
    )

    return parser.parse_args()


def find_requirement_docs(requirements_folder: Path) -> list[Path]:
    """Busca documentos soportados de forma recursiva."""
    if not requirements_folder.exists():
        return []
    return sorted(
        p for p in requirements_folder.rglob("*")
        if p.is_file() and p.suffix.lower() in REQUIREMENT_EXTENSIONS
    )


def sanitize_label(value: str) -> str:
    """Normaliza etiqueta para nombre de carpeta/archivo."""
    label = (value or "").strip()
    if not label:
        return "requerimiento"
    label = re.sub(r"\s+", "_", label)
    label = re.sub(r"[^A-Za-z0-9._-]", "_", label)
    label = re.sub(r"_+", "_", label).strip("._-")
    return label or "requerimiento"


def group_files_by_top_folder(
    requirements_folder: Path, files: list[Path]
) -> dict[str, list[Path]]:
    """Agrupa archivos por subcarpeta de primer nivel."""
    grouped: dict[str, list[Path]] = {}
    for f in files:
        rel = f.relative_to(requirements_folder)
        top = rel.parts[0] if len(rel.parts) >= 2 else "raiz_requerimientos"
        grouped.setdefault(top, []).append(f)
    for k in list(grouped.keys()):
        grouped[k] = sorted(grouped[k])
    return grouped


def infer_requirement_label(requirements_folder: Path, docs: list[Path]) -> str:
    """Infiere nombre lógico del requerimiento desde subcarpetas."""
    if not docs:
        return "requerimiento"
    top_folders = set()
    for doc in docs:
        rel = doc.relative_to(requirements_folder)
        if len(rel.parts) >= 2:
            top_folders.add(rel.parts[0])
        else:
            top_folders.add("raiz_requerimientos")

    if len(top_folders) == 1:
        return sanitize_label(next(iter(top_folders)))
    return "multi_requerimientos"


def print_folder_summary(requirements_folder: Path, docs: list[Path]) -> None:
    """Muestra resumen de subcarpetas con documentos."""
    from collections import defaultdict
    grouped: dict[str, list[str]] = defaultdict(list)
    for doc in docs:
        rel = doc.relative_to(requirements_folder)
        key = str(rel.parent) if str(rel.parent) != "." else "(raíz)"
        grouped[key].append(doc.name)

    if not grouped:
        return
    print("📁 Resumen de subcarpetas de requerimientos:")
    for folder in sorted(grouped.keys()):
        names = sorted(grouped[folder])
        print(f"   • {folder}: {len(names)} archivo(s)")
        for name in names:
            print(f"      - {name}")
    print()


# ── Procesamiento por requerimiento ──────────────────────────────────────────

def process_single_requirement(
    args,
    requirement_label: str,
    group_files: list[Path],
) -> bool:
    """
    Procesa un grupo de documentos y genera JSON + reporte.
    Retorna True si fue exitoso.
    """
    json_folder = args.output_folder / requirement_label
    json_folder.mkdir(parents=True, exist_ok=True)

    # Verificar si ya existe un JSON procesado
    existing_json = get_latest_processed_requirements(json_folder)
    if existing_json and not args.force:
        print(f"ℹ️  Ya existe JSON procesado: {existing_json.name}")
        print(f"ℹ️  Usa --force para reprocesar.\n")
        return True

    # Procesar documentos
    try:
        merged_data, report_path, json_path = process_requirements_folder(
            requirements_folder=args.requirements_folder,
            output_folder=json_folder,
            use_ocr=args.use_ocr,
            pdf_method=args.pdf_method,
            input_files=group_files,
            ocr_provider=args.ocr_provider,
            nanonets_api_key=args.nanonets_api_key,
            nanonets_model_id=args.nanonets_model_id,
        )

        if is_valid_processed_requirements(merged_data):
            context = requirements_to_context(merged_data)
            print(f"\n✅ Procesado exitosamente:")
            print(f"   JSON:    {json_path}")
            print(f"   Reporte: {report_path}")
            print(f"   Contexto generado: {len(context)} caracteres\n")
            return True
        else:
            print("⚠️  El JSON generado no tiene contenido útil (posible fallo de extracción).")
            if existing_json:
                print(f"ℹ️  Se conserva el JSON previo: {existing_json.name}")
            return False

    except Exception as e:
        print(f"\n❌ Error procesando: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    """Función principal."""
    args = parse_args()

    print("=" * 60)
    print("📄 FLUJO NUEVO: PROCESAMIENTO DE REQUERIMIENTOS → JSON")
    print("=" * 60)
    print()

    # Mostrar configuración
    print("📋 Configuración:")
    print(f"   Carpeta docs:  {args.requirements_folder}")
    print(f"   Salida JSON:   {args.output_folder}")
    print(f"   Método PDF:    {args.pdf_method}")
    print(f"   OCR:           {'Activado' if args.use_ocr else 'Desactivado'}")
    if args.use_ocr:
        print(f"   OCR Provider:  {args.ocr_provider}")
    print(f"   Ollama API:    {args.lm_url}")
    print(f"   Modelo:        {args.model}")
    print(f"   Forzar:        {'Sí' if args.force else 'No'}")
    print()

    # Actualizar config global si se especificó
    if args.lm_url != "http://127.0.0.1:11434/v1" or args.model != "gpt-oss:20b":
        from config import config
        config.base_url = args.lm_url
        config.model = args.model

    # Buscar documentos
    all_docs = find_requirement_docs(args.requirements_folder)
    if not all_docs:
        print(f"❌ No se encontraron documentos soportados en: {args.requirements_folder}")
        print(f"   Extensiones soportadas: {', '.join(sorted(REQUIREMENT_EXTENSIONS))}")
        sys.exit(1)

    print(f"📂 Encontrados {len(all_docs)} documento(s) en {args.requirements_folder}")
    print_folder_summary(args.requirements_folder, all_docs)

    # Agrupar por subcarpeta de primer nivel
    grouped = group_files_by_top_folder(args.requirements_folder, all_docs)

    if len(grouped) <= 1:
        # Un solo requerimiento / todos en raíz
        label = infer_requirement_label(args.requirements_folder, all_docs)
        print(f"📁 Requerimiento detectado: {label}")
        print(f"📁 Salida en: {args.output_folder / label}")
        print()

        success = process_single_requirement(args, label, all_docs)
        if not success:
            sys.exit(1)
    else:
        # Múltiples requerimientos
        print(f"🧩 Modo multi-requerimiento: {len(grouped)} carpetas detectadas.\n")
        grouped_sorted = sorted(grouped.items(), key=lambda x: x[0])
        total = len(grouped_sorted)
        ok_count = 0

        for idx, (top_folder, group_files) in enumerate(grouped_sorted, start=1):
            label = sanitize_label(top_folder)
            print("=" * 70)
            print(f"REQUERIMIENTO [{idx}/{total}]: {label}")
            print("=" * 70)
            print(f"📁 Documentos: {len(group_files)}")
            for p in group_files:
                print(f"   - {p.relative_to(args.requirements_folder)}")
            print()

            success = process_single_requirement(args, label, group_files)
            if success:
                ok_count += 1

        print("=" * 60)
        print(f"✅ Procesamiento finalizado: {ok_count}/{total} requerimientos exitosos.")
        print("=" * 60)


if __name__ == "__main__":
    main()
