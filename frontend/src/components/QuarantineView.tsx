import { AlertTriangle } from "lucide-react";

import type { OrphanItem } from "./ResultsDashboard";

type QuarantineViewProps = {
  rows: OrphanItem[];
};

export function QuarantineView({ rows }: QuarantineViewProps) {
  return (
    <section className="mx-auto mt-4 w-full max-w-6xl rounded-3xl border border-white/30 bg-white/55 p-5 shadow-[0_8px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl">
      <div className="mb-4 flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 text-amber-600" />
        <h3 className="text-base font-semibold text-slate-900">Bandeja de Cuarentena</h3>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white/75">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-100/80 text-xs uppercase tracking-wide text-slate-600">
            <tr>
              <th className="px-4 py-3">CUM</th>
              <th className="px-4 py-3">Descripcion</th>
              <th className="px-4 py-3">Frecuencia</th>
              <th className="px-4 py-3">Estado</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${row.cum}-${idx}`} className="border-t border-slate-100 text-slate-700 hover:bg-slate-50/70">
                <td className="px-4 py-3 font-medium text-slate-900">{row.cum}</td>
                <td className="px-4 py-3">{row.descripcion}</td>
                <td className="px-4 py-3">{row.frecuencia}</td>
                <td className="px-4 py-3">
                  <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700">
                    {row.estado}
                  </span>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-sm text-slate-500">
                  No hay medicamentos huerfanos pendientes.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
