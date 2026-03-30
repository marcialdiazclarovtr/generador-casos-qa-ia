"""
Módulo de carga y normalización de todas las fuentes de conocimiento.

Carga dic, mantis, matrices y siebel en un objeto KnowledgeBase
que será compartido por todos los agentes.
"""
import csv
import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


DATOS_DIR = Path(__file__).parent / "Datos"


# ── Mapeos de normalización Diccionario ↔ Matriz ────────────────────────────

# Procesos del diccionario → procesos de la matriz
PROCESO_DIC_A_MATRIZ = {
    "Venta": "Venta",
    "Cambio de Promoción": "Postventa",
    "Traslado": "Postventa",
    "Modificación": "Postventa",
    "Suspensión": "Postventa",
    "Reanudación": "Postventa",
    "Retención": "Postventa",
    "Servicio Técnico": "Postventa",
    "Servicio Tecnico": "Postventa",
    "Facturación": "Facturacion",
    "Facturacion": "Facturacion",
    "Cancelación": "Postventa",
    "Cancelacion": "Postventa",
    "Activación": "Venta",
    "Activacion": "Venta",
    "Postventa": "Postventa",
    "Recaudacion": "Recaudacion",
    "Recaudación": "Recaudacion",
    "Cobranza": "Cobranza",
}

# Segmento del diccionario → segmento macro de la matriz
SEGMENTO_A_MACRO = {
    "B2C": "B2C",
    "B2C Residencial": "B2C",
    "B2C PYME": "B2C",
    "B2B": "B2B",
    "B2B PYME": "B2B",
    "B2B GC": "B2B",
}

# Tecnología del diccionario → red de la matriz
RED_NORM = {
    "MOVIL": "Movil",
    "Movil": "Movil",
    "HFC": "HFC",
    "FTTH": "FTTH",
    "NEUTRA": "Neutra",
    "Neutra": "Neutra",
    "NFTT": "FTTH",
    "CFTT": "FTTH",
    "SIP": "Movil",
    "XGSPON": "FTTH",
    "GPON": "FTTH",
}


# ── Modelo de datos ─────────────────────────────────────────────────────────

@dataclass
class CampoDiccionario:
    """Definición de un campo del diccionario QA."""
    nombre: str
    descripcion: str
    tipo_dato: str
    valores_permitidos: list[str]
    ejemplos: list[str]


