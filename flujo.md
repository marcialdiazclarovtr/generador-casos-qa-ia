# Flujo del Sistema Multi-Agente QA

Documento técnico que describe cómo funciona internamente el pipeline completo.

---

## Diagrama General

```
┌──────────────────────────────────────────────────────────────────────┐
│                         pipeline.py                                  │
│                                                                      │
│  ┌─────────────────────────┐     ┌────────────────────────────────┐  │
│  │    FASE 1: Documentos   │     │     FASE 2: Casos de Prueba   │  │
│  │    ─────────────────    │     │     ───────────────────────    │  │
│  │                         │     │                                │  │
│  │  requerimientos/        │     │  Agente Maestro (planifica)    │  │
│  │    └─ GDI-XXXX/         │     │    │                           │  │
│  │        ├─ pdf            │     │    ├── Agente 1 (cabecera)    │  │
│  │        ├─ pptx          │     │    │     ✓ valida              │  │
│  │        └─ docx          │     │    │                           │  │
│  │                         │     │    ├── Agente 2 (detalle)     │  │
│  │  pdf_processor.py       │     │    │     ✓ valida              │  │
│  │    → texto extraído     │     │    │                           │  │
│  │                         │     │    └── 💾 CSV + Excel          │  │
│  │  requirement_extractor  │     │         (incremental)          │  │
│  │    → JSON estructurado  │     │                                │  │
│  │                         │     │                                │  │
│  └─────────────────────────┘     └────────────────────────────────┘  │
│                                                                      │
│           json/<req>/                    output/<req>/                │
│           ├─ txt/*.txt                   ├─ casos_prueba.csv         │
│           ├─ merged_*.json               ├─ casos_prueba.xlsx        │
│           └─ reporte_*.md                └─ resumen_*.md             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Fase 1: Procesamiento de Documentos

**Script:** `main.py` | **Módulos:** `pdf_processor.py`, `requirement_extractor.py`, `process_requirements.py`

### Paso a paso

1. **Buscar documentos** en `requerimientos/` (PDF, PPTX, DOCX, XLSX, imágenes, texto)
2. **Agrupar por subcarpeta** — cada subcarpeta es un requerimiento independiente
3. **Extraer texto** de cada documento:
   - PDF → PyPDF2 o pdfplumber (auto-detecta cuál funciona mejor)
   - PPTX → python-pptx (extrae texto de cada slide)
   - DOCX → python-docx (extrae párrafos y tablas)
   - Imágenes → OCR con Tesseract o Nanonets (si `--use-ocr`)
4. **Guardar textos** en `json/<req>/txt/<nombre_doc>.txt`
5. **Extracción estructurada con LLM** — el modelo analiza los textos y extrae:
   - `contexto`: descripción general del requerimiento
   - `que_piden`: qué funcionalidad se solicita
   - `solucion`: propuesta técnica
   - `impacto_sistemas_bd`: sistemas y bases de datos afectados
   - `flujo`: pasos del proceso de negocio
   - `casos_prueba`: sugerencias de prueba
6. **Merge y export** → `merged_*.json` + `reporte_*.md`

### Fallback sin LLM

Si el LLM falla, se genera un JSON mínimo útil usando análisis de texto directo (`build_fallback_requirements_from_txt`).

---

## Fase 2: Generación de Casos de Prueba

**Script:** `run_agents.py` | **Módulos:** `agente_maestro.py`, `agente1_campos.py`, `agente2_detalle.py`

### Base de Conocimiento

Antes de generar, se carga el `KnowledgeBase` desde `Datos/`:

| Fuente | Archivo | Contenido |
|--------|---------|-----------|
| Diccionario | `dic/NUEVO_DICCIONARIO 3.csv` | Campos, tipos, valores permitidos |
| Mantis Claro | `mantis/...Claro.csv` | 33 casos de ejemplo (few-shot) |
| Mantis VTR | `mantis/...VTR.csv` | 69 casos de ejemplo (few-shot) |
| Matrices | `matriz/matrices_estructuradas_limpias.txt` | Reglas de combinación válidas |
| Siebel | `siebel/siebel.md` | Mapa de plataformas (Mermaid) |

### Agente Maestro (`agente_maestro.py`)

1. **Planificación** — LLM analiza el JSON del requerimiento y genera combinaciones:
   ```
   {proceso: "Servicio Técnico", tecnologia: "HFC", marca: "Claro"}
   {proceso: "Cancelación", tecnologia: "FTTH", marca: "VTR"}
   ...
   ```
   - Si el LLM falla → fallback determinístico por keywords
   - Intenta con `response_format: json_object`, luego sin él

2. **Ciclo por combinación:**
   ```
   Para cada combinación:
     ├── Agente 1 genera cabecera
     │     ├── Validación determinística (valores permitidos, campos vacíos)
     │     └── Hasta 3 reintentos con feedback de errores
     │
     ├── Agente 2 genera detalle (recibe la cabecera validada)
     │     ├── Validación determinística (estructura, plataformas Siebel)
     │     ├── Validación LLM (coherencia cabecera↔detalle)
     │     └── Hasta 3 reintentos con feedback de errores
     │
     └── 💾 Guardar CSV + Excel (incremental, sobrevive crashes)
   ```

### Agente 1: Campos de Cabecera (`agente1_campos.py`)

Genera 9 campos usando el contexto completo:

| Campo | Tipo | Ejemplo |
|-------|------|---------|
| Tipo de Prueba | Lista | Proyecto (Funcional) |
| Prioridad | Número | 1 |
| Marca | Lista | Claro |
| Segmento | Lista | B2C Residencial |
| Tecnología | Lista | HFC |
| Proceso | Lista | Servicio Técnico |
| Sub Proceso | Lista | Reparación |
| Servicios | Texto libre | Reclamos HFC |
| Descripción | Texto largo | Validar inyección de solicitud... |

**Contexto que recibe:** JSON del requerimiento + diccionario de campos + ejemplos Mantis + matrices + mapa Siebel.

### Agente 2: Campos de Detalle (`agente2_detalle.py`)

Genera 4 campos manteniendo coherencia con la cabecera del Agente 1:

| Campo | Formato | Ejemplo |
|-------|---------|---------|
| Precondiciones | Texto | Cliente con servicio activo... |
| Paso a Paso | Estructura I. → 1. → a. | I. Acceso a SV\n1. Login... |
| Resultado Esperado | Lista con * | *Solicitud creada en Siebel... |
| Datos de Prueba | Texto | RUT: 12.345.678-9 |

**Contexto que recibe:** Todo lo de Agente 1 + la cabecera ya validada.

---

## Robustez del LLM

El modelo `gpt-oss:20b` es un modelo de razonamiento que a veces envuelve su respuesta en tags `<think>`. El sistema maneja esto con:

1. **`JSONExtractor`** en `llm_client.py` — limpia `<think>`, `<reasoning>`, markdown fences, comillas Unicode
2. **`response_format: json_object`** — primer intento con modo JSON forzado
3. **Fallback sin `response_format`** — segundo intento si el servidor no lo soporta
4. **Fallback determinístico** — para la planificación, si ambos intentos fallan
5. **Logging de respuestas raw** — para debugging cuando el parsing falla

---

## Guardado Incremental

Los archivos CSV y Excel se sobrescriben después de **cada caso validado**. Si el proceso se interrumpe (Ctrl+C, crash, timeout), no se pierde lo generado. Los archivos siempre están en:

```
output/<requerimiento>/
├── casos_prueba.csv        ← siempre actualizado
├── casos_prueba.xlsx       ← siempre actualizado
└── resumen_<timestamp>.md  ← al finalizar
```
