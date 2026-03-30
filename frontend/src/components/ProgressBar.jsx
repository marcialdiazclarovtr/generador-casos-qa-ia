import React, { useEffect, useRef, useState } from 'react';
import { Check, Loader2, AlertCircle, Upload, FileSearch, Cpu, CheckCircle2, Clock, BarChart3 } from 'lucide-react';

// ─── Steps ────────────────────────────────────────────────────────────────────
const STEPS = [
    { id: 'upload', label: 'Carga', icon: Upload, keywords: ['uploading', 'subiendo', 'iniciando'] },
    { id: 'docs', label: 'Documentos', icon: FileSearch, keywords: ['fase 1', 'procesando', 'convirtiendo', 'extrayendo', 'requerimientos', 'cargando', 'modelo configurado', 'módulos', 'conocimiento'] },
    { id: 'generate', label: 'Generación', icon: Cpu, keywords: ['fase 2', 'planificando', 'combinaciones', 'agente 1', 'agente 2', 'cabecera', 'detalle', 'caso #', 'caso 1', 'caso 2', 'caso 3', 'maestro', 'generando', 'incremental'] },
    { id: 'done', label: 'Completado', icon: CheckCircle2, keywords: ['completad', 'success', 'listo'] },
];

function detectStep(status, message) {
    if (status === 'success') return 3;
    if (status === 'uploading') return 0;
    if (!message) return 1;
    const lower = message.toLowerCase();
    for (let i = STEPS.length - 1; i >= 0; i--) {
        if (STEPS[i].keywords.some(k => lower.includes(k))) return i;
    }
    return 1;
}

// ─── Log entry ────────────────────────────────────────────────────────────────
function LogEntry({ text, isLatest }) {
    const isReasoning = text.includes('💭') || text.includes('Razonamiento');
    const isSuccess = text.includes('✅') || text.includes('✓');
    const isCase = text.includes('🎯') || text.includes('Caso #');

    return (
        <div className={`flex items-start gap-2.5 py-1.5 px-3 rounded transition-colors ${isLatest ? 'bg-red-50' :
            isReasoning ? 'bg-purple-50/50' :
                isCase ? 'bg-green-50/50' : ''
            }`}>
            <span className={`mt-0.5 text-xs shrink-0 font-mono ${isLatest ? 'text-red-500' :
                isReasoning ? 'text-purple-400' :
                    isSuccess ? 'text-green-400' : 'text-gray-300'
                }`}>›</span>
            <span className={`text-xs leading-relaxed ${isLatest ? 'text-gray-800 font-medium' :
                isReasoning ? 'text-purple-700' :
                    isCase ? 'text-green-700 font-medium' : 'text-gray-400'
                }`}>{text}</span>
            {isLatest && (
                <span className="ml-auto shrink-0 flex items-center gap-1 text-xs text-gray-400">
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                </span>
            )}
        </div>
    );
}

// ─── Step indicator ───────────────────────────────────────────────────────────
function Step({ step, index, currentStep, isSuccess, isError }) {
    const Icon = step.icon;
    const done = isSuccess || index < currentStep;
    const active = !isSuccess && index === currentStep;
    const pending = !isSuccess && index > currentStep;

    return (
        <div className="flex flex-col items-center gap-1.5">
            <div className={`
        w-9 h-9 rounded-full flex items-center justify-center border-2 transition-all duration-400
        ${done ? 'bg-red-600 border-red-600 text-white shadow-sm shadow-red-200' :
                    active && isError ? 'bg-red-50 border-red-400 text-red-500' :
                        active ? 'bg-white border-red-600 text-red-600 shadow-sm' :
                            'bg-white border-gray-200 text-gray-300'}
      `}>
                {done ? (
                    <Check className="w-4 h-4" strokeWidth={2.5} />
                ) : active && isError ? (
                    <AlertCircle className="w-4 h-4" />
                ) : active ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                    <Icon className="w-4 h-4" />
                )}
            </div>
            <span className={`text-[10px] font-semibold uppercase tracking-wider transition-colors ${done ? 'text-red-600' : active ? 'text-gray-700' : 'text-gray-300'
                }`}>{step.label}</span>
        </div>
    );
}

