#!/usr/bin/env python3
"""
Pipeline completo: Requerimientos → JSON → Casos de Prueba

Cadena unificada que:
  1. Lee subcarpetas de requerimientos/ (PDF, PPTX, DOCX, etc.)
  2. Extrae texto y genera JSON estructurado + reporte Markdown
  3. Alimenta el JSON al sistema multi-agente (Maestro → Agente 1 → Agente 2)
  4. Exporta casos de prueba a CSV y Excel incrementalmente

Uso:
    python pipeline.py
    python pipeline.py --requirements-folder ruta/a/docs --max-casos 10
    python pipeline.py --force --use-ocr
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Agregar directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from main import (
    find_requirement_docs,
    group_files_by_top_folder,
    sanitize_label,
    infer_requirement_label,
    print_folder_summary,
    REQUIREMENT_EXTENSIONS,
)
from process_requirements import (
    process_requirements_folder,
    get_latest_processed_requirements,
    is_valid_processed_requirements,
    build_fallback_requirements_from_txt,
)
from knowledge_loader import load_all
from agente_maestro import AgenteMaestro
from llm_client import get_llm_client, cleanup


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pipeline completo: Requerimientos → JSON → Casos de Prueba",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Procesar todos los requerimientos y generar casos
  python pipeline.py

  # Limitar a 5 casos por requerimiento
  python pipeline.py --max-casos 5

  # Forzar reprocesamiento de documentos
  python pipeline.py --force

  # Usar OCR para PDFs escaneados
  python pipeline.py --use-ocr
        """
    )

    # Entrada / Salida
    parser.add_argument(
        "--requirements-folder", "-rf",
        type=Path,
        default=Path("requerimientos"),
        help="Carpeta con subcarpetas de requerimientos (default: requerimientos/)"
    )
    parser.add_argument(
        "--json-folder",
        type=Path,
        default=Path("json"),
        help="Carpeta para JSONs intermedios (default: json/)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("output"),
        help="Carpeta para output final CSV/Excel (default: output/)"
    )

    # Casos de prueba
    parser.add_argument(
        "--max-casos",
        type=int,
        default=None,
        help="Máximo de casos de prueba por requerimiento (default: 20)"
    )
    parser.add_argument(
        "--datos-dir",
        type=Path,
        default=None,
        help="Directorio de datos del KnowledgeBase (default: ./Datos)"
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
        choices=["auto", "tesseract", "nanonets", "llm"],
        help="Proveedor OCR (llm usa modelo de visión local de Ollama)"
    )
    parser.add_argument(
        "--pdf-method",
        type=str,
        default="auto",
        choices=["auto", "pypdf2", "pdfplumber", "ocr"],
        help="Método de extracción de PDF"
    )
    parser.add_argument(
        "--nanonets-api-key", type=str, default=None,
    )
    parser.add_argument(
        "--nanonets-model-id", type=str, default=None,
    )

    # Control
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forzar reprocesamiento de documentos aunque ya exista JSON"
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Saltar fase de procesamiento de documentos (usar JSONs existentes)"
    )
    parser.add_argument(
        "--skip-agents",
        action="store_true",
        help="Saltar fase de generación de casos (solo procesar documentos)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Modo verbose"
    )

    return parser.parse_args()


# ── Fase 1: Procesamiento de documentos ──────────────────────────────────────

