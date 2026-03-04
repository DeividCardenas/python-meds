import { STEP_LABELS, STEP_ORDER } from "./constants";
import { useCargaProveedor } from "./hooks/useCargaProveedor";
import { useStagingFilas } from "./hooks/useStagingFilas";
import { CoPilotCard } from "./steps/CoPilotCard";
import { DoneStep } from "./steps/DoneStep";
import { EngineCard } from "./steps/EngineCard";
import { IngestionPortalCard } from "./steps/IngestionPortalCard";
import { ReviewStep } from "./steps/ReviewStep";
import { detectSupplier } from "./ui";

export function CargaProveedor() {
  const carga = useCargaProveedor();
  const staging = useStagingFilas({
    archivoId: carga.archivoId,
    active: carga.step === "processing",
    onFilasLoaded: carga.handleProcessingComplete,
  });

  const aprobadas       = staging.filas.filter((f) => f.estadoHomologacion === "APROBADO").length;
  const pendientes      = staging.filas.filter((f) => f.estadoHomologacion === "PENDIENTE").length;
  const indefinidos     = staging.filas.filter((f) => f.fechaVigenciaIndefinida).length;
  const detectedSupplier = detectSupplier(carga.filename);
  const elapsedSec      = ((carga.finalElapsedMs ?? carga.elapsedMs) / 1000).toFixed(2);
  const avgConfidence = staging.filas.length > 0 ? staging.filas.reduce((acc, f) => acc + (f.confianzaScore ?? 0), 0) / staging.filas.length : 0;
  const stepIdx = STEP_ORDER.indexOf(carga.step);

  return (
    <section className="space-y-4">
      {/* ── Page header + stepper ── */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-teal-600 mb-0.5">Pipeline de Precios</p>
          <h2 className="text-2xl font-bold text-slate-900 leading-tight">Centro de Comando — Tarifario Proveedor</h2>
        </div>
        <nav aria-label="Progreso del flujo" className="flex items-center gap-1">
          {STEP_ORDER.map((s, idx) => {
            const isDone = stepIdx > idx;
            const isActive = carga.step === s;
            return (
              <div key={s} className="flex items-center gap-1">
                <div className={`flex h-6 items-center gap-1.5 rounded-full px-2.5 text-[10px] font-bold transition-all duration-300 ${isDone ? "bg-teal-600 text-white" : isActive ? "bg-blue-600 text-white ring-2 ring-blue-300" : "bg-slate-100 text-slate-400"}`}>
                  {isDone ? <svg className="h-2.5 w-2.5" viewBox="0 0 10 10" fill="currentColor"><path d="M8.5 2.5 4 7.5 1.5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none"/></svg> : <span>{idx + 1}</span>}
                  <span className="hidden sm:inline">{STEP_LABELS[s]}</span>
                </div>
                {idx < STEP_ORDER.length - 1 && <div className={`h-px w-3 transition-colors duration-300 ${stepIdx > idx ? "bg-teal-400" : "bg-slate-200"}`} />}
              </div>
            );
          })}
        </nav>
      </div>

      {/* ── Error banner ── */}
      {carga.errorMsg && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <svg className="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm.75 9.5h-1.5v-1.5h1.5v1.5zm0-3h-1.5v-4h1.5v4z"/></svg>
          <span>{carga.errorMsg}</span>
        </div>
      )}

      {/* ── Done ── */}
      {carga.step === "done" && carga.publicado && (
        <DoneStep filasPublicadas={carga.publicado.filasPublicadas} detectedSupplier={detectedSupplier} elapsedSec={carga.finalElapsedMs !== null ? elapsedSec : null} onReset={carga.handleReset} />
      )}

      {/* ── Main bento grid ── */}
      {carga.step !== "done" && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <IngestionPortalCard step={carga.step} filename={carga.filename} columnas={carga.columnas} mapeo={carga.mapeo} setMapeo={carga.setMapeo} dragOver={carga.dragOver} onDragOver={() => carga.setDragOver(true)} onDragLeave={() => carga.setDragOver(false)} onFileSelected={(f) => void carga.handleUpload(f)} onConfirmar={() => void carga.handleConfirmarMapeo()} onCancel={carga.handleReset} loadingSubir={carga.loadingSubir} loadingConfirmar={carga.loadingConfirmar} filaCount={staging.filas.length} aprobadas={aprobadas} pendientes={pendientes} />
          <EngineCard step={carga.step} columnas={carga.columnas.length} elapsedMs={carga.elapsedMs} elapsedSec={elapsedSec} aprobadas={aprobadas} pendientes={pendientes} avgConfidence={avgConfidence} indefinidos={indefinidos} filaCount={staging.filas.length} />
          <CoPilotCard step={carga.step} detectedSupplier={detectedSupplier} indefinidos={indefinidos} />
          {carga.step === "review" && (
            <ReviewStep filas={staging.filas} filasState={staging.filasState} setFilasState={staging.setFilasState} expandedRow={staging.expandedRow} setExpandedRow={staging.setExpandedRow} onAprobar={staging.aprobarFila} onPublicar={() => void carga.handlePublicar()} isLoading={carga.loadingPublicar} aprobadas={aprobadas} pendientes={pendientes} />
          )}
        </div>
      )}
    </section>
  );
}
