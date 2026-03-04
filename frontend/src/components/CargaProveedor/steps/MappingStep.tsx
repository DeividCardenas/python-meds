import { CAMPOS } from "../constants";
import { Pill } from "../ui";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MappingStepProps {
  columnas: string[];
  mapeo: Record<string, string>;
  onMapeoChange: (key: string, value: string) => void;
  onConfirmar: () => void;
  onCancel: () => void;
  isLoading: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MappingStep({
  columnas,
  mapeo,
  onMapeoChange,
  onConfirmar,
  onCancel,
  isLoading,
}: MappingStepProps) {
  const mappedCount = Object.values(mapeo).filter(Boolean).length;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-bold text-slate-800">Mapeo de Columnas</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            El motor de IA pre-mapeó{" "}
            <strong className="text-teal-600">
              {mappedCount} de {CAMPOS.length}
            </strong>{" "}
            campos. Ajusta los que necesites.
          </p>
        </div>
        <Pill label={`${columnas.length} cols detectadas`} color="blue" />
      </div>

      {/* Field grid */}
      <div className="grid gap-3 sm:grid-cols-2">
        {CAMPOS.map(({ key, label, description }) => {
          const isMapped = Boolean(mapeo[key]);
          return (
            <div
              key={key}
              className={`rounded-xl border p-3 transition-all duration-200 ${
                isMapped
                  ? "border-teal-200 bg-teal-50/50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <div className="mb-1.5 flex items-center justify-between">
                <label className="text-xs font-bold text-slate-700">
                  {label}
                </label>
                {isMapped && (
                  <span className="text-[9px] font-bold uppercase tracking-wider text-teal-600">
                    ✓ mapeado
                  </span>
                )}
              </div>
              <p className="mb-2 text-[10px] text-slate-400 leading-snug">
                {description}
              </p>
              <select
                value={mapeo[key] ?? ""}
                onChange={(e) => onMapeoChange(key, e.target.value)}
                className="h-8 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-xs outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
              >
                <option value="">— No mapear —</option>
                {columnas.map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
              </select>
            </div>
          );
        })}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between border-t border-slate-100 pt-4">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50"
        >
          ← Cancelar
        </button>
        <button
          type="button"
          onClick={onConfirmar}
          disabled={isLoading}
          className="inline-flex items-center gap-2 rounded-xl bg-teal-600 px-6 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-teal-700 hover:shadow-md disabled:opacity-60 active:scale-95"
        >
          {isLoading ? (
            <>
              <svg
                className="h-3.5 w-3.5 animate-spin"
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
              Enviando al motor…
            </>
          ) : (
            "Confirmar y lanzar ETL →"
          )}
        </button>
      </div>
    </div>
  );
}
