# Memory — Proyecto QA Multi-Agente (Flujo_nuevo)

Historial de todo lo construido para referencia futura si se supera el límite de tokens.

---

## 1. Estructura del Proyecto

```
Flujo_nuevo/
├── pipeline.py               ← Punto de entrada unificado (docs → JSON → casos)
├── main.py                   ← Solo fase doc processing
├── run_agents.py             ← Solo fase generación de casos
│
├── agente_maestro.py         ← Orquestador: planifica combos, valida, ensambla
├── agente1_campos.py         ← Genera 9 campos de cabecera
├── agente2_detalle.py        ← Genera 4 campos de detalle
│
├── config.py                 ← Config central (URLs, temperaturas, max tokens)
├── llm_client.py             ← Cliente LLM con JSONExtractor robusto
├── knowledge_loader.py       ← Carga dic/mantis/matrices/siebel → KnowledgeBase
├── pdf_processor.py          ← PDF/PPTX/DOCX/XLSX → texto
├── requirement_extractor.py  ← Extracción estructurada con LLM
├── process_requirements.py   ← Integrador: doc → txt → JSON → reporte
│
├── backend/                  ← FastAPI (del proyecto anterior, pendiente adaptar)
│   ├── app.py                ← FastAPI + CORS + router
│   ├── pipeline.py           ← Adapter viejo (import generator → HAY QUE REESCRIBIR)
│   ├── api/endpoints.py      ← /upload, /generate, /status, /files
│   └── schemas/request.py    ← Pydantic GenerateRequest
│
├── frontend/                 ← Vite + React + Tailwind (del proyecto anterior)
│   ├── src/App.jsx           ← Layout principal 2 columnas
│   ├── src/components/
│   │   ├── UploadArea.jsx    ← Drag & drop de documentos
│   │   ├── ProgressBar.jsx   ← Steps + log en tiempo real
│   │   ├── ResultsDisplay.jsx← Lista archivos generados
│   │   └── ConfigurationForm.jsx ← Form de config (no usado en App.jsx)
│   └── src/api/client.js     ← Axios: upload, generate, status, files
│
├── Datos/                    ← Base de conocimiento QA
│   ├── dic/                  ← Diccionario de campos (CSV)
│   ├── mantis/               ← Casos ejemplo Claro (33) + VTR (69)
│   ├── matriz/               ← Reglas de combinación
│   └── siebel/               ← Mapa plataformas (Mermaid)
│
├── requerimientos/           ← Documentos de entrada
├── json/                     ← JSONs intermedios
└── output/                   ← CSV + Excel de salida
```

## 2. Columnas CSV (14 columnas del diccionario)

| # | Columna | Agente |
|---|---------|--------|
| 1 | ID | Auto |
| 2 | Tipo de Prueba | A1 |
| 3 | Prioridad | A1 |
| 4 | Marca | A1 |
| 5 | Segmento | A1 |
| 6 | Tecnología | A1 |
| 7 | Proceso | A1 |
| 8 | Sub Proceso | A1 |
| 9 | Servicios | A1 |
| 10 | Precondiciones | A2 |
| 11 | Descripción | A1 |
| 12 | Paso a Paso | A2 |
| 13 | Resultado Esperado | A2 |
| 14 | Datos de Prueba | A2 |

## 3. Flujo Multi-Agente

```
JSON req → Agente Maestro planifica combinaciones (proceso/tecnología/marca)
         → Para cada combo:
              Agente 1 genera cabecera (9 campos) → validación determinística
              Agente 2 genera detalle (4 campos) → validación determinística + LLM
              → Ensambla caso → Guarda incremental (CSV + Excel)
```

## 4. Decisiones Técnicas Importantes

- **LLM:** Ollama `gpt-oss:20b` en `http://127.0.0.1:11434/v1`
- **JSONExtractor** strip `<think>` y `<reasoning>` tags para modelos reasoning
- **response_format:** Intenta primero con `{"type": "json_object"}`, fallback sin él
- **Fallback determinístico:** Si LLM falla en planificación, infiere por keywords
- **CSV:** Usa `csv.QUOTE_ALL`, coma como delimitador, `utf-8-sig` (BOM para Excel)
- **Newlines en CSV:** Reemplazados por `\n` literal para que cada caso = 1 fila
- **Excel:** Mantiene newlines reales (openpyxl)
- **Guardado incremental:** Después de cada caso validado, sobrevive Ctrl+C

## 5. Cambios Realizados (sesión actual)

