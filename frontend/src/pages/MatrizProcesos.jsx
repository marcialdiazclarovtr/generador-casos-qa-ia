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

function EditBoolCell({ value, onClick }) {
  return (
    <td
      onClick={onClick}
      style={{
        backgroundColor: value ? '#d4edda' : '#f8d7da',
        textAlign: 'center',
        border: '1px solid #9ca3af',
        minWidth: 56,
        cursor: 'pointer',
        userSelect: 'none',
      }}
      title="Click para cambiar"
    >
      <span style={{ color: value ? '#155724' : '#721c24', fontSize: 16, fontWeight: 'bold' }}>
        {value ? '✓' : '✗'}
      </span>
    </td>
  );
}

function MatrizTable({ data, setData }) {
  // ➕ Agregar proceso
  const addProcesoBelow = (pIdx) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));

      next.splice(pIdx + 1, 0, {
        proceso: "Nuevo Proceso",
        subprocesos: [
          {
            subproceso: "",
            control_origen_codigo: "Ambas",
            habilitado: {
              B2C: { Movil: true, HFC: true, FTTH: true, Neutra: true },
              B2B: { Movil: true, HFC: true, FTTH: true, Neutra: true }
            }
          }
        ]
      });

      return next;
    });
  };

  // Actualizar proceso
  const updateProceso = (pIdx, value) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[pIdx].proceso = value;
      return next;
    });
  };

  // ➖ Eliminar proceso
  const removeProceso = (pIdx) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.splice(pIdx, 1);
      return next;
    });
  };

  // Añadir subproceso
  const addSubprocesoBelow = (pIdx, spIdx) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));

      next[pIdx].subprocesos.splice(spIdx + 1, 0, {
        subproceso: "",
        control_origen_codigo: "Ambas",
        habilitado: {
          B2C: { Movil: true, HFC: true, FTTH: true, Neutra: true },
          B2B: { Movil: true, HFC: true, FTTH: true, Neutra: true }
        }
      });

      return next;
    });
  };

  // Eliminar subproceso
  const removeSubproceso = (pIdx, spIdx) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));

      // 1. Eliminar subproceso
      next[pIdx].subprocesos.splice(spIdx, 1);

      // 2. Si ya no quedan subprocesos → eliminar proceso completo
      if (next[pIdx].subprocesos.length === 0) {
        next.splice(pIdx, 1);
      }

      return next;
    });
  };

  const CICLO_CONTROL = ['Ambas', 'VT', 'CL'];

  // Helpers de mutación inmutable
  const updateSubproceso = (pIdx, spIdx, field, value) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[pIdx].subprocesos[spIdx][field] = value;
      return next;
    });
  };

  const toggleBool = (pIdx, spIdx, segmento, tecnologia) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[pIdx].subprocesos[spIdx].habilitado[segmento][tecnologia] =
        !next[pIdx].subprocesos[spIdx].habilitado[segmento][tecnologia];
      return next;
    });
  };

  const cycleControl = (pIdx, spIdx, current) => {
    const nextVal = CICLO_CONTROL[(CICLO_CONTROL.indexOf(current) + 1) % CICLO_CONTROL.length];
    updateSubproceso(pIdx, spIdx, 'control_origen_codigo', nextVal);
  };

  // Aplanar filas guardando índices originales
  const rows = [];
  data.forEach((p, pIdx) => {
    p.subprocesos.forEach((sp, spIdx) => {
      rows.push({ p, pIdx, sp, spIdx, isFirst: spIdx === 0, rowspan: p.subprocesos.length });
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
        <tr>
          <th rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE }}>{'Proceso\nN1'}</th>
          <th rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE }}>{'Procedimiento (SubProceso)\nN2'}</th>
          <th rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE }}>{'Control\n(Origen)'}</th>
          <th colSpan={4} style={{ ...thBase, backgroundColor: CELESTE }}>Residencial (B2C)</th>
          <th colSpan={4} style={{ ...thBase, backgroundColor: GREEN_DARK }}>Organización (B2B)</th>
          <th
            rowSpan={2}
            style={{ ...thBase, backgroundColor: DARK_BLUE }}
          >
            Agregar / Eliminar SubProceso
          </th>
        </tr>
        <tr>
          {['Móvil','HFC','FTTH','Neutra'].map(h => (
            <th key={`b2c-${h}`} style={{ ...thBase, backgroundColor: CELESTE_SUB, color: '#1e3a5f' }}>{h}</th>
          ))}
          {['Móvil','HFC','FTTH','Neutra'].map(h => (
            <th key={`b2b-${h}`} style={{ ...thBase, backgroundColor: GREEN_SUB, color: '#1b5e20' }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map(({ p, pIdx, sp, spIdx, isFirst, rowspan }, i) => (
          <tr key={i}>
            {isFirst && (
              <td
                rowSpan={rowspan}
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
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center' }}>
                  
                  {/* Nombre del proceso */}
                  <input
                    value={p.proceso}
                    onChange={e => updateProceso(pIdx, e.target.value)}
                    style={{
                      width: '100%',
                      background: 'transparent',
                      border: 'none',
                      outline: 'none',
                      fontSize: 12,
                      color: '#ffffff',
                      fontWeight: 600,
                      textAlign: 'center'
                    }}
                  />

                  {/* Botones */}
                  <div style={{ display: 'flex', gap: 4 }}>
                    
                    {/* ➖ Eliminar proceso */}
                    <button
                      onClick={() => removeProceso(pIdx)}
                      style={{
                        background: '#dc3545',
                        color: 'white',
                        border: 'none',
                        width: 22,
                        height: 22,
                        borderRadius: 4,
                        cursor: 'pointer',
                        fontWeight: 'bold'
                      }}
                      title="Eliminar proceso"
                    >
                      -
                    </button>

                    {/* ➕ Agregar proceso */}
                    <button
                      onClick={() => addProcesoBelow(pIdx)}
                      style={{
                        background: '#28a745',
                        color: 'white',
                        border: 'none',
                        width: 22,
                        height: 22,
                        borderRadius: 4,
                        cursor: 'pointer',
                        fontWeight: 'bold'
                      }}
                      title="Agregar proceso"
                    >
                      +
                    </button>

                  </div>
                </div>
              </td>
            )}

            {/* Subproceso — editable con input inline */}
            <td style={{
              border: '1px solid #9ca3af', backgroundColor: SUBPROC_BG,
              padding: '2px 6px', verticalAlign: 'middle',
            }}>
              <input
                value={sp.subproceso}
                onChange={e => updateSubproceso(pIdx, spIdx, 'subproceso', e.target.value)}
                style={{
                  width: '100%', background: 'transparent', border: 'none',
                  outline: 'none', fontSize: 12, color: '#1e3a5f',
                  fontWeight: 500, cursor: 'text',
                }}
              />
            </td>

            {/* Control Origen — cicla con click */}
            <td
              onClick={() => cycleControl(pIdx, spIdx, sp.control_origen_codigo)}
              style={{
                border: '1px solid #9ca3af',
                backgroundColor: getControlColor(sp.control_origen_codigo),
                padding: '5px 10px', textAlign: 'center', verticalAlign: 'middle',
                fontWeight: 600, fontSize: 11, cursor: 'pointer', userSelect: 'none',
              }}
              title="Click para cambiar"
            >
              {sp.control_origen_codigo}
            </td>

            {/* B2C — toggleable */}
            {['Movil','HFC','FTTH','Neutra'].map(tec => (
              <EditBoolCell
                key={`b2c-${tec}`}
                value={sp.habilitado.B2C[tec]}
                onClick={() => toggleBool(pIdx, spIdx, 'B2C', tec)}
              />
            ))}

            {/* B2B — toggleable */}
            {['Movil','HFC','FTTH','Neutra'].map(tec => (
              <EditBoolCell
                key={`b2b-${tec}`}
                value={sp.habilitado.B2B[tec]}
                onClick={() => toggleBool(pIdx, spIdx, 'B2B', tec)}
              />
            ))}

            {/* 👉 NUEVA COLUMNA: eliminar fila */}
            <td style={{
              border: '1px solid #9ca3af',
              textAlign: 'center',
              backgroundColor: SUBPROC_BG
            }}>
              <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                
                {/* ➖ Eliminar */}
                <button
                  onClick={() => removeSubproceso(pIdx, spIdx)}
                  style={{
                    background: '#dc3545',
                    color: 'white',
                    border: 'none',
                    width: 24,
                    height: 24,
                    borderRadius: 4,
                    cursor: 'pointer',
                    fontWeight: 'bold'
                  }}
                  title="Eliminar fila"
                >
                  -
                </button>

                {/* ➕ Agregar debajo */}
                <button
                  onClick={() => addSubprocesoBelow(pIdx, spIdx)}
                  style={{
                    background: '#28a745',
                    color: 'white',
                    border: 'none',
                    width: 24,
                    height: 24,
                    borderRadius: 4,
                    cursor: 'pointer',
                    fontWeight: 'bold'
                  }}
                  title="Agregar debajo"
                >
                  +
                </button>

              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function MatrizProcesos({ onBack }) {
  const [matrizJson, setMatrizJson] = useState(null);
  const [editData, setEditData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

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
        setEditData(JSON.parse(JSON.stringify(data.procesos))); // copia editable
      })
      .catch((err) => {
        console.error("Error cargando matriz:", err);
      });
  }, []);

  const handleApply = async () => {
    setSaving(true);
    setSaveMsg('');
    try {
      const res = await fetch('/api/matriz', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ procesos: editData }),
      });
      if (!res.ok) throw new Error('Error al guardar');
      setMatrizJson(JSON.parse(JSON.stringify(editData)));
      setSaveMsg('✓ Cambios aplicados correctamente');
    } catch (e) {
      setSaveMsg('✗ Error al guardar los cambios');
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(''), 3000);
    }
  };

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
          {editData ? (
            <MatrizTable data={editData} setData={setEditData} />
          ) : (
            <p className="text-sm text-gray-400">Cargando matriz...</p>
          )}
        </div>

        {/* Botón Aplicar cambios */}
        {editData && (
          <div className="mt-4 flex items-center gap-4">
            <button
              onClick={handleApply}
              disabled={saving}
              className={`px-5 py-2 rounded-lg text-sm font-semibold text-white transition-colors
                ${saving ? 'bg-gray-400 cursor-not-allowed' : 'bg-[#1e3a5f] hover:bg-[#162d4a]'}`}
            >
              {saving ? 'Guardando...' : 'Aplicar cambios'}
            </button>
            {saveMsg && (
              <span className={`text-sm font-medium ${saveMsg.startsWith('✓') ? 'text-green-600' : 'text-red-600'}`}>
                {saveMsg}
              </span>
            )}
          </div>
        )}
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