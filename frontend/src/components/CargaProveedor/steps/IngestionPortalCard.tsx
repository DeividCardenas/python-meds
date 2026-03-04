import type { Step } from "../constants";
import { CAMPOS } from "../constants";
import { BentoBox, Pill } from "../ui";
import { MappingStep } from "./MappingStep";
import { UploadStep } from "./UploadStep";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface IngestionPortalCardProps {
  step: Step;
  filename: string | null;
  columnas: string[];
  mapeo: Record<string, string>;
  setMapeo: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  dragOver: boolean;
  onDragOver: () => void;
  onDragLeave: () => void;
  onFileSelected: (file: File) => void;
  onConfirmar: () => void;
  onCancel: () => void;
  loadingSubir: boolean;
  loadingConfirmar: boolean;
  // review metrics
  filaCount: number;
  aprobadas: number;
  pendientes: number;
}

// ---------------------------------------------------------------------------
// Component — Box 1: Ingestion Portal
// ---------------------------------------------------------------------------

export function IngestionPortalCard({
  step,
  filename,
  columnas,
  mapeo,
  setMapeo,
  dragOver,
  onDragOver,
  onDragLeave,
  onFileSelected,
  onConfirmar,
  onCancel,
  loadingSubir,
  loadingConfirmar,
  filaCount,
  aprobadas,
  pendientes,
}: IngestionPortalCardProps) {
  const dotColor =
    step === "upload"
      ? "bg-slate-400"
      : step === "mapping"
        ? "bg-blue-500 animate-pulse"
        : step === "processing"
          ? "bg-amber-500 animate-pulse"
          : "bg-emerald-500";

  return (
    <BentoBox className="lg:col-span-7">
      {/* Card header */}
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
        <div className="flex items-center gap-2">
          <div className={`h-2 w-2 rounded-full transition-colors duration-500 ${dotColor}`} />
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
            Portal de Ingestión
          </span>
        </div>
        {filename && (
          <span className="max-w-50 truncate rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-medium text-slate-600">
            {filename}
          </span>
        )}
      </div>

      <div className="p-5">
        {/* ── Upload ── */}
        {step === "upload" && (
          <UploadStep
            onFileSelected={onFileSelected}
            isLoading={loadingSubir}
            dragOver={dragOver}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
          />
        )}

        {/* ── Mapping ── */}
        {step === "mapping" && (
          <MappingStep
            columnas={columnas}
            mapeo={mapeo}
            onMapeoChange={(key, value) =>
              setMapeo((prev) => ({ ...prev, [key]: value }))
            }
            onConfirmar={onConfirmar}
            onCancel={onCancel}
            isLoading={loadingConfirmar}
          />
        )}

        {/* ── Processing / Review ── */}
        {(step === "processing" || step === "review") && filename && (
          <div className="space-y-4">
            {/* File summary */}
            <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white border border-slate-200 shadow-sm">
                <svg
                  className="h-5 w-5 text-teal-600"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-800">
                  {filename}
                </p>
                <p className="text-xs text-slate-500">
                  {columnas.length} columnas detectadas
                </p>
              </div>
              <Pill
                label={step === "processing" ? "En proceso" : "Procesado"}
                color={step === "processing" ? "amber" : "emerald"}
              />
            </div>

            {/* Active mapping summary */}
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
                Mapeo activo
              </p>
              <div className="grid grid-cols-2 gap-1.5">
                {CAMPOS.filter((c) => mapeo[c.key]).map(({ key, label }) => (
                  <div
                    key={key}
                    className="flex items-center gap-2 rounded-lg bg-teal-50 border border-teal-100 px-2.5 py-1.5"
                  >
                    <div className="h-1.5 w-1.5 rounded-full bg-teal-500" />
                    <span className="truncate text-[10px] font-medium text-teal-700">
                      {label}:{" "}
                      <span className="text-teal-900 font-bold">
                        {mapeo[key]}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Review metrics */}
            {step === "review" && (
              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-100">
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-center">
                  <p className="text-xl font-bold text-slate-800">{filaCount}</p>
                  <p className="text-[10px] text-slate-500 font-medium">Total filas</p>
                </div>
                <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-center">
                  <p className="text-xl font-bold text-emerald-700">{aprobadas}</p>
                  <p className="text-[10px] text-emerald-600 font-medium">Auto-aprobadas</p>
                </div>
                <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-center">
                  <p className="text-xl font-bold text-amber-700">{pendientes}</p>
                  <p className="text-[10px] text-amber-600 font-medium">Pendientes</p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </BentoBox>
  );
}