@dataclass
class KnowledgeBase:
    """Almacén centralizado de todo el conocimiento para los agentes."""
    diccionario: dict[str, CampoDiccionario] = field(default_factory=dict)
    mantis_claro: list[dict] = field(default_factory=list)
    mantis_vtr: list[dict] = field(default_factory=list)
    matrices: dict = field(default_factory=dict)          # legacy lookup (proc,ctrl)→celdas
    matrices_raw: str = ""                                 # texto legible para prompts
    matriz_json: dict = field(default_factory=dict)        # estructura JSON completa
    matriz_lookup: dict = field(default_factory=dict)      # (proceso,subproceso)→habilitado
    siebel_flow: str = ""
    siebel_sistemas: list[str] = field(default_factory=list)

    # ── Consultas ────────────────────────────────────────────────────────

    def get_mantis_por_flujo(self, flujo: str, marca: str) -> list[dict]:
        """Filtra ejemplos mantis por flujo y marca para few-shot."""
        fuente = self.mantis_claro if marca.upper() == "CLARO" else self.mantis_vtr
        flujo_upper = flujo.upper().strip()
        return [m for m in fuente if m.get("FLUJO", "").upper().strip() == flujo_upper]

    def get_mantis_ejemplo(self, flujo: str, marca: str, max_ejemplos: int = 2) -> list[dict]:
        """Obtiene N ejemplos del mismo flujo/marca, o cualquiera si no hay."""
        candidatos = self.get_mantis_por_flujo(flujo, marca)
        if candidatos:
            return candidatos[:max_ejemplos]
        # Fallback: cualquier ejemplo de la misma marca
        fuente = self.mantis_claro if marca.upper() == "CLARO" else self.mantis_vtr
        return fuente[:max_ejemplos]

    def validar_combinacion(self, proceso: str, sub_proceso: str = None,
                            segmento: str = None, red: str = None) -> dict:
        """
        Valida una combinación contra la matriz JSON.
        
        Args:
            proceso: Proceso del diccionario (ej: "Venta", "Suspensión")
            sub_proceso: Sub proceso específico (ej: "Venta Fija")
            segmento: Segmento del diccionario (ej: "B2C Residencial")
            red: Tecnología/red del diccionario (ej: "NEUTRA", "HFC")
        
        Returns:
            {"valido": bool, "razon": str}
        """
        if not self.matriz_lookup:
            return {"valido": True, "razon": "Matriz no cargada, se asume válido"}

        # Normalizar red
        red_matriz = RED_NORM.get(red.strip(), red.strip()) if red else None
        # Normalizar segmento
        seg_macro = SEGMENTO_A_MACRO.get(segmento.strip(), segmento.strip()) if segmento else None

        if not sub_proceso:
            return {"valido": True, "razon": "Sin sub_proceso, no se puede validar"}

        # Buscar subproceso en el lookup (fuzzy match)
        sub_norm = sub_proceso.strip().lower()
        match_key = None
        for key in self.matriz_lookup:
            key_sub = key[1].strip().lower()
            if sub_norm == key_sub or sub_norm in key_sub or key_sub in sub_norm:
                match_key = key
                break

        if not match_key:
            return {"valido": True, "razon": f"Sub proceso '{sub_proceso}' no encontrado en matriz, se asume válido"}

        habilitado = self.matriz_lookup[match_key]

        if seg_macro and red_matriz:
            if seg_macro in habilitado and red_matriz in habilitado[seg_macro]:
                es_valido = habilitado[seg_macro][red_matriz]
                if not es_valido:
                    return {
                        "valido": False,
                        "razon": f"'{sub_proceso}' no está habilitado para {seg_macro}+{red_matriz} en la matriz"
                    }
            else:
                return {"valido": True, "razon": f"Segmento/red no encontrado en matriz para '{sub_proceso}'"}

        return {"valido": True, "razon": "Combinación validada OK"}

    def get_combinaciones_habilitadas(self, segmento: str = None, red: str = None,
                                       marca: str = None) -> list[dict]:
        """
        Retorna TODAS las combinaciones proceso/subproceso habilitadas
        para un segmento+red+marca dados.

        Args:
            segmento: Segmento del diccionario (ej: "B2C Residencial", "B2B")
            red: Tecnología/red del diccionario (ej: "NEUTRA", "HFC", "MOVIL")
            marca: "Claro", "VTR" o None para ambas

        Returns:
            [{"proceso": "Venta", "subproceso": "Crear Cliente", "control_origen": "CL"}, ...]
        """
        if not self.matriz_json:
            return []

        seg_macro = SEGMENTO_A_MACRO.get(segmento.strip(), segmento.strip()) if segmento else None
        red_matriz = RED_NORM.get(red.strip(), red.strip()) if red else None

        # Normalizar marca para comparar con control_origen_equivale_a
        marca_upper = marca.strip().upper() if marca else None

        resultado = []
        for proc in self.matriz_json.get("procesos", []):
            proceso_nombre = proc["proceso"]
            for sp in proc.get("subprocesos", []):
                sub_nombre = sp["subproceso"]
                # Usar la clave correcta del JSON
                control_codigo = sp.get("control_origen_codigo", "")
                control_equivale = sp.get("control_origen_equivale_a", [])
                hab = sp.get("habilitado", {})

                # Filtrar por marca si se especificó
                if marca_upper:
                    # control_origen_equivale_a contiene "CLARO" y/o "VTR"
                    marcas_validas = [m.upper() for m in control_equivale]
                    if marca_upper not in marcas_validas:
                        continue

                # Si no hay filtro de seg/red, incluir todo lo que pasó el filtro de marca
                if not seg_macro or not red_matriz:
                    resultado.append({
                        "proceso": proceso_nombre,
                        "subproceso": sub_nombre,
                        "control_origen": control_codigo,
                    })
                    continue

                # Filtrar por segmento + red
                if seg_macro in hab and red_matriz in hab[seg_macro]:
                    if hab[seg_macro][red_matriz]:
                        resultado.append({
                            "proceso": proceso_nombre,
                            "subproceso": sub_nombre,
                            "control_origen": control_codigo,
                        })

        return resultado

    def get_subprocesos_por_proceso(self, proceso_dic: str, segmento: str = None, red: str = None) -> list[str]:
        """
        Dado un proceso del diccionario, retorna los subprocesos habilitados
        en la matriz para el segmento+red dados.
        """
        proceso_matriz = PROCESO_DIC_A_MATRIZ.get(proceso_dic.strip(), proceso_dic.strip())
        combos = self.get_combinaciones_habilitadas(segmento, red)
        return [
            c["subproceso"] for c in combos
            if c["proceso"] == proceso_matriz
        ]

    def get_valores_permitidos(self, campo: str) -> list[str]:
        """Devuelve valores permitidos de un campo del diccionario."""
        campo_info = self.diccionario.get(campo)
        if campo_info and campo_info.valores_permitidos:
            return campo_info.valores_permitidos
        return []

    def get_sistemas_involucrados(self) -> list[str]:
        """Devuelve los nombres de sistemas extraídos del mapa Siebel."""
        return self.siebel_sistemas

    def get_flujos_disponibles(self) -> list[str]:
        """Devuelve flujos únicos de las mantis."""
        flujos = set()
        for m in self.mantis_claro + self.mantis_vtr:
            f = m.get("FLUJO", "").strip()
            if f:
                flujos.add(f)
        return sorted(flujos)

    def get_diccionario_texto(self) -> str:
        """Devuelve el diccionario formateado como texto para prompts."""
        lines = []
        for nombre, campo in self.diccionario.items():
            vals = ", ".join(campo.valores_permitidos) if campo.valores_permitidos else "Texto libre"
            lines.append(f"- {nombre} ({campo.tipo_dato}): {campo.descripcion}")
            lines.append(f"  Valores permitidos: {vals}")
            if campo.ejemplos:
                lines.append(f"  Ejemplos: {', '.join(campo.ejemplos)}")
        return "\n".join(lines)

    def get_matrices_texto(self) -> str:
        """Devuelve las matrices formateadas como texto legible para prompts."""
        if not self.matriz_json:
            return self.matrices_raw  # fallback al texto viejo

        lines = ["LEYENDA control_origen: [CL]=solo Claro  [VT]=solo VTR  [Ambas]=Claro y VTR"]
        for proc in self.matriz_json.get("procesos", []):
            lines.append(f"\nPROCESO: {proc['proceso']}")
            for sp in proc.get("subprocesos", []):
                sub = sp["subproceso"]
                ctrl = sp.get("control_origen_codigo", "?")
                hab = sp.get("habilitado", {})
                parts = []
                for seg in ["B2C", "B2B"]:
                    if seg in hab:
                        redes = []
                        for red_name in ["Movil", "HFC", "FTTH", "Neutra"]:
                            val = hab[seg].get(red_name, False)
                            redes.append(f"{red_name}{'✓' if val else '✗'}")
                        parts.append(f"{seg}({' '.join(redes)})")
                hab_str = " ".join(parts)
                lines.append(f"  - {sub} [{ctrl}] — {hab_str}")
        return "\n".join(lines)

    def formatear_mantis_ejemplo(self, ejemplo: dict) -> str:
        """Formatea un caso mantis como texto para incluir en prompts."""
        campos_relevantes = [
            "Id", "FLUJO", "TECNOLOGIA", "MARCA", "Descripción",
            "Precondición", "Pasos", "Resultado Esperado"
        ]
        lines = []
        for c in campos_relevantes:
            val = ejemplo.get(c, "")
            if val:
                lines.append(f"{c}: {val}")
        return "\n".join(lines)


