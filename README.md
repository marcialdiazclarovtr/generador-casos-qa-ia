# Sistema Multi-Agente QA - Generación de Casos de Prueba

Sistema automático que procesa documentos de requerimientos y genera casos de prueba QA usando un pipeline de 3 agentes LLM.

## Flujo Completo

```
requerimientos/              json/<req>/                   output/<req>/
  └─ GDI-1858/      →        ├─ txt/*.txt          →       ├─ casos_prueba.csv
      ├─ doc1.pdf             ├─ merged_*.json              ├─ casos_prueba.xlsx
      ├─ doc2.pptx            └─ reporte_*.md               └─ resumen_*.md
      └─ doc3.docx
   (Documentos)            (Extracción)                  (Casos de Prueba)
```

## Estructura del Proyecto

```text
Flujo_nuevo/
├── pipeline.py               ← 🚀 PUNTO DE ENTRADA PRINCIPAL (flujo completo)
├── main.py                   ← Fase 1: procesamiento de documentos → JSON
├── run_agents.py             ← Fase 2: generación de casos desde JSON existente
│
├── agente_maestro.py         ← Orquestador: planifica, valida, ensambla casos
├── agente1_campos.py         ← Agente 1: genera cabecera (9 campos)
├── agente2_detalle.py        ← Agente 2: genera detalle (4 campos)
│
├── config.py                 ← Configuración central (Ollama, temperaturas)
├── llm_client.py             ← Cliente LLM con JSON extraction robusto
├── knowledge_loader.py       ← Carga diccionario, mantis, matrices, siebel
├── pdf_processor.py          ← Conversión de documentos a texto
├── requirement_extractor.py  ← Extracción estructurada con LLM
├── process_requirements.py   ← Integrador: conversión → extracción → merge
│
├── Datos/                    ← Base de conocimiento QA
│   ├── dic/                  ← Diccionario de campos
│   ├── mantis/               ← Casos de ejemplo Claro + VTR
│   ├── matriz/               ← Reglas de combinación válidas
│   └── siebel/               ← Mapa de plataformas Siebel (Mermaid)
│
├── requerimientos/           ← Documentos de entrada (subcarpeta por req)
├── json/                     ← JSONs intermedios generados
├── output/                   ← Casos de prueba finales (CSV + Excel)
└── requirements.txt          ← Dependencias Python
```

## Requisitos

1. **Python 3.10+**
2. **Ollama** corriendo localmente con el modelo `gpt-oss:20b`:
```bash
ollama pull gpt-oss:20b
curl http://127.0.0.1:11434/v1/models
```
3. **Dependencias Python:**
```bash
pip install -r requirements.txt
```

## Ejecución

### Pipeline completo (recomendado)

```bash
# Procesar documentos Y generar casos de prueba
python pipeline.py

# Limitar cantidad de casos por requerimiento
python pipeline.py --max-casos 5

# Forzar reprocesamiento de documentos
python pipeline.py --force

# Con OCR para PDFs escaneados
python pipeline.py --use-ocr

# Saltar fase de documentos (usar JSONs existentes)
python pipeline.py --skip-docs --max-casos 3

# Solo procesar documentos (sin generar casos)
python pipeline.py --skip-agents
```

### Ejecución por fases (individual)

```bash
# Solo Fase 1: documentos → JSON
python main.py

# Solo Fase 2: JSON → casos de prueba
python run_agents.py --json json/<req>/merged_*.json --max-casos 5
```

## Argumentos del Pipeline

| Argumento | Default | Descripción |
|-----------|---------|-------------|
| `--requirements-folder` | `requerimientos/` | Carpeta con documentos |
| `--json-folder` | `json/` | Carpeta para JSONs intermedios |
| `--output` | `output/` | Carpeta para CSV/Excel de salida |
| `--max-casos` | `20` | Máximo de casos por requerimiento |
| `--skip-docs` | off | Saltar fase de documentos |
| `--skip-agents` | off | Saltar fase de generación de casos |
| `--force` | off | Forzar reproceso de documentos |
| `--use-ocr` | off | Activar OCR |
| `--pdf-method` | auto | pypdf2 / pdfplumber / ocr / auto |
| `--verbose` | off | Modo detallado |

## Columnas del CSV de Salida

| # | Columna | Agente | Descripción |
|---|---------|--------|-------------|
| 1 | ID | Auto | Identificador secuencial |
| 2 | Tipo de Prueba | A1 | Regresiva, Proyecto (Funcional), etc. |
| 3 | Prioridad | A1 | 1 (Alta), 2 (Media), 3 (Baja) |
| 4 | Marca | A1 | Claro o VTR |
| 5 | Segmento | A1 | B2C Residencial, B2B, etc. |
| 6 | Tecnología | A1 | HFC, FTTH, NEUTRA, etc. |
| 7 | Proceso | A1 | Venta, Cancelación, Servicio Técnico, etc. |
| 8 | Sub Proceso | A1 | Reparación, Desconexión, Upgrade, etc. |
| 9 | Servicios | A1 | Servicios impactados |
| 10 | Precondiciones | A2 | Estado del sistema antes de ejecutar |
| 11 | Descripción | A1 | Objetivo del caso de prueba |
| 12 | Paso a Paso | A2 | Pasos detallados (I. → 1. → a.) |
| 13 | Resultado Esperado | A2 | Validaciones esperadas |
| 14 | Datos de Prueba | A2 | RUT, cuenta, etc. |

## Multi-Requerimiento

Si hay múltiples subcarpetas en `requerimientos/`, el pipeline procesa cada una de forma independiente y genera salidas separadas.
