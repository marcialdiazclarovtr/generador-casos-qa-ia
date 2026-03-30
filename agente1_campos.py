"""
Agente 1: Rellena los campos de cabecera de un caso de prueba.

Campos que genera:
  Tipo de Prueba, Prioridad, Marca, Segmento, Tecnología,
  Proceso, Sub Proceso, Servicios.

NOTA: Descripción y Precondiciones se generan en el Agente 2 para
mantener coherencia con los pasos detallados.

Recibe contexto completo (dic, mantis, matriz, siebel) + JSON del requerimiento.
"""
import json
from typing import Optional

from config import agent_config
from llm_client import LMStudioClient, JSONExtractor, get_llm_client
from knowledge_loader import KnowledgeBase


class Agente1Campos:
    """Agente que rellena los campos de cabecera de un caso de prueba."""

    def __init__(self, kb: KnowledgeBase, llm_client: LMStudioClient = None):
        self.kb = kb
        self.llm = llm_client or get_llm_client()

    def _construir_prompt(
        self,
        json_req: dict,
        combinacion: dict,
        feedback_errores: Optional[list[str]] = None,
        user_focus: str = "",
    ) -> str:
        """Construye el prompt completo para el Agente 1."""

        # Extraer contexto del JSON del requerimiento
        contexto_parts = json_req.get("contexto", [])
        contexto_texto = "\n".join(contexto_parts[:5]) if isinstance(contexto_parts, list) else str(contexto_parts)

        que_piden = json_req.get("que_piden", [])
        que_piden_texto = "\n".join(f"- {p}" for p in que_piden[:10]) if isinstance(que_piden, list) else str(que_piden)

        solucion = json_req.get("solucion", [])
        solucion_texto = "\n".join(f"- {s}" for s in solucion[:5]) if isinstance(solucion, list) else str(solucion)

        impacto = json_req.get("impacto_sistemas_bd", [])
        impacto_texto = "\n".join(f"- {i}" for i in impacto[:8]) if isinstance(impacto, list) else str(impacto)

        # Obtener ejemplos similares de mantis
        marca = combinacion.get("marca", "Claro")
        proceso = combinacion.get("proceso", "Venta")
        ejemplos_mantis = self.kb.get_mantis_ejemplo(proceso, marca, max_ejemplos=2)

        ejemplos_texto = ""
        for i, ej in enumerate(ejemplos_mantis, 1):
            ejemplos_texto += f"\n--- Ejemplo {i} ---\n"
            for campo in ["FLUJO", "TECNOLOGIA", "MARCA", "Descripción"]:
                ejemplos_texto += f"{campo}: {ej.get(campo, '')}\n"

        # Valores permitidos del diccionario
        dic_texto = self.kb.get_diccionario_texto()

        # Matrices filtradas
        matrices_texto = self.kb.get_matrices_texto()

        # Feedback de correcciones previas
        feedback_section = ""
        if feedback_errores:
            errores = "\n".join(f"- {e}" for e in feedback_errores)
            feedback_section = f"""
=== CORRECCIONES REQUERIDAS (del Agente Maestro) ===
Los valores anteriores fueron RECHAZADOS por estos errores:
{errores}
Debes corregir estos errores en tu nueva respuesta.
"""

        # Sección de enfoque del usuario
        user_focus_section = ""
        if user_focus:
            user_focus_section = f"""
=== ENFOQUE DEL USUARIO ===
El usuario pide que los casos se enfoquen en: "{user_focus}"
Asegúrate de que la cabecera refleje este enfoque:
- Si el enfoque implica una tecnología, marca o proceso específico, priórizálo
- Los Servicios deben ser coherentes con el enfoque
"""

        sub_proceso_planificado = combinacion.get("sub_proceso", "")

        prompt = f"""Eres un experto QA de telecomunicaciones de Claro/VTR Chile.
Tu tarea es rellenar los CAMPOS DE CABECERA de un caso de prueba para certificación.

=== REQUERIMIENTO DEL PROYECTO ===
{contexto_texto[:2000]}

Qué se pide:
{que_piden_texto[:1500]}

Solución propuesta:
{solucion_texto[:1000]}

Impacto en sistemas:
{impacto_texto[:1000]}

=== COMBINACIÓN OBJETIVO PARA ESTE CASO ===
Proceso: {proceso}
Sub Proceso: {sub_proceso_planificado}  ← USAR EXACTAMENTE ESTE SUB-PROCESO
Tecnología: {combinacion.get('tecnologia', 'N/A')}
Marca: {marca}
Segmento: {combinacion.get('segmento', 'B2C Residencial')}
Empaquetado: {combinacion.get('empaquetado', '3Play')}  ← INCLUIR en Descripción y Servicios

IMPORTANTE: El Sub Proceso ya fue decidido: "{sub_proceso_planificado}".
Debes usarlo tal como está. NO lo cambies ni generalices.
El Empaquetado ({combinacion.get('empaquetado', '3Play')}) debe reflejarse en la Descripción y Servicios.

=== DICCIONARIO DE CAMPOS (valores y tipos permitidos) ===
{dic_texto}

=== COMBINACIONES VÁLIDAS EN MATRIZ ===
{matrices_texto[:2000]}

=== EJEMPLOS REALES DE CASOS SIMILARES (del equipo QA) ===
{ejemplos_texto}

=== MAPA DE PLATAFORMAS SIEBEL (sistemas reales) ===
Sistemas: {', '.join(self.kb.siebel_sistemas)}
{feedback_section}
{user_focus_section}

=== INSTRUCCIONES ===
1. Rellena los campos de cabecera del caso de prueba
2. Usa SOLO valores permitidos del diccionario para cada campo
3. Sigue el estilo de los ejemplos de Mantis del equipo QA
4. Razona sobre por qué eliges cada valor
5. IMPORTANTE: El Sub Proceso debe ser ATÓMICO y ESPECÍFICO.
   - CORRECTO: "Alta SSAA Lite", "RESET SSAA Pro", "Cambio Plan SSAA Plus"
   - INCORRECTO: "Alta + Modificación + Suspensión" (eso son VARIOS sub-procesos)
   - Cada caso de prueba cubre UN SOLO sub-proceso para UN SOLO producto/servicio
6. El Empaquetado ({combinacion.get('empaquetado', '3Play')}) DEBE reflejarse en:
   - Descripción: mencionar el tipo de bundle (ej: "Validar Venta Fija 3Play FTTH...")
   - Servicios: listar EXACTAMENTE los servicios que corresponden al número de play:
     * 1Play = UN solo servicio (ej: "Inet" O "TV" O "Telefonía", según el caso)
     * 2Play = DOS servicios (ej: "Inet + TV" O "Inet + Telefonía")
     * 3Play = TRES servicios (ej: "Inet + TV + Telefonía")
     * OTT   = "OTT"
     * Prepago / PostPago / ClaroUP = el servicio que corresponda
   NUNCA pongas más servicios de los que indica el número de play.
   Para 1Play NO pongas "Inet + TV + Telefonía" — eso sería un error grave.

=== VALORES PERMITIDOS POR CAMPO ===
- Tipo de Prueba: "Regresiva", "Proyecto (Funcional)", "Funcional Positiva"
- Prioridad: 1, 2, 3 (1=Alta, 2=Media, 3=Baja)
- Marca: "Claro", "VTR"
- Segmento: "B2B PYME", "B2B GC", "B2C PYME", "B2C Residencial", "B2C", "B2B"
- Tecnología: "NFTT", "NEUTRA", "HFC", "FTTH", "CFTT", "MOVIL", "SIP", "XGSPON", "GPON"
- Proceso: "Venta", "Cambio de Promoción", "Traslado", "Modificación", "Suspensión", "Reanudación", "Retención", "Servicio Tecnico", "Facturacion", "Cancelacion", "Activacion", "Postventa"
- Sub Proceso: UN sub-proceso específico y atómico (ej: "Crear Cliente", "Venta Fija", "Cambio de Promo")
- Empaquetado: "1Play", "2Play", "3Play", "OTT", "Prepago", "PostPago", "ClaroUP"
- Servicios: Texto libre con nombres de servicios/promociones (ej: "Inet + TV + Telefonía" para 3Play)

IMPORTANTE: Tu respuesta debe ser ÚNICAMENTE un JSON válido.
Formato exacto:
{{
  "Tipo de Prueba": "Proyecto (Funcional)",
  "Prioridad": 1,
  "Marca": "{marca}",
  "Segmento": "{combinacion.get('segmento', 'B2C Residencial')}",
  "Tecnología": "{combinacion.get('tecnologia', 'HFC')}",
  "Proceso": "{proceso}",
  "Sub Proceso": "{sub_proceso_planificado}",
  "Empaquetado": "{combinacion.get('empaquetado', '3Play')}",
  "Servicios": "solo los servicios del empaquetado (1Play=1 svc, 2Play=2 svc, 3Play=3 svc)",
  "razonamiento": "explica brevemente por qué elegiste estos valores"
}}"""
        return prompt

    def generar(
        self,
        json_req: dict,
        combinacion: dict,
        feedback_errores: Optional[list[str]] = None,
        user_focus: str = "",
    ) -> dict:
        """
        Genera los campos de cabecera para un caso de prueba.

        Args:
            json_req: JSON del requerimiento (output de main.py)
            combinacion: dict con {proceso, tecnologia, marca} objetivo
            feedback_errores: lista de errores del intento anterior (para corregir)

        Returns:
            dict con campos: Tipo de Prueba, Prioridad, Marca, Segmento,
                            Tecnología, Proceso, Sub Proceso, Servicios, Descripción
        """
        prompt = self._construir_prompt(json_req, combinacion, feedback_errores, user_focus=user_focus)

        print(f"  🤖 Agente 1 generando cabecera: {combinacion.get('proceso')}/{combinacion.get('tecnologia')}/{combinacion.get('marca')}...")

        # Intentar con response_format primero, luego sin él
        raw_response = None
        for attempt in range(2):
            try:
                kwargs = {
                    "temperature": agent_config.temperature_agente1,
                    "max_tokens": agent_config.max_tokens_agente1,
                }
                if attempt == 0:
                    kwargs["response_format"] = {"type": "json_object"}

                raw_response = self.llm.chat_with_retry(
                    [{"role": "user", "content": prompt}],
                    **kwargs,
                )
                parsed = JSONExtractor.extract(raw_response)
                break
            except Exception as e:
                if attempt == 0:
                    print(f"  ⚠️ Reintentando sin response_format...")
                else:
                    print(f"  ⚠️ Error parseando respuesta de Agente 1: {e}")
                    if raw_response:
                        print(f"  📜 Raw (500 chars): {raw_response[:500]}")
                    parsed = {
                        "Tipo de Prueba": "Proyecto (Funcional)",
                        "Prioridad": 1,
                        "Marca": combinacion.get("marca", "Claro"),
                        "Segmento": "B2C Residencial",
                        "Tecnología": combinacion.get("tecnologia", "HFC"),
                        "Proceso": combinacion.get("proceso", ""),
                        "Sub Proceso": combinacion.get("sub_proceso", ""),
                        "Servicios": "",
                        "razonamiento": "Fallback por error de parsing",
                    }

        # Limpiar razonamiento (no va al output final)
        razonamiento = parsed.pop("razonamiento", "")
        if razonamiento:
            print(f"  💭 Razonamiento A1: {razonamiento}")

        return parsed
