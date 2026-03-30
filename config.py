"""
Configuración central del sistema de generación de casos de prueba con RAG.
Optimizado para uso de memoria eficiente.
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class LMStudioConfig:
    """Configuración del endpoint LLM (adaptado para Ollama)."""
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = "qwen3.5:9b"
    embedding_model: str = "nomic-embed-text:latest"
    reranker_model: str = ""
    temperature: float = 0.1
    max_tokens: int = 1500
    timeout: int = 300

@dataclass
class RAGConfig:
    """Configuración del sistema RAG"""
    chunk_size: int = 180
    chunk_overlap: int = 30
    top_k_retrieval: int = 10
    top_k_rerank: int = 5
    similarity_threshold: float = 0.3
    batch_size: int = 5  # Para procesar casos en lotes y evitar OOM

@dataclass
class PathConfig:
    """Rutas de archivos"""
    base_dir: Path = field(default_factory=lambda: Path("."))
    json_requerimientos: Optional[Path] = None
    mantis_claro: Optional[Path] = None
    mantis_vtr: Optional[Path] = None
    diccionario: Optional[Path] = None
    matrices: Optional[Path] = None
    output_dir: Path = field(default_factory=lambda: Path("output"))
    chroma_dir: Path = field(default_factory=lambda: Path("chroma_db"))
    
    def __post_init__(self):
        self.output_dir.mkdir(exist_ok=True)
        self.chroma_dir.mkdir(exist_ok=True)

@dataclass
class TestCaseTemplate:
    """Plantilla para casos de prueba estilo Mantis"""
    required_fields: tuple = (
        "ID",
        "Tipo de Prueba",
        "Prioridad",
        "Marca",
        "Segmento",
        "Tecnología",
        "Proceso",
        "Sub Proceso",
        "Servicios",
        "Precondiciones",
        "Descripción",
        "Flujo General",
        "Paso a Paso",
        "Resultado Esperado",
        "Datos de Prueba"
    )
    
    tipos_prueba: tuple = (
        "Regresiva",
        "Proyecto (Funcional)",
        "Proyecto (Integración)",
        "Smoke Test"
    )
    
    prioridades: tuple = (1, 2, 3)
    
    marcas: tuple = ("CLARO", "VTR")
    
    tecnologias: tuple = ("FTTH", "HFC", "NEUTRA")
    
    procesos: tuple = (
        "VENTA",
        "POSTVENTA", 
        "CAMBIO PLAN",
        "FACTURACION",
        "COBRANZA",
        "MODIFICACIÓN"
    )

@dataclass
class AgentConfig:
    """Configuración del sistema multi-agente."""
    max_retries_validacion: int = 3       # Reintentos por agente antes de descartar caso
    max_casos_por_requerimiento: int = 50 # Límite de casos a generar
    temperature_agente1: float = 0.2      # Cabecera: más determinístico
    temperature_agente2: float = 0.3      # Detalle: un poco más variado
    temperature_maestro: float = 0.4      # Maestro: temperatura más alta para mayor variedad de combinaciones
    max_tokens_agente1: int = 1500        # Cabecera es corta
    max_tokens_agente2: int = 4500        # Pasos detallados + Descripción necesitan más tokens
    max_tokens_maestro: int = 2000        # Planificación y validación

# Configuración global
config = LMStudioConfig()
rag_config = RAGConfig()
paths = PathConfig()
template = TestCaseTemplate()
agent_config = AgentConfig()
