import React, { useState, useEffect, useRef } from 'react';
import { Loader2, Zap, AlertCircle, FileSearch, History } from 'lucide-react';
import UploadArea from './components/UploadArea';
import JsonReviewPanel from './components/JsonReviewPanel';
import ResultsDisplay from './components/ResultsDisplay';
import ProgressBar from './components/ProgressBar';
import CasesTable from './components/CasesTable';
import HistoryPanel from './components/HistoryPanel';
import {
  uploadFiles, processDocs, getDocResult, enhanceJson, getEnhanceResult,
  generateTestCases, getFiles, getGenerationStatus, cancelExecution
} from './api/client';

function App() {
  const [config, setConfig] = useState({
    model: 'gpt-oss:20b',
    lm_url: 'http://localhost:11434/v1',
    process_requirements: true,
    use_ocr: false,
    max_casos: 10,
  });

  // Estado del flujo: 'upload' → 'processing_docs' → 'review' → 'generating' → 'done'
  const [step, setStep] = useState('upload');
  const [files, setFiles] = useState([]);
  const [sessionFolder, setSessionFolder] = useState('');
  const [jsonData, setJsonData] = useState(null);
  const [userFocus, setUserFocus] = useState('');
  const [status, setStatus] = useState('idle');
  const [message, setMessage] = useState('');
  const [generatedFiles, setGeneratedFiles] = useState([]);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [isProcessingDocs, setIsProcessingDocs] = useState(false);
  const [statusLog, setStatusLog] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [tokenUsage, setTokenUsage] = useState(null);
  const [queuePosition, setQueuePosition] = useState(0);
  const timerRef = useRef(null);

  // ── Timer: cuenta cada segundo mientras isRunning ──
  const isRunning = status === 'uploading' || status === 'processing' || status === 'queued';

  useEffect(() => {
    if (isRunning) {
      timerRef.current = setInterval(() => {
        setElapsedTime(prev => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRunning]);

  // ── beforeunload: cancela backend y avisa al usuario ──
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isRunning && sessionFolder) {
        cancelExecution(sessionFolder);
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isRunning, sessionFolder]);

  const fetchFiles = async () => {
    if (!sessionFolder) { setGeneratedFiles([]); return; }
    try { setGeneratedFiles(await getFiles(sessionFolder)); }
    catch (e) { console.error(e); }
  };

  // ── Paso 1: Upload + Process Docs (background con polling) ──
  const handleProcessDocs = async () => {
    if (files.length === 0) {
      alert('Por favor carga al menos un archivo de requerimientos.');
      return;
    }
    try {
      setIsProcessingDocs(true);
      setStep('processing_docs');
      setStatus('uploading');
      setMessage('Subiendo archivos...');
      setStatusLog([]);
      setElapsedTime(0);
      setTokenUsage(null);

      const uploadResult = await uploadFiles(files);
      const session = uploadResult.session_folder;
      setSessionFolder(session);

      setStatus('processing');
      setMessage('Procesando documentos...');

      // Lanzar procesamiento en background
      await processDocs({
        ...config,
        session_folder: session,
      });

      // Polling hasta que state='doc_ready' o 'error'
      let polling = true;
      while (polling) {
        await new Promise(r => setTimeout(r, 1500));
        const s = await getGenerationStatus(session);

        if (s.log && s.log.length > 0) {
          setStatusLog(s.log);
          setMessage(s.log[s.log.length - 1]);
        } else if (s.message) {
          setMessage(s.message);
        }
        if (s.tokens) setTokenUsage(s.tokens);
        if (s.queue_position !== undefined) setQueuePosition(s.queue_position);

        if (s.state === 'queued') {
          setStatus('queued');
          setMessage(s.message || 'En cola de espera...');
        } else if (s.state === 'cancelled') {
          setStatus('idle');
          setMessage('Proceso cancelado.');
          setStep('upload');
          polling = false;
        } else if (s.state === 'processing') {
          setStatus('processing');
        } else if (s.state === 'doc_ready') {
          // Buscar el JSON generado
          try {
            const result = await getDocResult(session);
            if (result.json_data) {
              setJsonData(result.json_data);
              setStep('review');
              setStatus('idle');
              setMessage('');
            }
          } catch (e) {
            setStatus('error');
            setMessage('Error obteniendo JSON procesado');
          }
          polling = false;
        } else if (s.state === 'error') {
          setStatus('error');
          setMessage(s.message || 'Error procesando documentos');
          polling = false;
        }
      }
    } catch (err) {
      setStatus('error');
      setMessage(err.response?.data?.detail || err.message || 'Error');
    } finally {
      setIsProcessingDocs(false);
    }
  };

  // ── Paso 2: Enhance JSON (Agente 0, encolado) ──
  const handleEnhance = async (instructions) => {
    try {
      setIsEnhancing(true);
      // Guardar instrucciones para propagar a la generación
      if (instructions && instructions.trim()) {
        setUserFocus(instructions.trim());
      }
      await enhanceJson({
        json_data: jsonData,
        instructions,
        session_folder: sessionFolder,
      });

      // Polling hasta que state='enhance_ready' o 'error'
      let polling = true;
      while (polling) {
        await new Promise(r => setTimeout(r, 1500));
        const s = await getGenerationStatus(sessionFolder);

        if (s.state === 'enhance_ready') {
          try {
            const result = await getEnhanceResult(sessionFolder);
            if (result.json_data) {
              setJsonData(result.json_data);
            }
          } catch (_) { /* ignorar */ }
          polling = false;
        } else if (s.state === 'error') {
          alert('Error mejorando JSON: ' + (s.message || 'Error desconocido'));
          polling = false;
        } else if (s.state === 'queued') {
          // Sigue esperando en cola
        }
      }
    } catch (err) {
      alert('Error mejorando JSON: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsEnhancing(false);
    }
  };

  // ── Paso 3: Generate Test Cases ──
  const handleGenerate = async () => {
    try {
      setStep('generating');
      setStatus('processing');
      setMessage('Iniciando generación de casos...');
      setStatusLog([]);
      setElapsedTime(0);
      setTokenUsage(null);

      await generateTestCases({
        ...config,
        session_folder: sessionFolder,
        json_data: jsonData,
        user_focus: userFocus,
      });

      let polling = true;
      while (polling) {
        await new Promise(r => setTimeout(r, 1500));
        const s = await getGenerationStatus(sessionFolder);

        // Tomar el log completo del backend
        if (s.log && s.log.length > 0) {
          setStatusLog(s.log);
          setMessage(s.log[s.log.length - 1]);
        } else if (s.message) {
          setMessage(s.message);
        }
        if (s.tokens) setTokenUsage(s.tokens);
        if (s.queue_position !== undefined) setQueuePosition(s.queue_position);

        if (s.state === 'queued') {
          setStatus('queued');
          setMessage(s.message || 'En cola de espera...');
        } else if (s.state === 'processing') {
          setStatus('processing');
        } else if (s.state === 'cancelled') {
          setStatus('idle');
          setMessage('Proceso cancelado.');
          setStep('upload');
          polling = false;
        } else if (s.state === 'success') {
          setStatus('success');
          setMessage(s.message || '¡Completado!');
          setStep('done');
          await fetchFiles();
          polling = false;
        } else if (s.state === 'error') {
          setStatus('error');
          setMessage(s.message || 'Error desconocido');
          polling = false;
        }
      }
    } catch (err) {
      setStatus('error');
      setMessage(err.message || 'Error desconocido');
    }
  };

  const handleReset = () => {
    setStep('upload');
    setFiles([]);
    setSessionFolder('');
    setJsonData(null);
    setUserFocus('');
    setStatus('idle');
    setMessage('');
  };

  return (
    <div className="flex flex-col min-h-screen bg-gray-50 font-sans">

      {/* ── HEADER ─────────────────────────────────────────────────────── */}
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
            <img src="/logo_claro.png" alt="Claro" className="h-9 w-auto object-contain brightness-0 invert" />
            <div className="w-px h-6 bg-white/30" />
            <img src="/logo_vtr.png" alt="VTR" className="h-7 w-auto object-contain brightness-0 invert" />
          </div>
        </div>
      </header>

      {/* ── PAGE TITLE BAR ──────────────────────────────────────────────── */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">Automatización QA con IA</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Sistema multi-agente para generación de casos de prueba exhaustivos.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={`text-xs flex items-center gap-1.5 border px-3 py-1.5 rounded-lg transition-colors
                ${showHistory
                  ? 'text-[#DA291C] border-red-200 bg-red-50'
                  : 'text-gray-500 border-gray-200 hover:text-gray-700 hover:bg-gray-50'}`}
            >
              <History className="w-3.5 h-3.5" />
              Historial
            </button>
            {step !== 'upload' && (
              <button
                onClick={handleReset}
                className="text-xs text-gray-500 hover:text-gray-700 border border-gray-200
                           px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
              >
                ← Nuevo proceso
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── MAIN LAYOUT ─────────────────────────────────────────────────── */}
      <main className="flex-grow max-w-7xl mx-auto w-full px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">

          {/* ── LEFT PANEL ─────────────────────────────────────────────── */}
          <div className="lg:col-span-3 flex flex-col gap-5">

            {/* Step 1: Upload */}
            {step === 'upload' && (
              <>
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                  <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-700">
                      Paso 1 — Documentos de Requerimientos
                    </h3>
                    <span className="text-xs text-gray-400">PDF, DOCX, PPTX, Imágenes</span>
                  </div>
                  <div className="p-5">
                    <UploadArea onFilesSelected={setFiles} />
                  </div>
                </div>

                {/* Config */}
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-semibold text-gray-700">Máximo de Casos</label>
                    <span className="text-sm font-bold text-[#DA291C] bg-red-50 px-2 py-0.5 rounded">
                      {config.max_casos}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="50"
                    value={config.max_casos}
                    onChange={(e) => setConfig({ ...config, max_casos: parseInt(e.target.value) })}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#DA291C]"
                  />
                  <div className="flex justify-between text-xs text-gray-400 font-medium">
                    <span>1 caso</span>
                    <span>50 casos</span>
                  </div>
                </div>

                {/* Process button */}
                <button
                  onClick={handleProcessDocs}
                  disabled={files.length === 0 || isProcessingDocs}
                  className={`
                    w-full flex items-center justify-center gap-2.5 py-3 rounded-xl text-sm font-semibold
                    transition-all duration-200 shadow-sm
                    ${files.length > 0 && !isProcessingDocs
                      ? 'bg-[#DA291C] hover:bg-red-700 text-white shadow-red-200 hover:shadow-red-300 active:scale-[0.99]'
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'}
                  `}
                >
                  {isProcessingDocs ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Procesando documentos...</>
                  ) : (
                    <><FileSearch className="w-4 h-4" /> Procesar y Analizar</>
                  )}
                </button>
              </>
            )}

            {/* Step 1.5: Processing docs (shows ProgressBar with logs) */}
            {step === 'processing_docs' && (
              <>
                {status !== 'idle' && (
                  <ProgressBar status={status} message={message} logEntries={statusLog} elapsedTime={elapsedTime} tokenUsage={tokenUsage} queuePosition={queuePosition} />
                )}
                {status === 'error' && (
                  <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-semibold text-red-700">Error procesando documentos</p>
                      <p className="text-xs text-red-600 mt-0.5">{message}</p>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Step 2: JSON Review (Agent 0) */}
            {step === 'review' && (
              <JsonReviewPanel
                jsonData={jsonData}
                onJsonChange={setJsonData}
                onEnhance={handleEnhance}
                onContinue={handleGenerate}
                isEnhancing={isEnhancing}
              />
            )}

            {/* Step 3: Generating */}
            {(step === 'generating' || step === 'done') && (
              <>
                {status !== 'idle' && (
                  <ProgressBar status={status} message={message} logEntries={statusLog} elapsedTime={elapsedTime} tokenUsage={tokenUsage} queuePosition={queuePosition} />
                )}

                {status === 'error' && (
                  <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-semibold text-red-700">Error en el proceso</p>
                      <p className="text-xs text-red-600 mt-0.5">{message}</p>
                    </div>
                  </div>
                )}

                {/* Tabla de casos de prueba */}
                {step === 'done' && sessionFolder && (
                  <CasesTable session={sessionFolder} />
                )}
              </>
            )}

            {/* Historial */}
            {showHistory && (
              <HistoryPanel onClose={() => setShowHistory(false)} />
            )}
          </div>

          {/* ── RIGHT PANEL ────────────────────────────────────────────── */}
          <div className="lg:col-span-2 flex flex-col gap-5">

            {/* Generated files (solo sesión actual) */}
            {sessionFolder && generatedFiles.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-700">Descargar</h3>
                  <span className="text-xs font-medium text-white bg-[#DA291C] px-2 py-0.5 rounded-full">
                    {generatedFiles.length}
                  </span>
                </div>
                <div className="p-5">
                  <ResultsDisplay files={generatedFiles} />
                </div>
              </div>
            )}

            {/* Config info */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Configuración activa
              </h4>
              <div className="space-y-2">
                {[
                  { label: 'Modelo', value: config.model },
                  { label: 'Max casos', value: config.max_casos.toString() },
                  {
                    label: 'Paso actual', value:
                      step === 'upload' ? '1 — Upload' :
                        step === 'processing_docs' ? '2 — Procesando...' :
                          step === 'review' ? '3 — Revisión JSON' :
                            step === 'generating' ? '4 — Generando...' :
                              '✅ Completado'
                  },
                  ...(sessionFolder ? [{ label: 'Sesión', value: sessionFolder }] : []),
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between text-xs">
                    <span className="text-gray-500">{label}</span>
                    <span className="font-medium text-gray-800">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Step indicator */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Flujo</h4>
              <div className="space-y-2">
                {[
                  { key: 'upload', label: '1. Subir documentos', emoji: '📄' },
                  { key: 'processing_docs', label: '2. Procesar + FAISS', emoji: '🔍' },
                  { key: 'review', label: '3. Revisar con Agente 0', emoji: '🤖' },
                  { key: 'generating', label: '4. Generar casos', emoji: '⚡' },
                  { key: 'done', label: '5. Descargar', emoji: '📥' },
                ].map(({ key, label, emoji }) => {
                  const stepOrder = ['upload', 'processing_docs', 'review', 'generating', 'done'];
                  const current = stepOrder.indexOf(step);
                  const idx = stepOrder.indexOf(key);
                  const isDone = idx < current || step === 'done';
                  const isActive = idx === current && step !== 'done';

                  return (
                    <div key={key} className={`flex items-center gap-2 text-xs py-1 px-2 rounded ${isActive ? 'bg-red-50 text-red-700 font-semibold' :
                      isDone ? 'text-green-600' : 'text-gray-400'
                      }`}>
                      <span>{isDone ? '✅' : emoji}</span>
                      <span>{label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

        </div>
      </main>

      {/* ── FOOTER ──────────────────────────────────────────────────────── */}
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

export default App;
