import React from 'react';
import { clsx } from 'clsx';

const ConfigurationForm = ({ config, setConfig }) => {
    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setConfig(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    const handleArrayChange = (e, field) => {
        const { value, checked } = e.target;
        setConfig(prev => {
            const current = prev[field];
            if (checked) {
                return { ...prev, [field]: [...current, value] };
            } else {
                return { ...prev, [field]: current.filter(item => item !== value) };
            }
        });
    };

    return (
        <div className="space-y-6">

            {/* Brands */}
            <div className="space-y-2">
                <label className="text-sm font-semibold text-gray-700 block uppercase tracking-wide text-xs">Marcas</label>
                <div className="flex flex-wrap gap-3">
                    {['CLARO', 'VTR'].map((brand) => (
                        <label
                            key={brand}
                            className={clsx(
                                "flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer select-none transition-all",
                                config.marcas.includes(brand)
                                    ? "border-claro-red bg-red-50 text-claro-red font-bold shadow-sm"
                                    : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                            )}
                        >
                            <input
                                type="checkbox"
                                value={brand}
                                checked={config.marcas.includes(brand)}
                                onChange={(e) => handleArrayChange(e, 'marcas')}
                                className="hidden"
                            />
                            <span className="text-sm">{brand}</span>
                        </label>
                    ))}
                </div>
            </div>

            {/* Technologies */}
            <div className="space-y-2">
                <label className="text-sm font-semibold text-gray-700 block uppercase tracking-wide text-xs">Tecnologías</label>
                <div className="flex flex-wrap gap-3">
                    {['FTTH', 'HFC'].map((tech) => (
                        <label
                            key={tech}
                            className={clsx(
                                "flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer select-none transition-all",
                                config.tecnologias.includes(tech)
                                    ? "border-amber-500 bg-amber-50 text-amber-700 font-bold shadow-sm"
                                    : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                            )}
                        >
                            <input
                                type="checkbox"
                                value={tech}
                                checked={config.tecnologias.includes(tech)}
                                onChange={(e) => handleArrayChange(e, 'tecnologias')}
                                className="hidden"
                            />
                            <span className="text-sm">{tech}</span>
                        </label>
                    ))}
                </div>
            </div>

            {/* Provider Settings (Collapsed / Technical) */}
            <div className="pt-4 border-t border-gray-100">
                <details className="group">
                    <summary className="flex cursor-pointer items-center justify-between text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">
                        <span>Configuración Avanzada (IA)</span>
                        <span className="ml-2 transition group-open:rotate-180">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-4 h-4">
                                <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                            </svg>
                        </span>
                    </summary>

                    <div className="mt-4 space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">
                        <div>
                            <label className="text-xs font-semibold text-gray-500 block mb-2">Proveedor</label>
                            <select
                                name="provider"
                                value={config.provider}
                                onChange={handleChange}
                                className="w-full bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 focus:outline-none focus:border-claro-red focus:ring-1 focus:ring-claro-red"
                            >
                                <option value="lmstudio">LM Studio (Local)</option>
                                <option value="ollama">Ollama (Local)</option>
                            </select>
                        </div>

                        <div>
                            <label className="text-xs font-semibold text-gray-500 block mb-2">URL del Modelo</label>
                            <input
                                type="text"
                                name="lm_url"
                                value={config.lm_url}
                                onChange={handleChange}
                                className="w-full bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 focus:outline-none focus:border-claro-red focus:ring-1 focus:ring-claro-red"
                            />
                        </div>
                    </div>
                </details>
            </div>
        </div>
    );
};

export default ConfigurationForm;
