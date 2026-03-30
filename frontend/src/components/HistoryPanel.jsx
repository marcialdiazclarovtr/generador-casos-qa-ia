import React, { useState, useEffect } from 'react';
import { History, FolderOpen, FileSpreadsheet, FileText, ChevronRight, Loader2, ArrowLeft } from 'lucide-react';
import { getSessions } from '../api/client';
import CasesTable from './CasesTable';

/**
 * Panel de historial: lista sesiones pasadas y permite ver sus casos.
 */
const HistoryPanel = ({ onClose }) => {
    const [sessions, setSessions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedSession, setSelectedSession] = useState(null);

    useEffect(() => {
        getSessions()
            .then(setSessions)
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    const formatDate = (mtime) => {
        if (!mtime) return '—';
        const d = new Date(mtime * 1000);
        return d.toLocaleDateString('es-CL', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    };

    // Vista detalle de una sesión
    if (selectedSession) {
        return (
            <div className="space-y-4">
                <button
                    onClick={() => setSelectedSession(null)}
                    className="flex items-center gap-2 text-sm text-gray-500 hover:text-[#DA291C] transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Volver al historial
                </button>

                <CasesTable session={selectedSession.name} />

                {/* Descargas */}
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
                    <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Descargar</h4>
                    <div className="flex gap-3">
                        {selectedSession.csv_path && (
                            <a
                                href={`${selectedSession.csv_path}`}
                                download="casos_prueba.csv"
                                className="flex items-center gap-2 px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg text-xs font-semibold transition-colors"
                            >
                                <FileText className="w-4 h-4" /> CSV
                            </a>
                        )}
                        {selectedSession.xlsx_path && (
                            <a
                                href={`${selectedSession.xlsx_path}`}
                                download="casos_prueba.xlsx"
                                className="flex items-center gap-2 px-4 py-2 bg-green-50 hover:bg-green-100 text-green-700 rounded-lg text-xs font-semibold transition-colors"
                            >
                                <FileSpreadsheet className="w-4 h-4" /> Excel
                            </a>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    // Lista de sesiones
    return (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <History className="w-4 h-4 text-[#DA291C]" />
                    <h3 className="text-sm font-semibold text-gray-700">Historial de Generaciones</h3>
                </div>
                {onClose && (
                    <button
                        onClick={onClose}
                        className="text-xs text-gray-400 hover:text-red-500"
                    >
                        Cerrar
                    </button>
                )}
            </div>

            {loading ? (
                <div className="flex items-center justify-center py-10 text-gray-400">
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    Cargando historial...
                </div>
            ) : sessions.length === 0 ? (
                <div className="text-center py-10 text-sm text-gray-400">
                    Sin generaciones previas
                </div>
            ) : (
                <div className="divide-y divide-gray-50">
                    {sessions.map((s) => (
                        <button
                            key={s.name}
                            onClick={() => setSelectedSession(s)}
                            className="w-full flex items-center gap-3 px-5 py-3 hover:bg-red-50/40 transition-colors text-left group"
                        >
                            <div className="p-2 bg-gray-50 rounded-lg group-hover:bg-white transition-colors shrink-0">
                                <FolderOpen className="w-4 h-4 text-amber-500" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-xs font-semibold text-gray-800 truncate group-hover:text-[#DA291C] transition-colors">
                                    {s.name}
                                </p>
                                <div className="flex items-center gap-3 mt-0.5">
                                    <span className="text-[10px] text-gray-400">
                                        {formatDate(s.mtime)}
                                    </span>
                                    <span className="text-[10px] font-bold text-[#DA291C] bg-red-50 px-1.5 py-0.5 rounded">
                                        {s.case_count} casos
                                    </span>
                                    {s.has_xlsx && (
                                        <span className="text-[10px] text-green-600">XLSX</span>
                                    )}
                                    {s.has_csv && (
                                        <span className="text-[10px] text-blue-500">CSV</span>
                                    )}
                                </div>
                            </div>
                            <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-[#DA291C] transition-colors shrink-0" />
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};

export default HistoryPanel;