def process_documents(args, label: str, files: list[Path]) -> Path | None:
    """
    Procesa documentos y retorna la ruta al JSON generado.
    Retorna None si falla.
    """
    json_folder = args.json_folder / label
    json_folder.mkdir(parents=True, exist_ok=True)

    # Verificar si ya existe uno válido
    existing = get_latest_processed_requirements(json_folder)
    if existing and not args.force:
        print(f"  ℹ️  JSON existente: {existing.name}")
        print(f"  ℹ️  Usa --force para reprocesar.")
        return existing

    # Crear args-like para process_requirements_folder
    try:
        merged_data, report_path, json_path = process_requirements_folder(
            requirements_folder=args.requirements_folder,
            output_folder=json_folder,
            use_ocr=args.use_ocr,
            pdf_method=args.pdf_method,
            input_files=files,
            ocr_provider=args.ocr_provider,
            nanonets_api_key=args.nanonets_api_key,
            nanonets_model_id=args.nanonets_model_id,
        )

        if is_valid_processed_requirements(merged_data):
            print(f"  ✅ JSON generado: {json_path.name}")
            print(f"  📝 Reporte: {report_path.name}")
            return json_path
        else:
            print(f"  ⚠️ JSON vacío, intentando fallback desde TXT...")
            # Intentar fallback desde archivos .txt
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
                        print(f"  ✅ Fallback JSON generado: {fallback_path.name}")
                        return fallback_path

            if existing:
                print(f"  ℹ️  Se conserva JSON previo: {existing.name}")
                return existing
            return None

    except Exception as e:
        print(f"  ❌ Error procesando documentos: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return existing


# ── Fase 2: Generación de casos de prueba ────────────────────────────────────

def generate_test_cases(
    json_path: Path,
    label: str,
    output_dir: Path,
    kb,
    llm,
    max_casos: int = None,
) -> int:
    """
    Genera casos de prueba desde un JSON de requerimiento.
    Retorna la cantidad de casos generados.
    """
    # Leer JSON
    with open(json_path, encoding="utf-8") as f:
        json_req = json.load(f)

    # Crear directorio de output
    case_output = output_dir / label
    case_output.mkdir(parents=True, exist_ok=True)

    # Ejecutar sistema multi-agente
    maestro = AgenteMaestro(kb, llm)
    casos = maestro.ejecutar(json_req, max_casos=max_casos, output_dir=case_output)

    if not casos:
        print(f"  ⚠️ No se generaron casos de prueba.")
        return 0

    # Guardar resumen
    resumen = maestro.get_resumen()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    resumen_path = case_output / f"resumen_{ts}.md"
    with open(resumen_path, "w", encoding="utf-8") as f:
        f.write(resumen)
    print(f"  📝 Resumen: {resumen_path.name}")

    return len(casos)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    base_dir = Path(__file__).parent

    print("=" * 70)
    print("🚀 PIPELINE COMPLETO: REQUERIMIENTOS → JSON → CASOS DE PRUEBA")
    print("=" * 70)
    print()
    print("📋 Configuración:")
    print(f"   Carpeta docs:     {args.requirements_folder}")
    print(f"   JSON intermedio:  {args.json_folder}")
    print(f"   Output final:     {args.output}")
    print(f"   Max casos:        {args.max_casos or 'sin límite (default 20)'}")
    print(f"   Skip docs:        {'Sí' if args.skip_docs else 'No'}")
    print(f"   Skip agents:      {'Sí' if args.skip_agents else 'No'}")
    print()

    # ── Paso 0: Preparar recursos compartidos ──
    datos_dir = args.datos_dir or base_dir / "Datos"

    if not args.skip_agents:
        kb = load_all(datos_dir)
        print()

        print("🔗 Conectando a LLM...")
        llm = get_llm_client()
        if not llm.check_connection():
            print("❌ No se pudo conectar al servidor LLM.")
            print("   Asegúrate de que Ollama está corriendo.")
            sys.exit(1)
        print(f"✅ LLM conectado: {llm.base_url} (modelo: {llm.model})")
        print()
    else:
        kb = None
        llm = None

    # ── Paso 1: Buscar documentos ──
    all_docs = find_requirement_docs(args.requirements_folder)
    if not all_docs and not args.skip_docs:
        print(f"❌ No se encontraron documentos en: {args.requirements_folder}")
        sys.exit(1)

    # Agrupar por subcarpeta
    grouped = group_files_by_top_folder(args.requirements_folder, all_docs)
    if not grouped and not args.skip_docs:
        print("❌ No se encontraron subcarpetas con documentos.")
        sys.exit(1)

    # Si skip_docs, buscar JSONs existentes
    if args.skip_docs:
        grouped = {}
        if args.json_folder.exists():
            for sub in sorted(args.json_folder.iterdir()):
                if sub.is_dir():
                    existing = get_latest_processed_requirements(sub)
                    if existing:
                        grouped[sub.name] = existing
        if not grouped:
            print(f"❌ No se encontraron JSONs procesados en: {args.json_folder}")
            sys.exit(1)
        print(f"📂 Encontrados {len(grouped)} requerimiento(s) con JSON existente.")
    else:
        print(f"📂 Encontrados {len(all_docs)} documento(s) en {len(grouped)} requerimiento(s)")
        print_folder_summary(args.requirements_folder, all_docs)

    # ── Paso 2: Procesar cada requerimiento ──
    total_reqs = len(grouped)
    resultados = []

    try:
        for idx, (folder_key, data) in enumerate(sorted(grouped.items()), start=1):
            label = sanitize_label(folder_key)

            print("=" * 70)
            print(f"📁 REQUERIMIENTO [{idx}/{total_reqs}]: {label}")
            print("=" * 70)

            # ── Fase 1: Procesamiento de documentos ──
            if args.skip_docs:
                # data ya es la ruta al JSON
                json_path = data
                print(f"  📄 JSON existente: {json_path.name}")
            else:
                files = data  # data es la lista de archivos
                print(f"  📝 Documentos: {len(files)}")

                print("\n  ── FASE 1: Extracción de texto y JSON ──")
                json_path = process_documents(args, label, files)

                if not json_path:
                    print(f"  ❌ No se pudo generar JSON. Saltando a siguiente.")
                    resultados.append((label, "❌ Sin JSON", 0))
                    continue

            # ── Fase 2: Generación de casos de prueba ──
            if args.skip_agents:
                print(f"  ⏭️  Saltando generación de casos (--skip-agents)")
                resultados.append((label, "✅ Solo JSON", 0))
                continue

            print(f"\n  ── FASE 2: Generación de casos de prueba ──")
            print(f"  📄 Usando JSON: {json_path.name}")

            n_casos = generate_test_cases(
                json_path=json_path,
                label=label,
                output_dir=args.output,
                kb=kb,
                llm=llm,
                max_casos=args.max_casos,
            )

            status = f"✅ {n_casos} casos" if n_casos > 0 else "⚠️ Sin casos"
            resultados.append((label, status, n_casos))
            print()

    except KeyboardInterrupt:
        print("\n\n⚡ Proceso interrumpido por el usuario.")
        print("   Los casos generados hasta ahora se guardaron incrementalmente.")
    finally:
        if llm:
            cleanup()

    # ── Paso 3: Resumen final ──
    print()
    print("=" * 70)
    print("🎉 PIPELINE COMPLETADO")
    print("=" * 70)
    total_casos = sum(r[2] for r in resultados)
    print(f"  📊 Requerimientos procesados: {len(resultados)}/{total_reqs}")
    print(f"  📊 Total casos generados:     {total_casos}")
    print()
    for label, status, n in resultados:
        print(f"  {status}  {label}")
    print()
    print(f"  📂 JSONs en:  {args.json_folder}/")
    print(f"  📂 Output en: {args.output}/")
    print("=" * 70)


if __name__ == "__main__":
    main()
