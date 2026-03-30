import React, { useState, useEffect } from 'react';
import { Table2, ChevronDown, ChevronUp, Eye, X, Loader2 } from 'lucide-react';
import { getCases } from '../api/client';

/**
 * Tabla de casos de prueba generados.
 * Carga el CSV parseado desde /api/cases y lo muestra como tabla interactiva.
 */
const CasesTable = ({ session }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [expandedRow, setExpandedRow] = useState(null);
    const [sortField, setSortField] = useState(null);
    const [sortAsc, setSortAsc] = useState(true);

    useEffect(() => {
        if (!session) return;
        setLoading(true);
        getCases(session)
            .then(setData)
            .catch((e) => setError(e.response?.data?.detail || 'Error cargando casos'))
            .finally(() => setLoading(false));
    }, [session]);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-10 text-gray-400">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                Cargando casos de prueba...
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center py-8 text-sm text-gray-400">
                {error}
            </div>
        );
    }

    if (!data || !data.cases || data.cases.length === 0) {
        return (
            <div className="text-center py-8 text-sm text-gray-400">
                Sin casos de prueba
            </div>
        );
    }

    // Columnas principales para la tabla compacta
    const mainCols = ['ID', 'Tipo Caso de Prueba', 'Prioridad', 'Marca', 'Tecnología', 'Proceso', 'SubProceso'];
    // Columnas de detalle (texto largo) — se muestran al expandir
    const detailCols = ['Servicios', 'Precondiciones', 'Descripción', 'Paso a Paso', 'Resultado Esperado', 'Datos de Prueba'];

    const cases = [...data.cases];

    // Sorting
    if (sortField) {
        cases.sort((a, b) => {
            const va = (a[sortField] || '').toLowerCase();
            const vb = (b[sortField] || '').toLowerCase();
            return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
        });
    }

    return (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Header */}
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Table2 className="w-4 h-4 text-[#DA291C]" />
                    <h3 className="text-sm font-semibold text-gray-700">
                        Casos de Prueba
                    </h3>
                    <span className="text-xs bg-red-50 text-[#DA291C] font-bold px-2 py-0.5 rounded-full">
                        {data.total}
                    </span>
                </div>
                <span className="text-xs text-gray-400">{session}</span>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
                <table className="w-full text-xs">
                    <thead>
                        <tr className="bg-gray-50/80 border-b border-gray-100">
                            <th className="w-8 px-2 py-2"></th>
                            {mainCols.map((col) => (
                                <th
                                    key={col}
                                    onClick={() => {
                                        if (sortField === col) setSortAsc(!sortAsc);
                                        else { setSortField(col); setSortAsc(true); }
                                    }}
                                    className="px-3 py-2 text-left font-semibold text-gray-500 cursor-pointer hover:text-gray-800 select-none whitespace-nowrap"
                                >
                                    <span className="flex items-center gap-1">
                                        {col}
                                        {sortField === col && (
                                            sortAsc
                                                ? <ChevronUp className="w-3 h-3" />
                                                : <ChevronDown className="w-3 h-3" />
                                        )}
                                    </span>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {cases.map((row, idx) => (
                            <React.Fragment key={idx}>
                                <tr
                                    onClick={() => setExpandedRow(expandedRow === idx ? null : idx)}
                                    className={`
                                        border-b border-gray-50 cursor-pointer transition-colors
                                        ${expandedRow === idx
                                            ? 'bg-red-50/60'
                                            : 'hover:bg-gray-50/60'}
                                    `}
                                >
                                    <td className="px-2 py-2 text-center">
                                        <Eye className={`w-3.5 h-3.5 transition-colors ${expandedRow === idx ? 'text-[#DA291C]' : 'text-gray-300'}`} />
                                    </td>
                                    {mainCols.map((col) => (
                                        <td key={col} className="px-3 py-2 text-gray-700 whitespace-nowrap max-w-[160px] truncate">
                                            {row[col] || '—'}
                                        </td>
                                    ))}
                                </tr>
                                {/* Expanded detail */}
                                {expandedRow === idx && (
                                    <tr>
                                        <td colSpan={mainCols.length + 1} className="bg-gray-50/40 px-4 py-3">
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                {detailCols.map((col) => {
                                                    const val = row[col];
                                                    if (!val) return null;
                                                    return (
                                                        <div key={col} className="bg-white rounded-lg border border-gray-100 p-3">
                                                            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
                                                                {col}
                                                            </p>
                                                            <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto scrollbar-thin">
                                                                {val}
                                                            </p>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); setExpandedRow(null); }}
                                                className="mt-2 text-[10px] text-gray-400 hover:text-red-500 flex items-center gap-1"
                                            >
                                                <X className="w-3 h-3" /> Cerrar detalle
                                            </button>
                                        </td>
                                    </tr>
                                )}
                            </React.Fragment>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default CasesTable;