# ── Funciones de carga ──────────────────────────────────────────────────────

def load_diccionario(path: Path = None) -> dict[str, CampoDiccionario]:
    """Parsea el CSV del diccionario de campos."""
    path = path or DATOS_DIR / "dic" / "NUEVO_DICCIONARIO 3.csv"
    resultado = {}

    with open(path, encoding="latin-1") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            nombre = row.get("Campo", "").strip()
            if not nombre:
                continue

            # Parsear valores permitidos
            valores_raw = row.get("Valores Permitidos (Reglas/Listas)", "")
            valores = [v.strip() for v in re.split(r"[,;]", valores_raw) if v.strip()]

            # Parsear ejemplos
            ejemplos_raw = row.get("Ejemplos (Casos de Uso)", "")
            ejemplos = [e.strip() for e in re.split(r"[,;]", ejemplos_raw) if e.strip()]

            resultado[nombre] = CampoDiccionario(
                nombre=nombre,
                descripcion=row.get("Descripción", "").strip(),
                tipo_dato=row.get("Tipo de Dato", "").strip(),
                valores_permitidos=valores,
                ejemplos=ejemplos,
            )

    return resultado


def load_mantis(path: Path, encoding: str = "latin-1") -> list[dict]:
    """Parsea un CSV de Mantis y devuelve lista de casos como dicts."""
    casos = []

    with open(path, encoding=encoding) as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            # Normalizar nombres de columnas
            caso = {}
            for key, val in row.items():
                key_clean = key.strip() if key else ""
                caso[key_clean] = val.strip() if val else ""
            # Solo agregar si tiene al menos FLUJO
            if caso.get("FLUJO"):
                casos.append(caso)

    return casos


