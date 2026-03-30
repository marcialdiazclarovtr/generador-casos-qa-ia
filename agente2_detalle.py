"""
Agente 2: Rellena los campos de detalle de un caso de prueba.

Campos que genera:
  Descripción, Precondiciones, Paso a Paso, Resultado Esperado, Datos de Prueba.

Recibe contexto completo (dic, mantis, matriz, siebel) + JSON del requerimiento
+ la cabecera validada del Agente 1 para mantener coherencia.
"""
import json
from typing import Optional

from config import agent_config
from llm_client import LMStudioClient, JSONExtractor, get_llm_client
from knowledge_loader import KnowledgeBase


class Agente2Detalle:
    """Agente que rellena los campos de detalle (pasos, precondiciones, resultado)."""

    def __init__(self, kb: KnowledgeBase, llm_client: LMStudioClient = None):
        self.kb = kb
        self.llm = llm_client or get_llm_client()

    def _construir_prompt(
        self,
        json_req: dict,
        cabecera_validada: dict,
        feedback_errores: Optional[list[str]] = None,
        user_focus: str = "",
    ) -> str:
        """Construye el prompt completo para el Agente 2."""

        # Contexto del JSON del requerimiento
        contexto_parts = json_req.get("contexto", [])
        contexto_texto = "\n".join(contexto_parts[:5]) if isinstance(contexto_parts, list) else str(contexto_parts)

        que_piden = json_req.get("que_piden", [])
        que_piden_texto = "\n".join(f"- {p}" for p in que_piden[:10]) if isinstance(que_piden, list) else str(que_piden)

        solucion = json_req.get("solucion", [])
        solucion_texto = "\n".join(f"- {s}" for s in solucion[:5]) if isinstance(solucion, list) else str(solucion)

        impacto = json_req.get("impacto_sistemas_bd", [])
        impacto_texto = "\n".join(f"- {i}" for i in impacto[:8]) if isinstance(impacto, list) else str(impacto)

        flujo_req = json_req.get("flujo", [])
        flujo_texto = "\n".join(f"- {f}" for f in flujo_req[:5]) if isinstance(flujo_req, list) else str(flujo_req)

        # Cabecera ya validada del Agente 1
        proceso = cabecera_validada.get("Proceso", "")
        marca = cabecera_validada.get("Marca", "Claro")
        tecnologia = cabecera_validada.get("Tecnología", "")
        sub_proceso = cabecera_validada.get("Sub Proceso", "")
        segmento = cabecera_validada.get("Segmento", "")
        servicios = cabecera_validada.get("Servicios", "")

        empaquetado = cabecera_validada.get("Empaquetado", "3Play")

        cabecera_texto = (
            f"Proceso: {proceso}\n"
            f"Sub Proceso: {sub_proceso}\n"
            f"Tecnología: {tecnologia}\n"
            f"Marca: {marca}\n"
            f"Segmento: {segmento}\n"
            f"Empaquetado: {empaquetado}\n"
            f"Servicios: {servicios}"
        )

        # Ejemplos de mantis del mismo proceso/marca
        ejemplos_mantis = self.kb.get_mantis_ejemplo(proceso, marca, max_ejemplos=2)

        ejemplos_texto = ""
        for i, ej in enumerate(ejemplos_mantis, 1):
            ejemplos_texto += f"\n--- Ejemplo Real {i} (del equipo QA) ---\n"
            ejemplos_texto += f"FLUJO: {ej.get('FLUJO', '')}\n"
            ejemplos_texto += f"TECNOLOGIA: {ej.get('TECNOLOGIA', '')}\n"
            ejemplos_texto += f"Precondición: {ej.get('Precondición', ej.get('Precondicion', 'N/A'))}\n"
            pasos = ej.get("Pasos", ej.get("Paso a Paso", ""))
            ejemplos_texto += f"Paso a Paso:\n{pasos}\n"
            resultado = ej.get("Resultado Esperado", "")
            ejemplos_texto += f"Resultado Esperado:\n{resultado}\n"

        # Mapa Siebel
        siebel_texto = self.kb.siebel_flow

        # Diccionario
        dic_texto = self.kb.get_diccionario_texto()

        # Feedback de correcciones
        feedback_section = ""
        if feedback_errores:
            errores = "\n".join(f"- {e}" for e in feedback_errores)
            feedback_section = f"""
=== CORRECCIONES REQUERIDAS (del Agente Maestro) ===
El detalle anterior fue RECHAZADO por estos errores:
{errores}
Debes corregir estos errores manteniendo coherencia con la cabecera.
"""

        # Sección de enfoque del usuario
        user_focus_section = ""
        if user_focus:
            user_focus_section = f"""
=== ENFOQUE DEL USUARIO ===
El usuario pide que los casos se enfoquen en: "{user_focus}"
La Descripción, los pasos, resultado esperado y datos de prueba deben reflejar este enfoque:
- La Descripción debe mencionar el área de enfoque
- Los pasos deben ser específicos para el área indicada
- Las validaciones deben verificar aspectos relacionados con el enfoque
- Los datos de prueba deben ser relevantes al área de enfoque
"""

        prompt = f"""Eres un experto QA de telecomunicaciones de Claro/VTR Chile.
Tu tarea es rellenar los CAMPOS DE DETALLE de un caso de prueba,
manteniendo COHERENCIA TOTAL con la cabecera ya validada.

=== CABECERA YA VALIDADA (del Agente 1 — NO la modifiques) ===
{cabecera_texto}

=== REQUERIMIENTO DEL PROYECTO ===
{contexto_texto[:2000]}

Qué se pide:
{que_piden_texto[:1500]}

Solución propuesta:
{solucion_texto[:1000]}

Impacto en sistemas:
{impacto_texto[:1000]}

Flujo del proyecto:
{flujo_texto[:800]}

=== DICCIONARIO DE CAMPOS ===
{dic_texto}

=== MAPA DE PLATAFORMAS SIEBEL (flujo real de la orden) ===
{siebel_texto}

Sistemas reales (SOLO usar estos): {', '.join(self.kb.siebel_sistemas)}

=== EJEMPLOS REALES DEL EQUIPO QA ===
Estudia la ESTRUCTURA y NIVEL DE DETALLE de estos ejemplos.
Tus pasos deben seguir el MISMO formato:
{ejemplos_texto[:3000]}
{feedback_section}
{user_focus_section}

=== REGLA CRÍTICA: UN SOLO SUB-PROCESO POR CASO ===
Este caso cubre ÚNICAMENTE el sub-proceso: "{sub_proceso}"
NO mezcles múltiples flujos en un solo caso. Por ejemplo:
- INCORRECTO: Cubrir activación + modificación + suspensión + baja en un caso
- CORRECTO: Cubrir SOLO "{sub_proceso}" con todos sus pasos específicos
La Descripción, Precondiciones, Pasos y Resultado deben referirse ÚNICAMENTE a "{sub_proceso}".

=== INSTRUCCIONES DETALLADAS ===
1. PRECONDICIONES: Estado del sistema/datos necesario ANTES de ejecutar el caso.
   Debe ser coherente con el Proceso, Tecnología y Empaquetado de la cabecera.
   Incluir el empaquetado: ej: "Cliente {segmento} con servicio {empaquetado} activo en red {tecnologia}"
   Ejemplos: "Cliente activo con servicio {empaquetado} HFC", "Usuario creado, servicio {empaquetado} activo"

2. DESCRIPCIÓN: Resumen conciso de lo que hace este caso de prueba.
   - Debe ser específica para el sub-proceso "{sub_proceso}"
   - DEBE mencionar el empaquetado "{empaquetado}" (ej: "Validar Venta Fija 3Play FTTH...")
   - Debe reflejar las precondiciones (ej: si el cliente ya existe, mencionarlo)
   - Ejemplo: "Realizar {sub_proceso} {empaquetado} {tecnologia} Marca {marca} Segmento {segmento}"
   - NO debe ser genérica ni mezclar múltiples acciones

3. PASO A PASO: Deben seguir esta estructura EXACTA (como las Mantis):
   - Secciones principales con números romanos: I., II., III., IV., V.
   - Pasos individuales con números arábigos: 1., 2., 3.
   - Sub-pasos con letras minúsculas: a., b., c.
   - DEBEN mencionar las plataformas REALES del mapa Siebel (Siebel CRM, TOA, BRM, OSM, UIM, etc.)
   - NO inventes plataformas que no existen en el mapa
   - Incluye validaciones post-ejecución en plataformas (Siebel, UIM, OSM, BRM)
   - TODOS los pasos deben referirse SOLO al sub-proceso "{sub_proceso}"

4. RESULTADO ESPERADO: Lista de validaciones con el formato:
   - Cada línea empieza con * (asterisco)
   - Describe el estado final verificable en cada plataforma

5. DATOS DE PRUEBA: Datos específicos necesarios para ejecutar (RUT, cuenta, etc.)
   Si no aplica, dejar vacío.

IMPORTANTE: Tu respuesta debe ser ÚNICAMENTE un JSON válido.
Formato exacto:
{{
  "Precondiciones": "texto de precondiciones",
  "Descripción": "descripción concisa y específica de este caso (coherente con las precondiciones)",
  "Paso a Paso": "I. Sección...\\n1. Paso...\\n...",
  "Resultado Esperado": "*Validación 1\\n*Validación 2\\n...",
  "Datos de Prueba": "datos necesarios o vacío",
  "razonamiento": "explica tu razonamiento sobre los pasos elegidos"
}}"""
        return prompt

    def generar(
        self,
        json_req: dict,
        cabecera_validada: dict,
        feedback_errores: Optional[list[str]] = None,
        user_focus: str = "",
    ) -> dict:
        """
        Genera los campos de detalle para un caso de prueba.

        Args:
            json_req: JSON del requerimiento
            cabecera_validada: cabecera aprobada por el Agente Maestro
            feedback_errores: errores del intento anterior para corregir

        Returns:
            dict con: Descripción, Precondiciones, Paso a Paso, Resultado Esperado, Datos de Prueba
        """
        prompt = self._construir_prompt(json_req, cabecera_validada, feedback_errores, user_focus=user_focus)

        proceso = cabecera_validada.get("Proceso", "?")
        marca = cabecera_validada.get("Marca", "?")
        print(f"  🤖 Agente 2 generando detalle para: {proceso}/{marca}...")

        # Intentar con response_format primero, luego sin él
        raw_response = None
        for attempt in range(2):
            try:
                kwargs = {
                    "temperature": agent_config.temperature_agente2,
                    "max_tokens": agent_config.max_tokens_agente2,
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
                    print(f"  ⚠️ Error parseando respuesta de Agente 2: {e}")
                    if raw_response:
                        print(f"  📜 Raw (500 chars): {raw_response[:500]}")
                    parsed = {
                        "Precondiciones": "N/A",
                        "Descripción": f"Caso de prueba para {cabecera_validada.get('Sub Proceso', cabecera_validada.get('Proceso', ''))}",
                        "Paso a Paso": "I. Verificar estado inicial\n1. Revisar plataforma Siebel",
                        "Resultado Esperado": "*Caso ejecutado correctamente",
                        "Datos de Prueba": "",
                        "razonamiento": "Fallback por error de parsing",
                    }

        # Limpiar razonamiento
        razonamiento = parsed.pop("razonamiento", "")
        if razonamiento:
            print(f"  💭 Razonamiento A2: {razonamiento}")

        return parsed
