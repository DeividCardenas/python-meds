import type { Step } from "../constants";
import { BentoBox, Pill, ProgressRing, scoreColor } from "../ui";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface EngineCardProps {
  step: Step;
  columnas: number;
  elapsedMs: number;
  elapsedSec: string;
  aprobadas: number;
  pendientes: number;
  avgConfidence: number;
  indefinidos: number;
  filaCount: number;
}

// ---------------------------------------------------------------------------
// Component — Box 2: Motor Polars
// ---------------------------------------------------------------------------

export function EngineCard({
  step,
  columnas,
  elapsedMs,
  elapsedSec,
  aprobadas,
  pendientes,
  avgConfidence,
  indefinidos,
  filaCount,
}: EngineCardProps) {
  const labelMap: Record<Step, string> = {
    upload: "En espera",
    mapping: "Listo",
    processing: "Activo",
    review: "Completado",
    done: "Completado",
  };
  const colorMap: "amber" | "emerald" | "slate" = step === "processing"
    ? "amber"
    : step === "review"
      ? "emerald"
      : "slate";

  return (
    <BentoBox className="lg:col-span-5">
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
        <div className="flex items-center gap-2">
          <div
            className={`h-2 w-2 rounded-full ${
              step === "processing"
                ? "bg-amber-500 animate-pulse"
                : step === "review"
                  ? "bg-emerald-500"
                  : "bg-slate-300"
            }`}
          />
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
            Motor Polars
          </span>
        </div>
        <Pill label={labelMap[step]} color={colorMap} />
      </div>

      <div className="flex flex-col items-center justify-center p-5 gap-5">
        {/* ── Idle ── */}
        {(step === "upload" || step === "mapping") && (
          <div className="flex flex-col items-center gap-4 py-4 text-center">
            <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-slate-100 border-2 border-slate-200">
              <svg
                className="h-8 w-8 text-slate-400"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-semibold text-slate-600">
                {step === "upload"
                  ? "Esperando archivo"
                  : "Motor listo para ejecutar"}
              </p>
              <p className="text-xs text-slate-400">
                {step === "upload"
                  ? "Sube un tarifario para iniciar el pipeline"
                  : "Confirma el mapeo para lanzar el ETL Polars + Celery"}
              </p>
            </div>
            {step === "mapping" && columnas > 0 && (
              <div className="w-full rounded-xl border border-blue-100 bg-blue-50 p-3 text-center">
                <p className="text-2xl font-bold text-blue-700">{columnas}</p>
                <p className="text-xs text-blue-600 font-medium">
                  Columnas detectadas en el archivo
                </p>
              </div>
            )}
          </div>
        )}

        {/* ── Processing ── */}
        {step === "processing" && (
          <div className="flex flex-col items-center gap-4 w-full">
            <div className="relative flex items-center justify-center">
              <div
                className="absolute h-24 w-24 rounded-full bg-amber-400/20 animate-ping"
                style={{ animationDuration: "1.5s" }}
              />
              <div
                className="absolute h-20 w-20 rounded-full bg-amber-400/10 animate-ping"
                style={{ animationDuration: "2s" }}
              />
              <div className="relative z-10 flex h-16 w-16 items-center justify-center rounded-full bg-white border-2 border-amber-200 shadow-md">
                <svg
                  className="h-7 w-7 animate-spin text-amber-500"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
              </div>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold tabular-nums text-slate-800">
                {(elapsedMs / 1000).toFixed(2)}
                <span className="text-base font-medium text-slate-400">s</span>
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                Tiempo de procesamiento
              </p>
            </div>
            <div className="w-full space-y-2">
              <div className="flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
                <div className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                <p className="text-xs text-amber-700 font-medium">
                  Homologando códigos CUM via pgvector…
                </p>
              </div>
              <div className="flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-200 px-3 py-2">
                <div
                  className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse"
                  style={{ animationDelay: "0.3s" }}
                />
                <p className="text-xs text-blue-700 font-medium">
                  Celery worker procesando filas…
                </p>
              </div>
              <div className="flex items-center gap-2 rounded-lg bg-violet-50 border border-violet-200 px-3 py-2">
                <div
                  className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-pulse"
                  style={{ animationDelay: "0.6s" }}
                />
                <p className="text-xs text-violet-700 font-medium">
                  Aplicando reglas de negocio…
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ── Review ── */}
        {step === "review" && (
          <div className="flex flex-col items-center gap-4 w-full">
            <div className="relative flex items-center justify-center">
              <ProgressRing
                value={aprobadas}
                max={filaCount}
                size={96}
                strokeWidth={7}
              />
              <div className="absolute text-center">
                <p className="text-lg font-bold text-slate-800 leading-none">
                  {filaCount > 0
                    ? Math.round((aprobadas / filaCount) * 100)
                    : 0}%
                </p>
                <p className="text-[9px] text-slate-400 font-medium">listo</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 w-full">
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-center">
                <div className="flex items-center justify-center gap-1 mb-0.5">
                  <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
                    Auto-aprobadas
                  </p>
                </div>
                <p className="text-2xl font-bold text-emerald-700">
                  {aprobadas}
                </p>
              </div>
              <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-center">
                <div className="flex items-center justify-center gap-1 mb-0.5">
                  <div className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                  <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600">
                    Pendientes
                  </p>
                </div>
                <p className="text-2xl font-bold text-amber-700">{pendientes}</p>
              </div>
            </div>
            <div className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Tiempo de motor</span>
                <span className="font-bold tabular-nums text-slate-800">
                  {elapsedSec}s
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Confianza media</span>
                <span className={`font-bold ${scoreColor(avgConfidence)}`}>
                  {(avgConfidence * 100).toFixed(1)}%
                </span>
              </div>
              {indefinidos > 0 && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Vigencia indefinida</span>
                  <span className="font-bold text-violet-700">
                    {indefinidos} filas
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </BentoBox>
  );
}