def load_matrices(path: Path = None) -> tuple[dict, str]:
    """
    Parsea matrices_estructuradas_limpias.txt (legacy).
    Devuelve:
      - dict de (Procedimiento, Control) → lista de celdas
      - texto raw para incluir en prompts
    """
    path = path or DATOS_DIR / "matriz" / "matrices_estructuradas_limpias.txt"

    if not path.exists():
        return {}, ""

    with open(path, encoding="utf-8") as f:
        raw = f.read()

    matrices = {}
    for line in raw.strip().split("\n"):
        m_proc = re.search(r'Procedimiento="([^"]*)"', line)
        m_ctrl = re.search(r'Control=(\S*)', line)
        m_cells = re.search(r"Celdas=\[([^\]]*)\]", line)

        if m_proc and m_cells:
            proc = m_proc.group(1).strip()
            ctrl = m_ctrl.group(1).strip() if m_ctrl else ""
            cells_raw = m_cells.group(1)
            cells = [c.strip().strip("'\"") for c in cells_raw.split(",")]
            matrices[(proc, ctrl)] = cells

    return matrices, raw


def load_matriz_json(path: Path = None) -> tuple[dict, dict]:
    """
    Carga matriz.json estructurada.
    Devuelve:
      - matriz_json: estructura JSON completa
      - matriz_lookup: dict de (proceso, subproceso) → {B2C: {Movil: bool, ...}, B2B: {...}}
    """
    path = path or DATOS_DIR / "matriz" / "matriz.json"

    if not path.exists():
        print(f"  ⚠️ No se encontró {path}, matriz JSON no disponible")
        return {}, {}

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Construir lookup rápido
    lookup = {}
    total_subs = 0
    for proc in data.get("procesos", []):
        proceso_nombre = proc["proceso"]
        for sp in proc.get("subprocesos", []):
            sub_nombre = sp["subproceso"]
            hab = sp.get("habilitado", {})
            lookup[(proceso_nombre, sub_nombre)] = hab
            total_subs += 1

    print(f"     → {total_subs} subprocesos en {len(data.get('procesos', []))} procesos")
    return data, lookup


