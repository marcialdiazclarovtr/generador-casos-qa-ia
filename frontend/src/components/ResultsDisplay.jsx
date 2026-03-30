import React from 'react';
import { FileDown, FileSpreadsheet, FileText, Clock } from 'lucide-react';

const ResultsDisplay = ({ files }) => {
    if (!files || files.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-10 text-center">
                <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
                    <FileDown className="w-5 h-5 text-gray-300" />
                </div>
                <p className="text-sm text-gray-400 font-medium">Sin archivos generados</p>
                <p className="text-xs text-gray-300 mt-1">Los resultados aparecerán aquí</p>
            </div>
        );
    }

    const getIcon = (name) => {
        if (name.endsWith('.xlsx')) return <FileSpreadsheet className="w-4 h-4 text-green-600" />;
        if (name.endsWith('.csv')) return <FileText className="w-4 h-4 text-blue-500" />;
        return <FileDown className="w-4 h-4 text-gray-400" />;
    };

    const formatDate = (mtime) => {
        const d = new Date(mtime * 1000);
        return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    };

    return (
        <div className="space-y-2">
            {files.map((file) => (
                <a
                    key={file.name}
                    href={`${file.path}`}
                    download={file.name}
                    className="group flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:border-red-200 hover:bg-red-50/40 transition-all duration-150"
                >
                    <div className="p-2 bg-gray-50 rounded-lg group-hover:bg-white transition-colors shrink-0">
                        {getIcon(file.name)}
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-gray-800 truncate group-hover:text-[#DA291C] transition-colors">
                            {file.name}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                            <Clock className="w-3 h-3 text-gray-300" />
                            <span className="text-[10px] text-gray-400">{formatDate(file.mtime)}</span>
                            <span className="text-[10px] text-gray-300">·</span>
                            <span className="text-[10px] text-gray-400">{(file.size / 1024).toFixed(0)} KB</span>
                        </div>
                    </div>
                    <FileDown className="w-4 h-4 text-gray-300 group-hover:text-[#DA291C] transition-colors shrink-0" />
                </a>
            ))}
        </div>
    );
};

export default ResultsDisplay;
