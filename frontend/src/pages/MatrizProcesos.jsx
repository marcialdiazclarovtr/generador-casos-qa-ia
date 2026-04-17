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

const btnStyle = (color) => ({
  background: color,
  color: 'white',
  border: 'none',
  width: 18,
  height: 18,
  borderRadius: 3,
  cursor: 'pointer',
  fontWeight: 'bold',
  fontSize: 12,
  lineHeight: '18px',
  padding: 0,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
});

function ColHeader({ label, bgColor, textColor = '#fff', onAdd, onRemove, editable = false, onRename, fontSize = 11 }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(label);

  useEffect(() => {
    if (!editing) setVal(label);
  }, [label, editing]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
      {editable && editing ? (
        <input
          autoFocus
          value={val}
          onChange={e => setVal(e.target.value)}
          onBlur={() => { setEditing(false); onRename && onRename(val); }}
          onKeyDown={e => { if (e.key === 'Enter') { setEditing(false); onRename && onRename(val); } }}
          style={{ width: 80, fontSize, textAlign: 'center', border: '1px solid #ccc', borderRadius: 3, padding: '1px 4px', color: '#1e3a5f', backgroundColor: '#ffffff' }}
        />
      ) : (
        <span
          onClick={() => editable && setEditing(true)}
          style={{ cursor: editable ? 'pointer' : 'default', fontSize, fontWeight: 600, color: textColor }}
          title={editable ? 'Click para renombrar' : ''}
        >
          {label}
        </span>
      )}
      <div style={{ display: 'flex', gap: 3 }}>
        {onRemove && <button style={btnStyle('#dc3545')} onClick={onRemove} title="Eliminar columna">−</button>}
        {onAdd    && <button style={btnStyle('#28a745')} onClick={onAdd}    title="Agregar columna">+</button>}
      </div>
    </div>
  );
}

