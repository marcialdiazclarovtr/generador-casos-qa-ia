from pydantic import BaseModel
from typing import Optional


class GenerateRequest(BaseModel):
    model: str = "gpt-oss:20b"
    lm_url: str = "http://127.0.0.1:11434/v1"
    use_ocr: bool = False
    process_requirements: bool = True
    max_casos: int = 20
    session_folder: Optional[str] = None
    user_focus: str = ""


class EnhanceJsonRequest(BaseModel):
    """Request para el Agente 0: mejorar JSON con LLM."""
    json_data: dict
    instructions: str = ""
    session_folder: str = ""
