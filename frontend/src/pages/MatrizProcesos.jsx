import React, { useState, useEffect } from 'react';

// ── Colores ────────────────────────────────────────────────────────────────
const DARK_BLUE = '#1e3a5f';
const CELESTE = '#0077b6';
const CELESTE_SUB = '#caf0f8';
const GREEN_DARK = '#1b5e20';
const GREEN_SUB = '#a5d6a7';
const SUBPROC_BG = '#bde0fe';

function getControlColor(codigo) {
  if (codigo === 'Ambas') return '#b3d9f7';
  if (codigo === 'CL' || codigo === 'VT') return '#f5c6cb';
  return '#e2e8f0';
}

function BoolCell({ value }) {
  if (value) {
    return (
      <td style={{ backgroundColor: '#d4edda', textAlign: 'center', border: '1px solid #9ca3af', minWidth: 56 }}>
        <span style={{ color: '#155724', fontSize: 16, fontWeight: 'bold' }}>✓</span>
      </td>
    );
  }
  return (
    <td style={{ backgroundColor: '#f8d7da', textAlign: 'center', border: '1px solid #9ca3af', minWidth: 56 }}>
      <span style={{ color: '#721c24', fontSize: 16, fontWeight: 'bold' }}>✗</span>
    </td>
  );
}

function MatrizTable({ data }) {
  // Aplana el JSON en filas
  const rows = [];
  data.forEach((p) => {
    p.subprocesos.forEach((sp, idx) => {
      rows.push({
        proceso: p.proceso,
        isFirst: idx === 0,
        rowspan: p.subprocesos.length,
        subproceso: sp.subproceso,
        control: sp.control_origen_codigo,
        habilitado: sp.habilitado,
      });
    });
  });

  const thBase = {
    border: '1px solid #9ca3af',
    padding: '6px 10px',
    color: '#ffffff',
    fontWeight: '600',
    fontSize: 12,
    textAlign: 'center',
    verticalAlign: 'middle',
    whiteSpace: 'pre-line',
  };

  return (
    <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 12 }}>
      <thead>
        {/* ── Fila 1 de encabezados ── */}
        <tr>
          <th rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE }}>{'Proceso\nN1'}</th>
          <th rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE }}>{'Procedimiento (SubProceso)\nN2'}</th>
          <th rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE }}>{'Control\n(Origen)'}</th>
          <th colSpan={4} style={{ ...thBase, backgroundColor: CELESTE }}>Residencial (B2C)</th>
          <th colSpan={4} style={{ ...thBase, backgroundColor: GREEN_DARK }}>Organización (B2B)</th>
        </tr>
        {/* ── Fila 2 de encabezados: subcolumnas ── */}
        <tr>
          {['Móvil', 'HFC', 'FTTH', 'Neutra'].map(h => (
            <th key={`b2c-${h}`} style={{ ...thBase, backgroundColor: CELESTE_SUB, color: '#1e3a5f' }}>{h}</th>
          ))}
          {['Móvil', 'HFC', 'FTTH', 'Neutra'].map(h => (
            <th key={`b2b-${h}`} style={{ ...thBase, backgroundColor: GREEN_SUB, color: '#1b5e20' }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            {/* Celda Proceso — solo en la primera fila del grupo, con rowspan */}
            {row.isFirst && (
              <td
                rowSpan={row.rowspan}
                style={{
                  border: '1px solid #9ca3af',
                  backgroundColor: DARK_BLUE,
                  color: '#ffffff',
                  fontWeight: '600',
                  fontSize: 12,
                  padding: '6px 10px',
                  textAlign: 'center',
                  verticalAlign: 'middle',
                }}
              >
                {row.proceso}
              </td>
            )}

            {/* Subproceso */}
            <td style={{
              border: '1px solid #9ca3af',
              backgroundColor: SUBPROC_BG,
              padding: '5px 10px',
              verticalAlign: 'middle',
              color: '#1e3a5f',
              fontWeight: 500,
            }}>
              {row.subproceso}
            </td>

            {/* Control Origen */}
            <td style={{
              border: '1px solid #9ca3af',
              backgroundColor: getControlColor(row.control),
              padding: '5px 10px',
              textAlign: 'center',
              verticalAlign: 'middle',
              fontWeight: 600,
              fontSize: 11,
            }}>
              {row.control}
            </td>

            {/* B2C */}
            <BoolCell value={row.habilitado.B2C.Movil} />
            <BoolCell value={row.habilitado.B2C.HFC} />
            <BoolCell value={row.habilitado.B2C.FTTH} />
            <BoolCell value={row.habilitado.B2C.Neutra} />

            {/* B2B */}
            <BoolCell value={row.habilitado.B2B.Movil} />
            <BoolCell value={row.habilitado.B2B.HFC} />
            <BoolCell value={row.habilitado.B2B.FTTH} />
            <BoolCell value={row.habilitado.B2B.Neutra} />
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function MatrizProcesos({ onBack }) {
  const [matrizJson, setMatrizJson] = useState(null);

  useEffect(() => {
    fetch("/api/matriz")
      .then(async (res) => {
        console.log("STATUS:", res.status);

        const text = await res.text();
        console.log("RAW RESPONSE:", text);

        if (!text) throw new Error("Respuesta vacía");

        return JSON.parse(text);
      })
      .then((data) => {
        console.log("DATA:", data);
        setMatrizJson(data.procesos);
      })
      .catch((err) => {
        console.error("Error cargando matriz:", err);
      });
  }, []);

  return (
    <div className="flex flex-col min-h-screen bg-gray-50 font-sans">

      {/* HEADER */}
      <header className="bg-[#DA291C] sticky top-0 z-50 shadow-md">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-white font-semibold text-base tracking-wide">
              Generador de Casos de Prueba
            </h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-white/15 text-white/90 border border-white/20">
              v2.0
            </span>
          </div>
          <div className="flex items-center gap-6">
            <button
              onClick={onBack}
              className="text-xs font-medium text-white border border-white/40 px-3 py-1.5 rounded-lg
             bg-white/10 hover:bg-white/20 transition-colors"
            >
              Inicio
            </button>
            <div className="w-px h-6 bg-white/30" />
            <img src="/logo_claro.png" alt="Claro" className="h-9 w-auto object-contain brightness-0 invert" />
            <div className="w-px h-6 bg-white/30" />
            <img src="/logo_vtr.png" alt="VTR" className="h-7 w-auto object-contain brightness-0 invert" />
          </div>
        </div>
      </header>

      {/* PAGE TITLE BAR */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-800">Configuración</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            En esta sección puedes configurar los parámetros que componen la matriz de procesos para la generación de casos de prueba.
          </p>
        </div>
      </div>

      {/* CONTENIDO — agrega aquí lo que necesites */}
      <main className="flex-grow max-w-7xl mx-auto w-full px-6 py-6">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 overflow-x-auto">
          {matrizJson ? (
            <MatrizTable data={matrizJson} />
          ) : (
            <p className="text-sm text-gray-400">Cargando matriz...</p>
          )}
        </div>
      </main>

      {/* FOOTER */}
      <footer className="bg-white border-t border-gray-200 mt-auto">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <img src="/logo_header.png" alt="ClaroVTR" className="h-8 w-auto opacity-60" />
          <div className="text-right">
            <p className="text-xs font-medium text-gray-600">© 2026 ClaroVTR. Todos los derechos reservados.</p>
            <p className="text-xs text-gray-400 mt-0.5">Plataforma interna de QA Automatizado — v2.0</p>
          </div>
        </div>
      </footer>

    </div>
  );
}

export default MatrizProcesos;