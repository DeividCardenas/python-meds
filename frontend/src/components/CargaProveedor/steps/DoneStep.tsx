import { BentoBox } from "../ui";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DoneStepProps {
  filasPublicadas: number;
  detectedSupplier: string | null;
  elapsedSec: string | null;
  onReset: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DoneStep({
  filasPublicadas,
  detectedSupplier,
  elapsedSec,
  onReset,
}: DoneStepProps) {
  return (
    <BentoBox className="relative overflow-hidden">
      {/* Decorative glow rings */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div
          className="h-64 w-64 rounded-full bg-emerald-400/10 animate-ping"
          style={{ animationDuration: "2s" }}
        />
      </div>
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div className="h-96 w-96 rounded-full bg-teal-400/5" />
      </div>

      <div className="relative flex flex-col items-center gap-6 py-16 text-center px-8">
        {/* Animated checkmark */}
        <div className="relative">
          <div
            className="h-20 w-20 rounded-full bg-emerald-100 flex items-center justify-center animate-bounce"
            style={{ animationDuration: "0.8s", animationIterationCount: 3 }}
          >
            <svg
              className="h-10 w-10 text-emerald-600"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
        </div>

        {/* Message */}
        <div className="space-y-1">
          <p className="text-2xl font-bold text-slate-900">
            ¡Precios publicados en el catálogo!
          </p>
          <p className="text-slate-500 text-sm max-w-sm mx-auto">
            El motor Polars procesó y publicó exitosamente las filas del
            tarifario al catálogo empresarial.
          </p>
        </div>

        {/* Metric pills */}
        <div className="flex flex-wrap justify-center gap-3">
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-6 py-3 text-center">
            <p className="text-2xl font-bold text-emerald-700">
              {filasPublicadas}
            </p>
            <p className="text-xs text-emerald-600 font-medium">
              Filas publicadas
            </p>
          </div>

          {detectedSupplier && (
            <div className="rounded-2xl border border-violet-200 bg-violet-50 px-6 py-3 text-center">
              <p className="text-lg font-bold text-violet-700">
                {detectedSupplier}
              </p>
              <p className="text-xs text-violet-600 font-medium">Proveedor</p>
            </div>
          )}

          {elapsedSec !== null && (
            <div className="rounded-2xl border border-blue-200 bg-blue-50 px-6 py-3 text-center">
              <p className="text-2xl font-bold text-blue-700">{elapsedSec}s</p>
              <p className="text-xs text-blue-600 font-medium">Tiempo motor</p>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={onReset}
          className="mt-2 rounded-xl bg-teal-600 px-8 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 hover:shadow-md active:scale-95"
        >
          Cargar otro tarifario
        </button>
      </div>
    </BentoBox>
  );
}
