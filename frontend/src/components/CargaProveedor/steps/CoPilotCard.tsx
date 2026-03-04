import type { Step } from "../constants";
import { BentoBox } from "../ui";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CoPilotCardProps {
  step: Step;
  detectedSupplier: string | null;
  indefinidos: number;
}

// ---------------------------------------------------------------------------
// Component — Box 3: Co-Pilot Insights (only rendered when there's content)
// ---------------------------------------------------------------------------

export function CoPilotCard({
  step,
  detectedSupplier,
  indefinidos,
}: CoPilotCardProps) {
  const visible =
    Boolean(detectedSupplier) || indefinidos > 0 || step === "processing";
  if (!visible) return null;

  return (
    <BentoBox className="lg:col-span-12">
      <div className="flex items-center gap-3 border-b border-violet-100 bg-violet-50/60 px-5 py-3">
        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-600">
          <svg
            className="h-3.5 w-3.5 text-white"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
          >
            <path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm0 6v4l3 3" />
          </svg>
        </div>
        <span className="text-xs font-bold uppercase tracking-widest text-violet-700">
          Co-Pilot — Inteligencia Proactiva
        </span>
        <div className="ml-auto">
          <div className="h-2 w-2 rounded-full bg-violet-500 animate-pulse" />
        </div>
      </div>

      <div className="flex flex-wrap gap-3 p-4">
        {/* Supplier insight */}
        {detectedSupplier && (
          <div className="flex-1 min-w-64 rounded-xl border border-violet-200 bg-violet-50 p-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-100">
                <svg
                  className="h-4 w-4 text-violet-600"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
                </svg>
              </div>
              <div>
                <p className="text-xs font-bold text-violet-800">
                  Proveedor detectado: {detectedSupplier}
                </p>
                <p className="mt-0.5 text-xs text-violet-600 leading-snug">
                  {detectedSupplier === "La Santé"
                    ? "Regla 'Vigencia Indefinida' aplicada automáticamente a campos de fecha vacíos."
                    : `Perfil de ${detectedSupplier} reconocido. Reglas de negocio específicas activadas.`}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Indefinite dates insight */}
        {indefinidos > 0 && (
          <div className="flex-1 min-w-64 rounded-xl border border-teal-200 bg-teal-50 p-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-teal-100">
                <svg
                  className="h-4 w-4 text-teal-600"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M9 11l3 3L22 4" />
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
              </div>
              <div>
                <p className="text-xs font-bold text-teal-800">
                  {indefinidos} filas con vigencia indefinida
                </p>
                <p className="mt-0.5 text-xs text-teal-600 leading-snug">
                  El motor Polars marcó estas filas con{" "}
                  <code className="rounded bg-teal-100 px-1 font-mono text-[10px]">
                    fecha_vigencia_indefinida = true
                  </code>{" "}
                  y sustituyó las fechas vacías.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Analysing supplier (processing, no data yet) */}
        {step === "processing" && !detectedSupplier && indefinidos === 0 && (
          <div className="flex-1 min-w-64 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-200 animate-pulse">
                <svg
                  className="h-4 w-4 text-slate-600"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
              </div>
              <div>
                <p className="text-xs font-bold text-slate-700">
                  Analizando firma del proveedor…
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  El Co-Pilot está identificando el proveedor y las reglas
                  aplicables.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </BentoBox>
  );
}
