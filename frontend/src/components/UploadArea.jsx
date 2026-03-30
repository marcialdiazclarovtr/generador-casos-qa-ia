import React, { useState, useRef } from 'react';
import { Upload, FileText, X } from 'lucide-react';

const VALID_EXTS = [
    '.pdf', '.doc', '.docx', '.pptx', '.ppt', '.xlsx', '.xls',
    '.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp',
    '.txt', '.md',
];

const UploadArea = ({ onFilesSelected }) => {
    const [dragActive, setDragActive] = useState(false);
    const [files, setFiles] = useState([]);
    const inputRef = useRef(null);

    const handleDrag = (e) => {
        e.preventDefault(); e.stopPropagation();
        setDragActive(e.type === 'dragenter' || e.type === 'dragover');
    };

    const handleDrop = (e) => {
        e.preventDefault(); e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files?.[0]) processFiles(e.dataTransfer.files);
    };

    const processFiles = (raw) => {
        const valid = Array.from(raw).filter(f =>
            VALID_EXTS.includes(f.name.substring(f.name.lastIndexOf('.')).toLowerCase())
        );
        if (!valid.length) { alert('Formatos soportados: PDF, Word, PowerPoint, Excel, Imágenes, Texto'); return; }
        const next = [...files, ...valid];
        setFiles(next);
        onFilesSelected(next);
    };

    const removeFile = (i) => {
        const next = files.filter((_, idx) => idx !== i);
        setFiles(next);
        onFilesSelected(next);
    };

    return (
        <div className="w-full space-y-3">
            {/* Drop zone */}
            <div
                className={`
          relative flex flex-col items-center justify-center w-full h-36 border-2 border-dashed rounded-lg
          cursor-pointer transition-all duration-200
          ${dragActive
                        ? 'border-[#DA291C] bg-red-50'
                        : 'border-gray-200 bg-gray-50 hover:border-gray-300 hover:bg-white'}
        `}
                onDragEnter={handleDrag} onDragLeave={handleDrag}
                onDragOver={handleDrag} onDrop={handleDrop}
                onClick={() => inputRef.current.click()}
            >
                <input
                    ref={inputRef} type="file" className="hidden" multiple
                    accept=".pdf,.doc,.docx,.pptx,.ppt,.xlsx,.xls,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp,.txt,.md"
                    onChange={e => e.target.files?.[0] && processFiles(e.target.files)}
                />
                <div className={`p-3 rounded-full mb-2 transition-colors ${dragActive ? 'bg-red-100' : 'bg-white shadow-sm'}`}>
                    <Upload className={`w-5 h-5 ${dragActive ? 'text-[#DA291C]' : 'text-gray-400'}`} />
                </div>
                <p className="text-sm text-gray-600">
                    <span className="font-semibold text-[#DA291C]">Haz clic</span> o arrastra tus archivos
                </p>
                <p className="text-xs text-gray-400 mt-1">PDF, Word, PowerPoint, Excel, Imágenes</p>
            </div>

            {/* File list */}
            {files.length > 0 && (
                <div className="space-y-1.5">
                    {files.map((file, i) => (
                        <div key={`${file.name}-${i}`}
                            className="flex items-center gap-3 px-3 py-2 bg-white rounded-lg border border-gray-100 shadow-sm"
                        >
                            <div className="p-1.5 bg-red-50 rounded text-[#DA291C] shrink-0">
                                <FileText className="w-3.5 h-3.5" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium text-gray-800 truncate">{file.name}</p>
                                <p className="text-[10px] text-gray-400">{(file.size / 1024).toFixed(0)} KB</p>
                            </div>
                            <button
                                onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                                className="p-1 rounded hover:bg-gray-100 text-gray-300 hover:text-gray-500 transition-colors"
                            >
                                <X className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default UploadArea;