function MatrizTable({ data, setData }) {
  const CICLO_CONTROL = ['Ambas', 'VT', 'CL'];

  // ── Leer segmentos y tecnologías dinámicamente del JSON ──
  const getSegmentos = () => {
    for (const p of data) {
      for (const sp of p.subprocesos) {
        if (sp.habilitado) return Object.keys(sp.habilitado);
      }
    }
    return [];
  };

  const getTecnologias = (segmento) => {
    for (const p of data) {
      for (const sp of p.subprocesos) {
        if (sp.habilitado?.[segmento]) return Object.keys(sp.habilitado[segmento]);
      }
    }
    return [];
  };

  const segmentos = getSegmentos();

  // ── Columnas extra de Proceso, Subproceso y Control ──────────────
  // Se derivan leyendo las claves del JSON dinámicamente
  const getExtraProcesoKeys = () => {
    const keys = [];
    data.forEach(p => {
      Object.keys(p).forEach(k => {
        if (k.startsWith('proceso_') && !keys.includes(k)) keys.push(k);
      });
    });
    return keys.sort();
  };

  const getExtraSubprocesoKeys = () => {
    const keys = [];
    data.forEach(p => p.subprocesos.forEach(sp => {
      Object.keys(sp).forEach(k => {
        if (k.startsWith('subproceso_') && !keys.includes(k)) keys.push(k);
      });
    }));
    return keys.sort();
  };

  const getExtraControlKeys = () => {
    const keys = [];
    data.forEach(p => p.subprocesos.forEach(sp => {
      Object.keys(sp).forEach(k => {
        if (k.startsWith('control_origen_codigo_') && !keys.includes(k)) keys.push(k);
      });
    }));
    return keys.sort();
  };

  const extraProcesoKeys   = getExtraProcesoKeys();
  const extraSubprocesoKeys = getExtraSubprocesoKeys();
  const extraControlKeys   = getExtraControlKeys();

  // Estados para cambiar nombre de columnas nuevas genereadas a partir de encabezados Proceso N1, Procedimiento (SubProceso) N2, y Control (Origen)
  const [headerLabels, setHeaderLabels] = useState(() => {
    try {
      const saved = localStorage.getItem('matrizHeaderLabels');
      return saved ? JSON.parse(saved) : {};
    } catch { return {}; }
  });

  const getHeaderLabel = (key, defaultLabel) => headerLabels[key] ?? defaultLabel;
  const setHeaderLabel = (key, label) => {
    setHeaderLabels(prev => {
      const next = { ...prev, [key]: label };
      try { localStorage.setItem('matrizHeaderLabels', JSON.stringify(next)); } catch {}
      return next;
    });
  };

  // ── Columnas base visibles (se puede ocultar/mostrar cada una) ───
  // Se guarda en data como metadato _columnas_ocultas en el primer proceso
  const COLUMNAS_BASE = ['proceso', 'subproceso', 'control'];

  const getColumnasOcultas = () => {
    return data[0]?._columnas_ocultas ?? [];
  };

  const columnasOcultas = getColumnasOcultas();
  const mostrarProceso    = !columnasOcultas.includes('proceso');
  const mostrarSubproceso = !columnasOcultas.includes('subproceso');
  const mostrarControl    = !columnasOcultas.includes('control');

  const ocultarColumnaBase = (col) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      const ocultas = next[0]._columnas_ocultas ?? [];
      if (!ocultas.includes(col)) ocultas.push(col);
      next[0]._columnas_ocultas = ocultas;
      return next;
    });
  };

  // Renombrar columna proceso
  const renameColumnaProceso = (key, newValue) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => { if (p[key] !== undefined) p[key] = newValue; });
      return next;
    });
  };

  // ── Helpers de mutación ──────────────────────────────────
  const updateSubproceso = (pIdx, spIdx, field, value) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[pIdx].subprocesos[spIdx][field] = value;
      return next;
    });
  };

  const updateProceso = (pIdx, value) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[pIdx].proceso = value;
      return next;
    });
  };

  const toggleBool = (pIdx, spIdx, segmento, tec) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[pIdx].subprocesos[spIdx].habilitado[segmento][tec] =
        !next[pIdx].subprocesos[spIdx].habilitado[segmento][tec];
      return next;
    });
  };

  const cycleControl = (pIdx, spIdx, current) => {
    const nextVal = CICLO_CONTROL[(CICLO_CONTROL.indexOf(current) + 1) % CICLO_CONTROL.length];
    updateSubproceso(pIdx, spIdx, 'control_origen_codigo', nextVal);
  };

  // ── Agregar / eliminar filas ─────────────────────────────
  const addProcesoBelow = (pIdx) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      const habilitado = {};
      getSegmentos().forEach(seg => {
        habilitado[seg] = {};
        getTecnologias(seg).forEach(tec => { habilitado[seg][tec] = true; });
      });
      next.splice(pIdx + 1, 0, {
        proceso: 'Nuevo Proceso',
        subprocesos: [{ subproceso: '', control_origen_codigo: 'Ambas', habilitado }]
      });
      return next;
    });
  };

  const removeProceso = (pIdx) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.splice(pIdx, 1);
      return next;
    });
  };

  const addSubprocesoBelow = (pIdx, spIdx) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      const habilitado = {};
      getSegmentos().forEach(seg => {
        habilitado[seg] = {};
        getTecnologias(seg).forEach(tec => { habilitado[seg][tec] = true; });
      });

      // Construir el nuevo subproceso con el mismo orden de claves que los existentes
      const nuevoSp = { subproceso: '' };
      // Agregar claves subproceso_N en orden
      extraSubprocesoKeys.forEach(k => { nuevoSp[k] = ''; });
      nuevoSp.control_origen_codigo = 'Ambas';
      // Agregar claves control_origen_codigo_N en orden
      extraControlKeys.forEach(k => { nuevoSp[k] = 'Ambas'; });
      nuevoSp.habilitado = habilitado;

      next[pIdx].subprocesos.splice(spIdx + 1, 0, nuevoSp);
      return next;
    });
  };

  const removeSubproceso = (pIdx, spIdx) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[pIdx].subprocesos.splice(spIdx, 1);
      if (next[pIdx].subprocesos.length === 0) next.splice(pIdx, 1);
      return next;
    });
  };

  // Funciones para agregar o eliminar columnas proceso / subproceso / control
  const addColumnaProceso = () => {
    const existingNums = extraProcesoKeys
      .map(k => parseInt(k.replace('proceso_', ''), 10))
      .filter(n => !isNaN(n));
    const nextNum = existingNums.length > 0 ? Math.max(...existingNums) + 1 : 2;
    const newKey = `proceso_${nextNum}`;
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        const reordered = { proceso: p.proceso };
        // agregar todas las claves proceso_N existentes
        Object.keys(p).forEach(k => {
          if (k.startsWith('proceso_')) reordered[k] = p[k];
        });
        // agregar la nueva
        reordered[newKey] = 'Sin nombre';
        // agregar el resto (subprocesos, _columnas_ocultas, etc.)
        Object.keys(p).forEach(k => {
          if (k !== 'proceso' && !k.startsWith('proceso_')) reordered[k] = p[k];
        });
        Object.keys(p).forEach(k => delete p[k]);
        Object.assign(p, reordered);
      });
      return next;
    });
  };

  const removeColumnaProceso = (key) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => { delete p[key]; });
      return next;
    });
  };

  const updateColumnaProceso = (pIdx, key, value) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[pIdx][key] = value;
      return next;
    });
  };

  const addColumnaSubproceso = () => {
    const existingNums = extraSubprocesoKeys
      .map(k => parseInt(k.replace('subproceso_', ''), 10))
      .filter(n => !isNaN(n));
    const nextNum = existingNums.length > 0 ? Math.max(...existingNums) + 1 : 2;
    const newKey = `subproceso_${nextNum}`;
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          const reordered = {};
          Object.keys(sp).forEach(k => {
            reordered[k] = sp[k];
            if (k === 'subproceso') reordered[newKey] = sp.subproceso;
          });
          Object.keys(sp).forEach(k => delete sp[k]);
          Object.assign(sp, reordered);
        });
      });
      return next;
    });
  };

  const removeColumnaSubproceso = (key) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => p.subprocesos.forEach(sp => { delete sp[key]; }));
      return next;
    });
  };

  const renameColumnaSubproceso = (oldKey, newName) => {
    const newKey = `sp__${newName}`;
    if (!newName || newKey === oldKey) return;
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          if (sp[oldKey] !== undefined) {
            const reordered = {};
            Object.keys(sp).forEach(k => {
              reordered[k === oldKey ? newKey : k] = sp[k];
            });
            Object.keys(sp).forEach(k => delete sp[k]);
            Object.assign(sp, reordered);
          }
        });
      });
      return next;
    });
  };

  const updateColumnaSubproceso = (pIdx, spIdx, key, value) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[pIdx].subprocesos[spIdx][key] = value;
      return next;
    });
  };
  
  const addColumnaControl = () => {
    const existingNums = extraControlKeys
      .map(k => parseInt(k.replace('control_origen_codigo_', ''), 10))
      .filter(n => !isNaN(n));
    const nextNum = existingNums.length > 0 ? Math.max(...existingNums) + 1 : 2;
    const newKey = `control_origen_codigo_${nextNum}`;
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          const reordered = {};
          Object.keys(sp).forEach(k => {
            reordered[k] = sp[k];
            if (k === 'control_origen_codigo') reordered[newKey] = sp.control_origen_codigo;
          });
          Object.keys(sp).forEach(k => delete sp[k]);
          Object.assign(sp, reordered);
        });
      });
      return next;
    });
  };

  const removeColumnaControl = (key) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => p.subprocesos.forEach(sp => { delete sp[key]; }));
      return next;
    });
  };

  const renameColumnaControl = (oldKey, newName) => {
    const newKey = `ctrl__${newName}`;
    if (!newName || newKey === oldKey) return;
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          if (sp[oldKey] !== undefined) {
            const reordered = {};
            Object.keys(sp).forEach(k => {
              reordered[k === oldKey ? newKey : k] = sp[k];
            });
            Object.keys(sp).forEach(k => delete sp[k]);
            Object.assign(sp, reordered);
          }
        });
      });
      return next;
    });
  };

  const cycleControlExtra = (pIdx, spIdx, key, current) => {
    const nextVal = CICLO_CONTROL[(CICLO_CONTROL.indexOf(current) + 1) % CICLO_CONTROL.length];
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next[pIdx].subprocesos[spIdx][key] = nextVal;
      return next;
    });
  };

  // ── Agregar / eliminar SEGMENTO (B2C, B2B, nuevo...) ────
  const addSegmento = (afterSegmento) => {
    const newSeg = `Segmento_${Date.now()}`;
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          const tecs = getTecnologias(afterSegmento);
          const reordered = {};
          Object.keys(sp.habilitado).forEach(k => {
            reordered[k] = sp.habilitado[k];
            if (k === afterSegmento) {
              reordered[newSeg] = {};
              tecs.forEach(tec => { reordered[newSeg][tec] = false; });
            }
          });
          sp.habilitado = reordered;
        });
      });
      return next;
    });
  };

  const removeSegmento = (seg) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          delete sp.habilitado[seg];
        });
      });
      return next;
    });
  };

  // ── Renombrar segmento ───────────────────────────────────
  const renameSegmento = (oldName, newName) => {
    if (!newName || newName === oldName) return;
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          if (sp.habilitado[oldName] !== undefined) {
            const reordered = {};
            Object.keys(sp.habilitado).forEach(k => {
              if (k === oldName) {
                reordered[newName] = sp.habilitado[oldName];
              } else {
                reordered[k] = sp.habilitado[k];
              }
            });
            sp.habilitado = reordered;
          }
        });
      });
      return next;
    });
  };

  // ── Agregar / eliminar TECNOLOGÍA dentro de un segmento ──
  const addTecnologia = (segmento, afterTec) => {
    const newTec = `Col_${Date.now()}`;
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          if (sp.habilitado[segmento]) {
            const reordered = {};
            Object.keys(sp.habilitado[segmento]).forEach(k => {
              reordered[k] = sp.habilitado[segmento][k];
              if (k === afterTec) {
                reordered[newTec] = false;
              }
            });
            sp.habilitado[segmento] = reordered;
          }
        });
      });
      return next;
    });
  };

  const removeTecnologia = (segmento, tec) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          if (sp.habilitado[segmento]) {
            delete sp.habilitado[segmento][tec];
          }
        });
      });
      return next;
    });
  };

  // Funciones para eliminar las columnas "control origen", "Proceso N1" y "Procedimiento (SubProceso) N2" (atributos "control_origen_codigo", "proceso" y "subproceso" del json respectivamente) de forma permanente
  const eliminarColumnaControl = () => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          delete sp.control_origen_codigo;
          delete sp.control_origen_nombre;
          delete sp.control_origen_equivale_a;
        });
      });
      // También marcarla como oculta para que no se muestre
      const ocultas = next[0]._columnas_ocultas ?? [];
      if (!ocultas.includes('control')) ocultas.push('control');
      next[0]._columnas_ocultas = ocultas;
      return next;
    });
  };

  const eliminarColumnaProceso = () => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        delete p.proceso;
      });
      const ocultas = next[0]._columnas_ocultas ?? [];
      if (!ocultas.includes('proceso')) ocultas.push('proceso');
      next[0]._columnas_ocultas = ocultas;
      return next;
    });
  };

  const eliminarColumnaSubproceso = () => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          delete sp.subproceso;
        });
      });
      const ocultas = next[0]._columnas_ocultas ?? [];
      if (!ocultas.includes('subproceso')) ocultas.push('subproceso');
      next[0]._columnas_ocultas = ocultas;
      return next;
    });
  };

  // ── Renombrar tecnología ─────────────────────────────────
  const renameTecnologia = (segmento, oldTec, newTec) => {
    if (!newTec || newTec === oldTec) return;
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.forEach(p => {
        p.subprocesos.forEach(sp => {
          if (sp.habilitado[segmento] && sp.habilitado[segmento][oldTec] !== undefined) {
            const reordered = {};
            Object.keys(sp.habilitado[segmento]).forEach(k => {
              if (k === oldTec) {
                reordered[newTec] = sp.habilitado[segmento][oldTec];
              } else {
                reordered[k] = sp.habilitado[segmento][k];
              }
            });
            sp.habilitado[segmento] = reordered;
          }
        });
      });
      return next;
    });
  };

  // ── Aplanar filas ────────────────────────────────────────
  const rows = [];
  data.forEach((p, pIdx) => {
    p.subprocesos.forEach((sp, spIdx) => {
      rows.push({ p, pIdx, sp, spIdx, isFirst: spIdx === 0, rowspan: p.subprocesos.length });
    });
  });

  // ── Estilos base ─────────────────────────────────────────
  const thBase = {
    border: '1px solid #9ca3af',
    padding: '4px 8px',
    color: '#ffffff',
    fontWeight: '600',
    fontSize: 11,
    textAlign: 'center',
    verticalAlign: 'middle',
    whiteSpace: 'nowrap',
  };

  const totalTecCols = segmentos.reduce((acc, seg) => acc + getTecnologias(seg).length, 0);

  return (
    <table style={{ borderCollapse: 'collapse', fontSize: 12 }}>
      <thead>
        {/* ── FILA 1: encabezados principales ── */}
        <tr>
          {/* Proceso N1 */}
          {mostrarProceso && (
            <th rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE, minWidth: 100 }}>
              <ColHeader
                label={getHeaderLabel('__proceso', 'Proceso N1')}
                bgColor={DARK_BLUE}
                editable
                onRename={(newName) => setHeaderLabel('__proceso', newName)}
                onAdd={() => addColumnaProceso()}
                onRemove={() => eliminarColumnaProceso()}
              />
            </th>
          )}
          {extraProcesoKeys.map(key => (
            <th key={key} rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE, minWidth: 100 }}>
              <ColHeader
                label={getHeaderLabel(key, 'Nuevo Proceso N1')}
                bgColor={DARK_BLUE}
                editable
                onRename={(newName) => setHeaderLabel(key, newName)}
                onRemove={() => removeColumnaProceso(key)}
                onAdd={() => addColumnaProceso()}
              />
            </th>
          ))}

          {/* Procedimiento N2 */}
          {mostrarSubproceso && (
            <th rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE, minWidth: 160 }}>
              <ColHeader
                label={getHeaderLabel('__subproceso', 'Procedimiento (SubProceso) N2')}
                bgColor={DARK_BLUE}
                editable
                onRename={(newName) => setHeaderLabel('__subproceso', newName)}
                onAdd={() => addColumnaSubproceso()}
                onRemove={() => eliminarColumnaSubproceso()}
              />
            </th>
          )}
          {extraSubprocesoKeys.map(key => (
            <th key={key} rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE, minWidth: 160 }}>
              <ColHeader
                label={getHeaderLabel(key, 'Nueva columna')}
                bgColor={DARK_BLUE}
                editable
                onRename={(newName) => setHeaderLabel(key, newName)}
                onRemove={() => removeColumnaSubproceso(key)}
                onAdd={() => addColumnaSubproceso()}
              />
            </th>
          ))}

          {/* Control Origen */}
          {mostrarControl && (
            <th rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE, minWidth: 90 }}>
              <ColHeader
                label={getHeaderLabel('__control', 'Control (Origen)')}
                bgColor={DARK_BLUE}
                editable
                onRename={(newName) => setHeaderLabel('__control', newName)}
                onAdd={() => addColumnaControl()}
                onRemove={() => eliminarColumnaControl()}
              />
            </th>
          )}
          {extraControlKeys.map(key => (
            <th key={key} rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE, minWidth: 90 }}>
              <ColHeader
                label={getHeaderLabel(key, 'Nueva columna')}
                bgColor={DARK_BLUE}
                editable
                onRename={(newName) => setHeaderLabel(key, newName)}
                onRemove={() => removeColumnaControl(key)}
                onAdd={() => addColumnaControl()}
              />
            </th>
          ))}

          {/* Segmentos dinámicos */}
          {segmentos.map((seg, sIdx) => (
            <th
              key={seg}
              colSpan={getTecnologias(seg).length}
              style={{ ...thBase, backgroundColor: sIdx % 2 === 0 ? CELESTE : GREEN_DARK }}
            >
              <ColHeader
                label={seg}
                bgColor={sIdx % 2 === 0 ? CELESTE : GREEN_DARK}
                editable
                onRename={(newName) => renameSegmento(seg, newName)}
                onAdd={() => addSegmento(seg)}
                onRemove={segmentos.length > 1 ? () => removeSegmento(seg) : null}
              />
            </th>
          ))}

          {/* Acciones fila */}
          <th rowSpan={2} style={{ ...thBase, backgroundColor: DARK_BLUE, minWidth: 70 }}>
            Acciones
          </th>
        </tr>

        {/* ── FILA 2: subencabezados tecnologías ── */}
        <tr>
          {segmentos.map((seg, sIdx) => {
            const tecs = getTecnologias(seg);
            const subBg = sIdx % 2 === 0 ? CELESTE_SUB : GREEN_SUB;
            const subColor = sIdx % 2 === 0 ? '#1e3a5f' : '#1b5e20';
            return tecs.map((tec, tIdx) => (
              <th key={`${seg}-${tec}`} style={{ ...thBase, backgroundColor: subBg, color: subColor, minWidth: 60 }}>
                <ColHeader
                  label={tec}
                  bgColor={subBg}
                  textColor={subColor}
                  editable
                  onRename={(newName) => renameTecnologia(seg, tec, newName)}
                  onAdd={() => addTecnologia(seg, tec)}
                  onRemove={tecs.length > 1 ? () => removeTecnologia(seg, tec) : null}
                />
              </th>
            ));
          })}
        </tr>
      </thead>

      <tbody>
        {rows.map(({ p, pIdx, sp, spIdx, isFirst, rowspan }, i) => (
          <tr key={i}>
            {/* Proceso — rowspan, editable */}
            {isFirst && mostrarProceso && (
              <td rowSpan={rowspan} style={{
                border: '1px solid #9ca3af', backgroundColor: DARK_BLUE,
                color: '#fff', fontWeight: 600, fontSize: 12,
                padding: '6px 8px', textAlign: 'center', verticalAlign: 'middle',
              }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center' }}>
                  <input
                    value={p.proceso}
                    onChange={e => updateProceso(pIdx, e.target.value)}
                    style={{ width: '100%', background: 'transparent', border: 'none', outline: 'none', fontSize: 12, color: '#fff', fontWeight: 600, textAlign: 'center' }}
                  />
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button style={btnStyle('#dc3545')} onClick={() => removeProceso(pIdx)} title="Eliminar proceso">−</button>
                    <button style={btnStyle('#28a745')} onClick={() => addProcesoBelow(pIdx)} title="Agregar proceso">+</button>
                  </div>
                </div>
              </td>
            )}
            {isFirst && extraProcesoKeys.map(key => (
              <td key={key} rowSpan={rowspan} style={{
                border: '1px solid #9ca3af', backgroundColor: DARK_BLUE,
                color: '#fff', fontWeight: 600, fontSize: 12,
                padding: '6px 8px', textAlign: 'center', verticalAlign: 'middle',
              }}>
                <input
                  value={p[key] ?? ''}
                  onChange={e => updateColumnaProceso(pIdx, key, e.target.value)}
                  style={{ width: '100%', background: 'transparent', border: 'none', outline: 'none', fontSize: 12, color: '#fff', fontWeight: 600, textAlign: 'center' }}
                />
              </td>
            ))}

            {/* Subproceso */}
            {mostrarSubproceso && (
            <td style={{ border: '1px solid #9ca3af', backgroundColor: SUBPROC_BG, padding: '2px 6px', verticalAlign: 'middle' }}>
              <input
                value={sp.subproceso}
                onChange={e => updateSubproceso(pIdx, spIdx, 'subproceso', e.target.value)}
                style={{ width: '100%', background: 'transparent', border: 'none', outline: 'none', fontSize: 12, color: '#1e3a5f', fontWeight: 500 }}
              />
            </td>
            )}

            {extraSubprocesoKeys.map(key => (
              <td key={key} style={{ border: '1px solid #9ca3af', backgroundColor: SUBPROC_BG, padding: '2px 6px', verticalAlign: 'middle' }}>
                <input
                  value={sp[key] ?? ''}
                  onChange={e => updateColumnaSubproceso(pIdx, spIdx, key, e.target.value)}
                  style={{ width: '100%', background: 'transparent', border: 'none', outline: 'none', fontSize: 12, color: '#1e3a5f', fontWeight: 500 }}
                />
              </td>
            ))}

            {/* Control Origen */}
            {mostrarControl && (
            <td
              onClick={() => cycleControl(pIdx, spIdx, sp.control_origen_codigo)}
              style={{
                border: '1px solid #9ca3af',
                backgroundColor: getControlColor(sp.control_origen_codigo),
                padding: '5px 8px', textAlign: 'center', verticalAlign: 'middle',
                fontWeight: 600, fontSize: 11, cursor: 'pointer', userSelect: 'none',
              }}
              title="Click para cambiar"
            >
              {sp.control_origen_codigo}
            </td>
            )}

            {extraControlKeys.map(key => (
              <td
                key={key}
                onClick={() => cycleControlExtra(pIdx, spIdx, key, sp[key] ?? 'Ambas')}
                style={{
                  border: '1px solid #9ca3af',
                  backgroundColor: getControlColor(sp[key] ?? 'Ambas'),
                  padding: '5px 8px', textAlign: 'center', verticalAlign: 'middle',
                  fontWeight: 600, fontSize: 11, cursor: 'pointer', userSelect: 'none',
                }}
                title="Click para cambiar"
              >
                {sp[key] ?? 'Ambas'}
              </td>
            ))}

            {/* Celdas bool dinámicas */}
            {segmentos.map(seg =>
              getTecnologias(seg).map(tec => (
                <EditBoolCell
                  key={`${seg}-${tec}`}
                  value={sp.habilitado?.[seg]?.[tec] ?? false}
                  onClick={() => toggleBool(pIdx, spIdx, seg, tec)}
                />
              ))
            )}

            {/* Acciones fila */}
            <td style={{ border: '1px solid #9ca3af', textAlign: 'center', backgroundColor: SUBPROC_BG }}>
              <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                <button style={btnStyle('#dc3545')} onClick={() => removeSubproceso(pIdx, spIdx)} title="Eliminar subproceso">−</button>
                <button style={btnStyle('#28a745')} onClick={() => addSubprocesoBelow(pIdx, spIdx)} title="Agregar subproceso">+</button>
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