1. **Columnas CSV:** Cambiado de 19 columnas Mantis a 14 columnas del diccionario
2. **Agente 1:** Reescrito para generar 9 campos de cabecera con valores del diccionario
3. **Agente 2:** Reescrito para generar 4 campos de detalle
4. **Agente Maestro:** Cambiado "flujo" → "proceso" en planificación y combos
5. **CSV fix:** QUOTE_ALL + newlines como `\n` literal + coma delimiter + utf-8-sig
6. **get_resumen:** Fix KeyError — usa nuevos nombres de columnas
7. **run_agents.py:** Eliminados exports duplicados (solo incremental + resumen)
8. **pipeline.py:** Nuevo — encadena main.py + run_agents.py en un solo comando
9. **README.md / flujo.md:** Actualizados con la nueva estructura

## 6. Pendiente: Adaptar Frontend/Backend

### Backend (`backend/pipeline.py`)
- El viejo importa `from generator import generate_test_cases` que NO EXISTE
- Hay que reescribirlo para usar el nuevo flujo: `knowledge_loader.load_all()` + `AgenteMaestro`
- `_StatusCapture` (intercepta stdout) funciona bien, se puede reusar
- `GenerateRequest` schema necesita quitar `num_regresivas`/`functional_only`, agregar `max_casos`

### Frontend
- `ProgressBar.jsx` tiene keywords para detectar steps — actualizar para nuevo flujo
- `App.jsx` muestra slider "Casos Regresivos (Fijo)" — quitar
- Config card muestra valores viejos — actualizar
- Agregar panel/sección para mostrar razonamientos de los agentes
- `/api/files` necesita listar archivos de `output/<session>/` no solo `output/`

### Arquitectura que funciona bien
- Upload → session subfolder en `requerimientos/`
- Background task con `run_pipeline()`
- `status.json` polling cada 2s
- `_StatusCapture` → captura prints → los envía como status messages
- Frontend `ProgressBar` con log en tiempo real

## 7. Frontend/Backend Adaptados (sesión actual)

### Backend (cambios realizados)
1. **`backend/pipeline.py`** — Reescrito completamente:
   - Importa `AgenteMaestro`, `load_all`, `get_llm_client` (en vez de viejo `generator`)
   - `process_docs_only()` — Solo Fase 1, retorna JSON para Agente 0
   - `enhance_json_with_llm()` — Agente 0: LLM mejora el JSON con prompt especializado
   - `run_pipeline()` — Flujo completo con soporte para `json_data` editado
   - `_StatusCapture` mantenido para captura de prints en tiempo real

2. **`backend/schemas/request.py`** — Simplificado:
   - Eliminados: `marcas`, `tecnologias`, `num_cases`, `num_regresivas`, `functional_only`, `provider`
   - Agregados: `max_casos` (int, default 20)
   - Nuevo: `EnhanceJsonRequest` (json_data, instructions, session_folder)

3. **`backend/api/endpoints.py`** — Nuevos endpoints:
   - `VALID_EXTENSIONS` incluye imágenes (.png, .jpg, .jpeg, .bmp, .tif, .webp, .txt, .md)
   - `POST /api/process-docs` → Solo fase 1 (docs → JSON) para revisión
   - `POST /api/enhance-json` → Agente 0 mejora JSON con LLM
   - `GET /api/files?session=X` → Filtra archivos por sesión

### Frontend (cambios realizados)
1. **`UploadArea.jsx`** — Extensiones de imagen + texto añadidas
2. **`JsonReviewPanel.jsx`** — NUEVO componente:
   - Secciones colapsables (contexto, que_piden, solución, impacto, flujo, etc.)
   - Cada sección editable con textarea
   - Botón "Mejorar con IA" → POST /enhance-json
   - Botón "Continuar con Generación" → lanza paso 3
3. **`App.jsx`** — Reescrito con flujo de 3 pasos:
   - Paso 1: Upload → "Procesar y Analizar"
   - Paso 2: JsonReviewPanel (Agente 0)
   - Paso 3: Generación con ProgressBar
   - Sidebar con indicador de paso + config activa
   - Botón "← Nuevo proceso" para resetear
4. **`ProgressBar.jsx`** — Keywords actualizadas para nuevo flujo:
   - Mensajes💭razonamiento en purple
   - Casos 🎯 en green
   - Log más alto (h-48)
5. **`client.js`** — Nuevas funciones: `processDocs()`, `enhanceJson()`, `getFiles(session)`
