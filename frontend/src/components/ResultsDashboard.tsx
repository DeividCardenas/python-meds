import { AlertTriangle, CircleCheckBig } from "lucide-react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

type OrphanItem = {
  cum: string;
  descripcion: string;
  frecuencia: number;
  estado: "Pendiente" | "Revisado";
};

type ResultsDashboardProps = {
  matchedCount: number;
  orphanCount: number;
  topOrphans: OrphanItem[];
};

const COLORS = ["#0f766e", "#f59e0b"];

export function ResultsDashboard({
  matchedCount,
  orphanCount,
  topOrphans,
}: ResultsDashboardProps) {
  const pieData = [
    { name: "Tarifas Cruzadas (Match)", value: Math.max(0, matchedCount) },
    { name: "Tarifas No Encontradas (Cuarentena)", value: Math.max(0, orphanCount) },
  ];

  return (
    <section className="mx-auto mt-8 grid w-full max-w-6xl gap-4 md:grid-cols-12">
      <article className="rounded-3xl border border-white/30 bg-white/55 p-5 shadow-[0_8px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl md:col-span-5">
        <div className="mb-3 flex items-center gap-2">
          <CircleCheckBig className="h-5 w-5 text-teal-700" />
          <h3 className="text-base font-semibold text-slate-900">Cruce de Tarifas</h3>
        </div>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                innerRadius={72}
                outerRadius={102}
                paddingAngle={3}
                dataKey="value"
              >
                {pieData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => {
                  const numeric = typeof value === "number" ? value : Number(value ?? 0);
                  return numeric.toLocaleString("es-CO");
                }}
              />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </article>

      <article className="rounded-3xl border border-white/30 bg-white/55 p-5 shadow-[0_8px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl md:col-span-7">
        <div className="mb-3 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-600" />
          <h3 className="text-base font-semibold text-slate-900">Top 10 CUMs en Cuarentena</h3>
        </div>

        <div className="grid gap-2">
          {topOrphans.slice(0, 10).map((item, idx) => (
            <div
              key={`${item.cum}-${idx}`}
              className="flex items-center justify-between rounded-xl border border-amber-100 bg-amber-50/60 px-3 py-2"
            >
              <div>
                <p className="text-sm font-semibold text-slate-900">{item.cum}</p>
                <p className="text-xs text-slate-600">{item.descripcion}</p>
              </div>
              <div className="text-right">
                <p className="text-xs font-medium text-amber-700">{item.estado}</p>
                <p className="text-xs text-slate-500">Frecuencia: {item.frecuencia}</p>
              </div>
            </div>
          ))}
          {topOrphans.length === 0 && (
            <p className="rounded-xl border border-slate-200 bg-white/70 p-3 text-sm text-slate-600">
              No hay CUMs en cuarentena para mostrar.
            </p>
          )}
        </div>
      </article>
    </section>
  );
}

export type { OrphanItem };
