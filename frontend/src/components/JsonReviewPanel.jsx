import React, { useState } from 'react';
import { Sparkles, ChevronDown, ChevronRight, Save, Loader2, Edit3 } from 'lucide-react';

const FIELD_LABELS = {
    contexto: { label: 'Contexto del Proyecto', icon: '📋' },
    que_piden: { label: 'Qué se Pide', icon: '🎯' },
    causa_raiz: { label: 'Causa Raíz', icon: '🔍' },
    solucion: { label: 'Solución Propuesta', icon: '💡' },
    impacto_sistemas_bd: { label: 'Impacto en Sistemas', icon: '⚙️' },
    flujo: { label: 'Flujo del Proceso', icon: '🔄' },
    casos_prueba: { label: 'Sugerencias de Prueba', icon: '🧪' },
    validaciones_errores: { label: 'Validaciones y Errores', icon: '⚠️' },
    minimo_certificable: { label: 'Mínimo Certificable', icon: '✅' },
};

function CollapsibleSection({ fieldKey, items, onChange }) {
    const [open, setOpen] = useState(true);
    const [editing, setEditing] = useState(false);
    const meta = FIELD_LABELS[fieldKey] || { label: fieldKey, icon: '📝' };

    const text = Array.isArray(items) ? items.join('\n') : (items || '');
    const lineCount = text.split('\n').length;

    const handleChange = (e) => {
        const lines = e.target.value.split('\n');
        onChange(fieldKey, lines);
    };

    return (
        <div className="border border-gray-100 rounded-lg overflow-hidden">
            <button
                onClick={() => setOpen(!open)}
                className="w-full flex items-center gap-2 px-3 py-2.5 bg-gray-50 hover:bg-gray-100
                           text-left text-sm font-medium text-gray-700 transition-colors"
            >
                <span>{meta.icon}</span>
                {open ? <ChevronDown className="w-3.5 h-3.5 text-gray-400" /> :
                    <ChevronRight className="w-3.5 h-3.5 text-gray-400" />}
                <span className="flex-1">{meta.label}</span>
                {items && items.length > 0 && (
                    <span className="text-xs text-gray-400 font-normal">
                        {items.length} {items.length === 1 ? 'item' : 'items'}
                    </span>
                )}
                <button
                    onClick={(e) => { e.stopPropagation(); setEditing(!editing); }}
                    className="p-1 rounded hover:bg-white text-gray-400 hover:text-gray-600"
                    title={editing ? 'Ver' : 'Editar'}
                >
                    <Edit3 className="w-3 h-3" />
                </button>
            </button>

            {open && (
                <div className="px-3 py-2">
                    {editing ? (
                        <textarea
                            value={text}
                            onChange={handleChange}
                            rows={Math.max(3, Math.min(lineCount + 1, 12))}
                            className="w-full text-xs text-gray-700 font-mono bg-white border border-gray-200
                                       rounded p-2 resize-y focus:outline-none focus:ring-1 focus:ring-red-300
                                       focus:border-red-300"
                            placeholder="Escribe aquí..."
                        />
                    ) : (
                        <div className="space-y-1">
                            {(!items || items.length === 0) ? (
                                <p className="text-xs text-gray-400 italic">Sin información</p>
                            ) : (
                                items.map((item, i) => (
                                    <p key={i} className="text-xs text-gray-600 leading-relaxed">
                                        {item.startsWith('-') || item.startsWith('•') ? item : `• ${item}`}
                                    </p>
                                ))
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

const JsonReviewPanel = ({ jsonData, onJsonChange, onEnhance, onContinue, isEnhancing }) => {
    const [instructions, setInstructions] = useState('');

    if (!jsonData) return null;

    const handleFieldChange = (key, newValue) => {
        onJsonChange({ ...jsonData, [key]: newValue });
    };

    // Campos a mostrar (en orden)
    const fieldOrder = [
        'contexto', 'que_piden', 'solucion', 'impacto_sistemas_bd',
        'flujo', 'casos_prueba', 'validaciones_errores', 'causa_raiz',
        'minimo_certificable',
    ];

    const visibleFields = fieldOrder.filter(f => jsonData[f] !== undefined);

    return (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white">
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                            🤖 Agente 0 — Revisión del Requerimiento
                        </h3>
                        <p className="text-xs text-gray-400 mt-0.5">
                            Revisa y edita antes de generar los casos de prueba
                        </p>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="p-4 space-y-2 max-h-[60vh] overflow-y-auto scrollbar-thin">
                {visibleFields.map(key => (
                    <CollapsibleSection
                        key={key}
                        fieldKey={key}
                        items={jsonData[key]}
                        onChange={handleFieldChange}
                    />
                ))}
            </div>

            {/* Enhance with AI */}
            <div className="px-4 py-3 border-t border-gray-100 bg-gray-50 space-y-3">
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={instructions}
                        onChange={(e) => setInstructions(e.target.value)}
                        placeholder="Ej: Enfócate en red NEUTRA para B2C, prioriza Venta..."
                        className="flex-1 text-xs px-3 py-2 border border-gray-200 rounded-lg
                                   focus:outline-none focus:ring-1 focus:ring-red-300 focus:border-red-300"
                    />
                    <button
                        onClick={() => onEnhance(instructions)}
                        disabled={isEnhancing}
                        className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium
                                    transition-all ${isEnhancing
                                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                : 'bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100'
                            }`}
                    >
                        {isEnhancing ? (
                            <><Loader2 className="w-3 h-3 animate-spin" /> Mejorando...</>
                        ) : (
                            <><Sparkles className="w-3 h-3" /> Mejorar con IA</>
                        )}
                    </button>
                </div>

                <button
                    onClick={onContinue}
                    disabled={isEnhancing}
                    className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm
                                font-semibold transition-all ${isEnhancing
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                            : 'bg-[#DA291C] hover:bg-red-700 text-white shadow-sm'
                        }`}
                >
                    <Save className="w-4 h-4" />
                    Continuar con Generación
                </button>
            </div>
        </div>
    );
};

export default JsonReviewPanel;