// ─── Helpers de formato ──────────────────────────────────────────────────────
function formatTime(seconds) {
    if (!seconds || seconds < 0) return '0s';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatTokens(n) {
    if (!n) return '0';
    return n.toLocaleString('es-CL');
}

// ─── Main ─────────────────────────────────────────────────────────────────────
const ProgressBar = ({ status, message, logEntries, elapsedTime, tokenUsage, queuePosition }) => {
    const [log, setLog] = useState([]);
    const logContainerRef = useRef(null);

    // Si viene logEntries del backend (log completo), usarlo directamente
    useEffect(() => {
        if (logEntries && logEntries.length > 0) {
            setLog(logEntries);
        }
    }, [logEntries]);

    // Fallback: si no hay logEntries, construir log desde messages individuales
    useEffect(() => {
        if (logEntries && logEntries.length > 0) return; // Ya usando logEntries
        if (!message || status === 'idle') return;
        setLog(prev => {
            if (prev.length > 0 && prev[prev.length - 1] === message) return prev;
            return [...prev.slice(-49), message];
        });
    }, [message, logEntries]);

    useEffect(() => {
        if (status === 'uploading') setLog([]);
    }, [status]);

    useEffect(() => {
        // Scroll solo dentro del contenedor de log, NO la página entera
        if (logContainerRef.current) {
            logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }
    }, [log]);

    if (status === 'idle') return null;

    const currentStep = detectStep(status, message);
    const isSuccess = status === 'success';
    const isError = status === 'error';

    const isQueued = status === 'queued';
    const pct = isSuccess ? 100 : isError ? 0 : isQueued ? 3 :
        status === 'uploading' ? 8 :
            Math.min(8 + (currentStep / (STEPS.length - 1)) * 88, 94);

    return (
        <div className="w-full bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">

            {/* Header strip */}
            <div className={`h-1 w-full transition-all duration-700 ${isSuccess ? 'bg-green-500' : isError ? 'bg-red-500' : 'bg-red-600'
                }`} style={{ width: `${pct}%` }} />

            <div className="p-5">
                {/* Title + badge */}
                <div className="flex items-center justify-between mb-5">
                    <h4 className="text-sm font-semibold text-gray-700">Progreso de generación</h4>
                    <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${isSuccess ? 'bg-green-50 text-green-700 border-green-200' :
                        isError ? 'bg-red-50 text-red-700 border-red-200' :
                            'bg-gray-50 text-gray-600 border-gray-200'
                        }`}>
                        {!isSuccess && !isError && <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />}
                        {isSuccess ? '✓ Completado' : isError ? '✗ Error' : isQueued ? 'En cola' : 'En proceso'}
                    </span>
                </div>

                {/* Queue waiting banner */}
                {isQueued && (
                    <div className="flex items-center gap-3 mb-5 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg">
                        <Loader2 className="w-5 h-5 text-amber-500 animate-spin" />
                        <div>
                            <p className="text-sm font-semibold text-amber-700">
                                En cola de espera
                            </p>
                            <p className="text-xs text-amber-600 mt-0.5">
                                {queuePosition > 0
                                    ? `Posicion ${queuePosition} en la cola. Tu tarea se ejecutara automaticamente.`
                                    : 'Preparando ejecucion...'}
                            </p>
                        </div>
                    </div>
                )}

                {/* Steps */}
                <div className="relative flex justify-between items-start mb-5">
                    {/* connector */}
                    <div className="absolute top-[1.1rem] left-[1.1rem] right-[1.1rem] h-px bg-gray-100" />
                    <div
                        className="absolute top-[1.1rem] left-[1.1rem] h-px bg-red-500 transition-all duration-700"
                        style={{ width: `calc(${isSuccess ? 100 : (currentStep / (STEPS.length - 1)) * 100}% - 2.2rem)` }}
                    />
                    {STEPS.map((step, i) => (
                        <Step key={step.id} step={step} index={i} currentStep={currentStep} isSuccess={isSuccess} isError={isError} />
                    ))}
                </div>

                {/* Metricas: Timer + Tokens */}
                {(elapsedTime > 0 || (tokenUsage && tokenUsage.total_tokens > 0)) && (
                    <div className="flex items-center gap-4 mb-4 px-1">
                        <div className="flex items-center gap-1.5 text-xs text-gray-600 bg-gray-100 px-3 py-1.5 rounded-lg">
                            <Clock className="w-3.5 h-3.5 text-gray-400" />
                            <span className="font-medium">{formatTime(elapsedTime)}</span>
                        </div>
                        {tokenUsage && tokenUsage.total_tokens > 0 && (
                            <div className="flex items-center gap-1.5 text-xs text-gray-600 bg-gray-100 px-3 py-1.5 rounded-lg">
                                <BarChart3 className="w-3.5 h-3.5 text-gray-400" />
                                <span className="font-medium">{formatTokens(tokenUsage.total_tokens)} tokens</span>
                                <span className="text-gray-400 text-[10px]">
                                    ({formatTokens(tokenUsage.prompt_tokens)} in / {formatTokens(tokenUsage.completion_tokens)} out)
                                </span>
                            </div>
                        )}
                    </div>
                )}

                {/* Log */}
                <div className="rounded-lg border border-gray-100 bg-gray-50 overflow-hidden">
                    <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-100 bg-white">
                        <span className="text-xs text-gray-400 font-mono">Registro de actividad</span>
                        {!isSuccess && !isError && (
                            <span className="ml-auto text-xs text-green-600 font-medium flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                                en vivo
                            </span>
                        )}
                    </div>
                    <div ref={logContainerRef} className="h-48 overflow-y-auto py-1 scrollbar-thin">
                        {log.length === 0 ? (
                            <p className="text-xs text-gray-400 px-3 py-2 font-mono">Esperando inicio...</p>
                        ) : (
                            log.map((entry, i) => (
                                <LogEntry key={i} text={entry} isLatest={i === log.length - 1} />
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ProgressBar;