def load_siebel(path: Path = None) -> tuple[str, list[str]]:
    """
    Lee siebel.md (diagrama Mermaid).
    Devuelve:
      - texto completo del diagrama
      - lista de nombres de sistemas extraídos
    """
    path = path or DATOS_DIR / "siebel" / "siebel.md"

    with open(path, encoding="utf-8") as f:
        raw = f.read()

    # Extraer nombres de sistemas de los nodos Mermaid
    # Buscar patrones como: (BRM Billing), (Siebel CRM), etc.
    # Formato Mermaid: "Descripción<br/>(NombreSistema)"
    sistemas = re.findall(r"\(([A-Z][A-Za-z\s]+)\)", raw)
    # Limpiar y deduplicar
    sistemas_unicos = []
    vistos = set()
    for s in sistemas:
        s_clean = s.strip()
        if s_clean and s_clean not in vistos:
            vistos.add(s_clean)
            sistemas_unicos.append(s_clean)

    return raw, sistemas_unicos


def load_all(datos_dir: Path = None) -> KnowledgeBase:
    """Carga todas las fuentes de datos y devuelve un KnowledgeBase completo."""
    datos = datos_dir or DATOS_DIR

    print("📚 Cargando base de conocimiento...")

    # Diccionario
    print("  📖 Cargando diccionario de campos...")
    diccionario = load_diccionario(datos / "dic" / "NUEVO_DICCIONARIO 3.csv")
    print(f"     → {len(diccionario)} campos cargados")

    # Mantis Claro
    mantis_claro_path = datos / "mantis" / "Mantis Nivelación 2026_V1(Regresivas Claro).csv"
    print("  📋 Cargando Mantis Claro...")
    mantis_claro = load_mantis(mantis_claro_path) if mantis_claro_path.exists() else []
    print(f"     → {len(mantis_claro)} casos cargados")

    # Mantis VTR
    mantis_vtr_path = datos / "mantis" / "Mantis Nivelación 2026_V1(Regresivas VTR).csv"
    print("  📋 Cargando Mantis VTR...")
    mantis_vtr = load_mantis(mantis_vtr_path) if mantis_vtr_path.exists() else []
    print(f"     → {len(mantis_vtr)} casos cargados")

    # Matrices — cargar JSON nueva (preferida) + TXT legacy (fallback)
    print("  📊 Cargando matrices de combinaciones...")
    matriz_json, matriz_lookup = load_matriz_json(datos / "matriz" / "matriz.json")
    matrices, matrices_raw_legacy = load_matrices(datos / "matriz" / "matrices_estructuradas_limpias.txt")
    print(f"     → {len(matrices)} reglas legacy cargadas")

    # Siebel
    print("  🗺️  Cargando mapa Siebel...")
    siebel_flow, siebel_sistemas = load_siebel(datos / "siebel" / "siebel.md")
    print(f"     → {len(siebel_sistemas)} sistemas identificados")

    kb = KnowledgeBase(
        diccionario=diccionario,
        mantis_claro=mantis_claro,
        mantis_vtr=mantis_vtr,
        matrices=matrices,
        matrices_raw=matrices_raw_legacy,
        matriz_json=matriz_json,
        matriz_lookup=matriz_lookup,
        siebel_flow=siebel_flow,
        siebel_sistemas=siebel_sistemas,
    )

    print(f"✅ Base de conocimiento cargada: "
          f"{len(diccionario)} campos, "
          f"{len(mantis_claro)}+{len(mantis_vtr)} mantis, "
          f"{len(matriz_lookup)} subprocesos (JSON) + {len(matrices)} reglas (legacy), "
          f"{len(siebel_sistemas)} sistemas")

    return kb


# ── Test rápido ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    kb = load_all()
    print("\n--- Resumen KnowledgeBase ---")
    print(f"Campos del diccionario: {list(kb.diccionario.keys())}")
    print(f"Flujos disponibles: {kb.get_flujos_disponibles()}")
    print(f"Sistemas Siebel: {kb.siebel_sistemas}")
    print(f"\nEjemplo mantis VENTA/CLARO:")
    ejemplos = kb.get_mantis_ejemplo("VENTA", "CLARO", 1)
    if ejemplos:
        print(kb.formatear_mantis_ejemplo(ejemplos[0])[:500])
