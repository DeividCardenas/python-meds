import type { Fila } from "../types";
import { BentoBox, Pill, formatPrice, parseSugerencias, scoreBg, scoreColor } from "../ui";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ReviewStepProps {
  filas: Fila[];
  filasState: Record<string, string>;
  setFilasState: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  expandedRow: string | null;
  setExpandedRow: React.Dispatch<React.SetStateAction<string | null>>;
  onAprobar: (filaId: string, idCum: string) => Promise<void>;
  onPublicar: () => void;
  isLoading: boolean;
  aprobadas: number;
  pendientes: number;
}

// ---------------------------------------------------------------------------
// Component — Box 4: Command Center
// ---------------------------------------------------------------------------

export function ReviewStep({
  filas,
  filasState,
  setFilasState,
  expandedRow,
  setExpandedRow,
  onAprobar,
  onPublicar,
  isLoading,
  aprobadas,
  pendientes,
}: ReviewStepProps) {
  return (
    <BentoBox className="lg:col-span-12">
      {/* Header with publish CTA */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-800">
            <svg
              className="h-4 w-4 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18M9 21V9" />
            </svg>
          </div>
          <div>
            <span className="text-sm font-bold text-slate-800">
              Centro de Comandos
            </span>
            <span className="ml-2 text-xs text-slate-400">
              — {filas.length} filas en staging
            </span>
          </div>
        </div>
        <button
          type="button"
          onClick={onPublicar}
          disabled={isLoading || aprobadas === 0}
          className={`inline-flex items-center gap-2 rounded-xl px-6 py-2.5 text-sm font-bold text-white shadow-md transition-all duration-200 active:scale-95 ${
            aprobadas > 0
              ? "bg-teal-600 hover:bg-teal-700 hover:shadow-lg shadow-teal-200"
              : "bg-slate-300 cursor-not-allowed"
          } disabled:opacity-60`}
        >
          {isLoading ? (
            <>
              <svg
                className="h-4 w-4 animate-spin"
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
              Publicando al catálogo…
            </>
          ) : (
            <>
              <svg
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <path d="m22 2-7 20-4-9-9-4 20-7z" />
              </svg>
              Publicar {aprobadas} precio{aprobadas !== 1 ? "s" : ""} al catálogo
            </>
          )}
        </button>
      </div>

      {/* Rows table */}
      <div className="divide-y divide-slate-100">
        {filas.map((fila) => {
          const sugerencias = parseSugerencias(fila.sugerenciasCum);
          const override = filasState[fila.id] ?? "";
          const isAprobado = fila.estadoHomologacion === "APROBADO";
          const isExpanded = expandedRow === fila.id;
          const topSugerencia = sugerencias[0];

          return (
            <div
              key={fila.id}
              className={`transition-colors duration-200 ${isAprobado ? "bg-white" : "bg-amber-50/40"}`}
            >
              {/* Row summary — always visible */}
              <button
                type="button"
                onClick={() => setExpandedRow(isExpanded ? null : fila.id)}
                className="flex w-full cursor-pointer items-center gap-3 px-5 py-3 text-left hover:bg-slate-50/80 transition-colors"
                aria-expanded={isExpanded}
              >
                <div
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${
                    isAprobado
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {isAprobado ? "✓" : "!"}
                </div>
                <span className="w-12 shrink-0 text-[10px] font-medium text-slate-400 tabular-nums">
                  #{fila.filaNumero}
                </span>
                <span className="flex-1 truncate text-sm font-medium text-slate-700">
                  {fila.descripcionRaw ?? "Sin descripción"}
                </span>
                {fila.cumCode && (
                  <span className="hidden shrink-0 rounded bg-slate-100 px-2 py-0.5 font-mono text-[10px] text-slate-600 sm:inline">
                    {fila.cumCode}
                  </span>
                )}
                <div className="hidden shrink-0 items-center gap-3 text-xs text-slate-500 lg:flex">
                  {fila.precioUnitario != null && (
                    <span>{formatPrice(fila.precioUnitario)}</span>
                  )}
                  {fila.porcentajeIva != null && (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                      IVA {(fila.porcentajeIva * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                {fila.confianzaScore != null && (
                  <span
                    className={`hidden shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold sm:inline ${scoreBg(fila.confianzaScore)} ${scoreColor(fila.confianzaScore)}`}
                  >
                    {(fila.confianzaScore * 100).toFixed(0)}%
                  </span>
                )}
                <svg
                  className={`h-4 w-4 shrink-0 text-slate-300 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>

              {/* Expanded detail panel */}
              {isExpanded && (
                <div className="border-t border-slate-100 bg-slate-50/60 px-5 py-4 space-y-4">
                  {/* Price pills */}
                  <div className="flex flex-wrap gap-2">
                    {fila.precioUnitario != null && (
                      <span className="rounded-lg bg-white border border-slate-200 px-3 py-1 text-xs">
                        <span className="text-slate-400">Unitario </span>
                        <strong>{formatPrice(fila.precioUnitario)}</strong>
                      </span>
                    )}
                    {fila.precioUnidad != null && (
                      <span className="rounded-lg bg-white border border-slate-200 px-3 py-1 text-xs">
                        <span className="text-slate-400">UMD </span>
                        <strong>{formatPrice(fila.precioUnidad)}</strong>
                      </span>
                    )}
                    {fila.precioPresentacion != null && (
                      <span className="rounded-lg bg-white border border-slate-200 px-3 py-1 text-xs">
                        <span className="text-slate-400">Caja </span>
                        <strong>{formatPrice(fila.precioPresentacion)}</strong>
                      </span>
                    )}
                    {fila.fechaVigenciaIndefinida && (
                      <Pill label="Vigencia indefinida" color="violet" />
                    )}
                  </div>

                  {/* CUM suggestions */}
                  {!isAprobado && sugerencias.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                        Sugerencias de homologación CUM
                      </p>
                      {sugerencias.slice(0, 4).map((sug) => (
                        <button
                          key={sug.id_cum}
                          type="button"
                          onClick={() => void onAprobar(fila.id, sug.id_cum)}
                          className={`flex w-full items-center justify-between gap-2 rounded-xl border bg-white px-4 py-2.5 text-left text-xs transition-all duration-150 hover:border-teal-300 hover:bg-teal-50 hover:shadow-sm ${
                            sug === topSugerencia
                              ? "border-teal-200"
                              : "border-slate-200"
                          }`}
                        >
                          <div className="min-w-0">
                            <span className="font-semibold text-slate-800">
                              {sug.nombre}
                            </span>
                            {sug.principio_activo && (
                              <span className="ml-2 text-slate-500">
                                {sug.principio_activo}
                              </span>
                            )}
                            {sug.laboratorio && (
                              <span className="ml-2 text-slate-400">
                                · {sug.laboratorio}
                              </span>
                            )}
                            <span className="ml-2 rounded bg-slate-100 px-1 py-px font-mono text-[10px] text-slate-500">
                              {sug.id_cum}
                            </span>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {sug === topSugerencia && (
                              <span className="rounded-full bg-teal-100 px-2 py-px text-[9px] font-bold text-teal-700">
                                TOP
                              </span>
                            )}
                            <span
                              className={`w-10 text-right font-bold tabular-nums ${scoreColor(sug.score)}`}
                            >
                              {(sug.score * 100).toFixed(0)}%
                            </span>
                            <span className="rounded-lg bg-teal-600 px-2.5 py-1 text-[10px] font-bold text-white">
                              Aprobar
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Manual CUM input */}
                  {!isAprobado && (
                    <div className="flex items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white p-3">
                      <svg
                        className="h-4 w-4 shrink-0 text-slate-400"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                      </svg>
                      <input
                        value={override}
                        onChange={(e) =>
                          setFilasState((prev) => ({
                            ...prev,
                            [fila.id]: e.target.value,
                          }))
                        }
                        placeholder="Ingresa CUM manualmente (ej. 52477-01)"
                        className="h-8 flex-1 border-0 bg-transparent text-xs outline-none placeholder:text-slate-300 focus:ring-0"
                      />
                      <button
                        type="button"
                        disabled={!override.trim()}
                        onClick={() => void onAprobar(fila.id, override.trim())}
                        className="shrink-0 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-bold text-white transition hover:bg-blue-700 disabled:opacity-40"
                      >
                        Aprobar CUM
                      </button>
                    </div>
                  )}

                  {/* Approved badge */}
                  {isAprobado && (
                    <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5">
                      <svg
                        className="h-4 w-4 text-emerald-600"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                      <span className="text-xs font-semibold text-emerald-700">
                        CUM aprobado:{" "}
                        <code className="rounded bg-emerald-100 px-1.5 py-px font-mono text-emerald-800">
                          {fila.cumCode}
                        </code>
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer summary */}
      <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/50 px-5 py-3">
        <p className="text-xs text-slate-400">
          {aprobadas} de {filas.length} filas listas para publicar
        </p>
        {pendientes > 0 && (
          <p className="text-xs text-amber-600 font-medium">
            {pendientes} fila{pendientes !== 1 ? "s" : ""} requiere
            {pendientes === 1 ? "" : "n"} revisión manual
          </p>
        )}
      </div>
    </BentoBox>
  );
}
