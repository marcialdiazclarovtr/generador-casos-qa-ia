#!/usr/bin/env python3
"""
Ejecuta el sistema multi-agente para generar casos de prueba QA.

Uso:
    python run_agents.py --json path/to/merged.json
    python run_agents.py --json path/to/merged.json --max-casos 5
    python run_agents.py --json path/to/merged.json --output output/mi_test/

Flujo:
    1. Carga KnowledgeBase (dic, mantis, matriz, siebel)
    2. Lee el JSON del requerimiento
    3. Agente Maestro planifica combinaciones
    4. Para cada combinación: Agente 1 → valida → Agente 2 → valida
    5. Exporta casos validados a CSV formato Mantis
"""
import argparse
import json
import sys
import glob
from pathlib import Path
from datetime import datetime

from knowledge_loader import load_all
from agente_maestro import AgenteMaestro
from llm_client import get_llm_client, cleanup


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sistema multi-agente para generación de casos de prueba QA"
    )
    parser.add_argument(
        "--json",
        type=str,
        required=False,
        help="Ruta al JSON del requerimiento (merged_*.json). "
             "Si no se especifica, busca el más reciente en json/.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output",
        help="Carpeta de salida (default: output/)",
    )
    parser.add_argument(
        "--max-casos",
        type=int,
        default=None,
        help="Límite de casos a generar (default: 20)",
    )
    parser.add_argument(
        "--datos-dir",
        type=str,
        default=None,
        help="Directorio de datos (default: ./Datos)",
    )
    return parser.parse_args()


def find_latest_json(json_dir: Path) -> Path | None:
    """Busca el JSON más reciente en el directorio json/."""
    pattern = str(json_dir / "**" / "merged_*.json")
    archivos = glob.glob(pattern, recursive=True)
    if not archivos:
        return None
    # Ordenar por fecha de modificación (más reciente primero)
    archivos.sort(key=lambda f: Path(f).stat().st_mtime, reverse=True)
    return Path(archivos[0])


def main():
    args = parse_args()
    base_dir = Path(__file__).parent

    print("=" * 60)
    print("🤖 Sistema Multi-Agente QA — Generador de Casos de Prueba")
    print("=" * 60)

    # ── 1. Cargar KnowledgeBase ──
    datos_dir = Path(args.datos_dir) if args.datos_dir else base_dir / "Datos"
    kb = load_all(datos_dir)

    # ── 2. Cargar JSON del requerimiento ──
    if args.json:
        json_path = Path(args.json)
    else:
        json_dir = base_dir / "json"
        json_path = find_latest_json(json_dir)
        if not json_path:
            print("❌ No se encontró ningún JSON de requerimiento.")
            print(f"   Busqué en: {json_dir}")
            print("   Usa --json para especificar la ruta.")
            sys.exit(1)

    if not json_path.exists():
        print(f"❌ Archivo no encontrado: {json_path}")
        sys.exit(1)

    print(f"\n📄 JSON del requerimiento: {json_path.name}")
    print(f"   Ruta: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        json_req = json.load(f)

    # ── 3. Preparar salida ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Usar el nombre del directorio padre del JSON como nombre del output
    req_name = json_path.parent.name if json_path.parent.name != "json" else json_path.stem
    output_dir = Path(args.output) / req_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 4. Ejecutar sistema multi-agente ──
    try:
        llm = get_llm_client()
        print(f"\n🔗 Conectando a LLM: {llm.base_url} (modelo: {llm.model})")

        if not llm.check_connection():
            print("❌ No se pudo conectar al servidor LLM.")
            print("   Asegúrate de que Ollama está corriendo.")
            sys.exit(1)

        print("✅ Conexión LLM establecida\n")

        maestro = AgenteMaestro(kb, llm)
        casos = maestro.ejecutar(json_req, max_casos=args.max_casos, output_dir=output_dir)

        if not casos:
            print("\n⚠️ No se generaron casos de prueba.")
            sys.exit(0)

        # ── 5. Guardar resumen ──
        resumen = maestro.get_resumen()
        resumen_path = output_dir / f"resumen_{timestamp}.md"
        with open(resumen_path, "w", encoding="utf-8") as f:
            f.write(resumen)
        print(f"📝 Resumen guardado: {resumen_path}")

        # Resumen final
        print(f"\n{'='*60}")
        print(f"🎉 PROCESO COMPLETADO")
        print(f"{'='*60}")
        print(f"  📊 Casos generados: {len(casos)}")
        print(f"  📄 CSV:    {output_dir / 'casos_prueba.csv'}")
        print(f"  📊 Excel:  {output_dir / 'casos_prueba.xlsx'}")
        print(f"  📝 Resumen: {resumen_path}")
        print(f"{'='*60}")

    except KeyboardInterrupt:
        print("\n\n⚡ Proceso interrumpido por el usuario.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cleanup()


if __name__ == "__main__":
    main()
