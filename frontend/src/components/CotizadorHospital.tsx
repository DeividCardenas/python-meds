import { useMutation, useQuery } from "@apollo/client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    GetCotizacionDocument,
    IniciarCotizacionDocument,
    type CotizacionFilaFragment,
    type PrecioItemFragment,
    type ResumenCotizacionFragment,
} from "../graphql/generated";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
type Step = "upload" | "procesando" | "resultados";
type SortKey = "nombreInput" | "matchConfidence" | "precioUnitario" | "preciosCount" | "fechaPublicacion";
type SortDir = "asc" | "desc";

// ─────────────────────────────────────────────────────────────────────────────
// Pure helpers
// ─────────────────────────────────────────────────────────────────────────────
const fmtCOP = (v?: number | null) =>
  v != null
    ? new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        maximumFractionDigits: 0,
      }).format(v)
    : "—";

const fmtDate = (s?: string | null) => {
  if (!s) return "—";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString("es-CO");
};

/** Pick the provider with the lowest precioUnitario */
const getBestPrecio = (precios?: PrecioItemFragment[] | null): PrecioItemFragment | null => {
  if (!precios?.length) return null;
  return precios.reduce((best, p) =>
    (p.precioUnitario ?? Infinity) < (best.precioUnitario ?? Infinity) ? p : best,
  );
};

/** Percentage above the best price (0 = it IS the best) */
const deviationPct = (price: number, best: number) =>
  best > 0 ? ((price - best) / best) * 100 : 0;

// ─────────────────────────────────────────────────────────────────────────────
// MatchBadge
// ─────────────────────────────────────────────────────────────────────────────
function MatchBadge({ stage, confidence }: { stage?: string | null; confidence?: number | null }) {
  if (!stage || stage === "NO_MATCH")
    return (
      <span className="inline-flex items-center rounded-md bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-500 ring-1 ring-inset ring-red-100">
        Sin match
      </span>
    );
  const pct = confidence != null ? Math.round(confidence * 100) : null;
  const [bg, text, ring] =
    stage === "INN"
      ? ["bg-emerald-50", "text-emerald-700", "ring-emerald-100"]
      : stage === "FUZZY"
        ? ["bg-amber-50", "text-amber-600", "ring-amber-100"]
        : ["bg-blue-50", "text-blue-600", "ring-blue-100"];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium ring-1 ring-inset ${bg} ${text} ${ring}`}
    >
      {stage}
      {pct != null && <span className="font-normal opacity-60">{pct}%</span>}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SortableHeader — sortable column header (numeric / date columns)
// ─────────────────────────────────────────────────────────────────────────────
function SortableHeader({
  label,
  colKey,
  activeSortKey,
  sortDir,
  onSort,
  align = "left",
}: {
  label: string;
  colKey: SortKey;
  activeSortKey: SortKey | null;
  sortDir: SortDir;
  onSort: (k: SortKey) => void;
  align?: "left" | "right" | "center";
}) {
  const active = activeSortKey === colKey;
  const thAlign =
    align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  const btnAlign =
    align === "right" ? "flex-row-reverse" : align === "center" ? "justify-center" : "";
  return (
    <th className={`px-4 py-3 ${thAlign}`}>
      <button
        type="button"
        onClick={() => onSort(colKey)}
        className={`inline-flex select-none items-center gap-1 text-[11px] font-semibold uppercase tracking-wide transition-colors ${btnAlign} ${
          active ? "text-teal-600" : "text-slate-400 hover:text-slate-600"
        }`}
      >
        {label}
        <span className={`text-[10px] transition-opacity ${active ? "opacity-100" : "opacity-0"}`}>
          {sortDir === "asc" ? "↑" : "↓"}
        </span>
      </button>
    </th>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// KPI bar — compact counters + inline progress bars
// ─────────────────────────────────────────────────────────────────────────────
function KpiBar({ r }: { r: ResumenCotizacionFragment }) {
  const matchPct = r.total > 0 ? (r.conMatch / r.total) * 100 : 0;
  const precioPct = r.total > 0 ? (r.conPrecio / r.total) * 100 : 0;

  return (
    <div className="flex flex-wrap items-center gap-x-8 gap-y-4 rounded-xl border border-slate-100 bg-white px-6 py-4 shadow-sm">
      {[
        { label: "Total",      value: r.total,     color: "text-slate-800" },
        { label: "Con match",  value: r.conMatch,  color: "text-emerald-600" },
        { label: "Sin match",  value: r.sinMatch,  color: "text-red-500" },
        { label: "Con precio", value: r.conPrecio, color: "text-teal-600" },
        { label: "Sin precio", value: r.sinPrecio, color: "text-amber-500" },
      ].map((s) => (
        <div key={s.label} className="flex flex-col items-center">
          <span className={`text-2xl font-bold tabular-nums ${s.color}`}>{s.value}</span>
          <span className="text-[11px] text-slate-400">{s.label}</span>
        </div>
      ))}

      <div className="hidden h-10 w-px self-center bg-slate-100 sm:block" />

      <div className="flex flex-1 flex-col gap-2 justify-center min-w-55">
        {[
          { label: "Match",     pct: matchPct,  barColor: "bg-emerald-400", textColor: "text-emerald-600" },
          { label: "Con precio", pct: precioPct, barColor: "bg-teal-400",    textColor: "text-teal-600" },
        ].map(({ label, pct, barColor, textColor }) => (
          <div key={label} className="flex items-center gap-3">
            <span className="w-20 text-right text-[11px] text-slate-400">{label}</span>
            <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${pct}%` }} />
            </div>
            <span className={`w-10 text-[11px] font-semibold tabular-nums ${textColor}`}>{pct.toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ProviderDrawer — progressive disclosure: all providers sorted asc + deviation
// ─────────────────────────────────────────────────────────────────────────────
function ProviderDrawer({ precios, bestPrice }: { precios: PrecioItemFragment[]; bestPrice: number | null }) {
  const sorted = useMemo(
    () => [...precios].sort((a, b) => (a.precioUnitario ?? Infinity) - (b.precioUnitario ?? Infinity)),
    [precios],
  );

  return (
    <tr>
      <td colSpan={8} className="p-0">
        <div className="mx-4 mb-3 mt-0.5 overflow-hidden rounded-lg border border-slate-100">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                {["Proveedor", "P. Unitario", "Desv.", "P. Unidad", "P. Presentación", "IVA", "Vigencia", "Publicado"].map(
                  (h, i) => (
                    <th
                      key={h}
                      className={`px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400 ${i > 0 ? "text-right" : ""} ${i >= 6 ? "text-left" : ""}`}
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {sorted.map((p: PrecioItemFragment, i: number) => {
                const isBest = bestPrice != null && p.precioUnitario === bestPrice;
                const dev =
                  bestPrice != null && p.precioUnitario != null && !isBest
                    ? deviationPct(p.precioUnitario, bestPrice)
                    : null;
                const devColor =
                  dev == null ? "text-slate-200"
                  : dev <= 5   ? "text-slate-400"
                  : dev <= 20  ? "text-amber-500 font-medium"
                  :              "text-red-500 font-medium";

                return (
                  <tr key={i} className={isBest ? "bg-emerald-50/70" : "bg-white"}>
                    <td className="px-3 py-1.5 text-xs text-slate-700">
                      <span className="flex items-center gap-2">
                        {isBest && (
                          <span className="inline-flex items-center rounded bg-emerald-100 px-1 py-0.5 text-[9px] font-bold uppercase tracking-wider text-emerald-700">
                            ★ Mejor
                          </span>
                        )}
                        {p.proveedorNombre ?? "—"}
                      </span>
                    </td>
                    <td className={`px-3 py-1.5 text-right text-xs font-medium tabular-nums ${isBest ? "text-emerald-700" : "text-slate-700"}`}>
                      {fmtCOP(p.precioUnitario)}
                    </td>
                    <td className={`px-3 py-1.5 text-right text-xs tabular-nums ${devColor}`}>
                      {dev == null ? "—" : `+${dev.toFixed(1)}%`}
                    </td>
                    <td className="px-3 py-1.5 text-right text-xs tabular-nums text-slate-500">{fmtCOP(p.precioUnidad)}</td>
                    <td className="px-3 py-1.5 text-right text-xs tabular-nums text-slate-500">{fmtCOP(p.precioPresentacion)}</td>
                    <td className="px-3 py-1.5 text-right text-xs text-slate-400">
                      {p.porcentajeIva != null ? `${p.porcentajeIva}%` : "—"}
                    </td>
                    <td className="px-3 py-1.5 text-xs text-slate-400">
                      {p.vigenteDesde || p.vigenteHasta
                        ? `${fmtDate(p.vigenteDesde)} → ${fmtDate(p.vigenteHasta)}`
                        : "—"}
                    </td>
                    <td className="px-3 py-1.5 text-xs text-slate-400">{fmtDate(p.fechaPublicacion)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </td>
    </tr>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FilaResultado — one drug row with sticky first columns + drill-down drawer
// ─────────────────────────────────────────────────────────────────────────────
function FilaResultado({ fila }: { fila: CotizacionFilaFragment }) {
  const [expanded, setExpanded] = useState(false);
  const precios = fila.todosPrecios ?? [];
  const tienePrecios = precios.length > 0;
  const hasMatch = fila.matchStage && fila.matchStage !== "NO_MATCH";

  const bestPrecio = getBestPrecio(precios);
  const bestPrice = bestPrecio?.precioUnitario ?? null;

  return (
    <>
      <tr
        className={`group border-b border-slate-50 transition-colors ${
          tienePrecios ? "cursor-pointer hover:bg-slate-50/60" : ""
        }`}
        onClick={() => tienePrecios && setExpanded((v) => !v)}
      >
        {/* ── Col 1: chevron (sticky left-0) ── */}
        <td className="sticky left-0 z-10 w-8 bg-white px-2 text-center transition-colors group-hover:bg-slate-50/60">
          {tienePrecios ? (
            <svg
              className={`inline h-3.5 w-3.5 text-slate-300 transition-transform duration-150 group-hover:text-slate-400 ${
                expanded ? "rotate-90" : "rotate-0"
              }`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
            </svg>
          ) : (
            <span className="inline-block h-3.5 w-3.5" />
          )}
        </td>

        {/* ── Col 2: product name (sticky left-8) ── */}
        <td
          className="sticky left-8 z-10 bg-white px-4 py-2.5 transition-colors group-hover:bg-slate-50/60"
          title={fila.nombreInput}
        >
          <span className="block max-w-47.5 truncate text-sm font-medium text-slate-800">
            {fila.nombreInput}
          </span>
          {hasMatch && fila.nombreMatcheado && fila.nombreMatcheado !== fila.nombreInput && (
            <span className="block max-w-47.5 truncate text-[10px] text-slate-400" title={fila.nombreMatcheado ?? ""}>
              {fila.nombreMatcheado}
            </span>
          )}
        </td>

        {/* ── Col 3: match badge ── */}
        <td className="px-4 py-2.5">
          <MatchBadge stage={fila.matchStage} confidence={fila.matchConfidence} />
        </td>

        {/* ── Col 4: forma · concentración ── */}
        <td className="px-4 py-2.5 text-xs text-slate-400">
          {fila.formaFarmaceutica ? (
            <>
              {fila.formaFarmaceutica}
              {fila.concentracion && <span className="text-slate-300"> · {fila.concentracion}</span>}
            </>
          ) : (
            <span className="text-slate-200">—</span>
          )}
        </td>

        {/* ── Col 5: best provider name ── */}
        <td className="max-w-35 truncate px-4 py-2.5 text-xs text-slate-500" title={bestPrecio?.proveedorNombre ?? ""}>
          {bestPrecio?.proveedorNombre ?? <span className="text-slate-200">—</span>}
        </td>

        {/* ── Col 6: best price — normalized (unitario) + secondary (unidad) ── */}
        <td className="px-4 py-2.5 text-right">
          {bestPrecio && bestPrice != null ? (
            <span className="inline-flex flex-col items-end">
              <span className="text-sm font-semibold tabular-nums text-emerald-700">{fmtCOP(bestPrice)}</span>
              {bestPrecio.precioUnidad != null && (
                <span className="text-[10px] tabular-nums text-slate-400">
                  {fmtCOP(bestPrecio.precioUnidad)}&thinsp;/ud
                </span>
              )}
            </span>
          ) : (
            <span className="text-xs text-slate-200">—</span>
          )}
        </td>

        {/* ── Col 7: provider count pill ── */}
        <td className="px-4 py-2.5 text-center">
          {tienePrecios ? (
            <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-teal-50 px-1.5 text-[11px] font-semibold text-teal-600">
              {precios.length}
            </span>
          ) : (
            <span className="text-xs text-slate-200">—</span>
          )}
        </td>

        {/* ── Col 8: publication date ── */}
        <td className="px-4 py-2.5 text-xs tabular-nums text-slate-400">
          {fmtDate(bestPrecio?.fechaPublicacion)}
        </td>

        {/* ── Col 9: regulation ── */}
        <td className="px-4 py-2.5">
          {fila.esRegulado ? (
            <span className="inline-flex flex-col gap-0.5">
              <span className="inline-flex items-center rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-semibold text-orange-700">
                🔒 Regulado
              </span>
              {fila.precioMaximoRegulado != null && (
                <span className="text-[10px] tabular-nums text-orange-500">
                  Máx {fmtCOP(fila.precioMaximoRegulado)}
                </span>
              )}
            </span>
          ) : (
            <span className="text-xs text-slate-200">—</span>
          )}
        </td>
      </tr>

      {/* Progressive disclosure: provider comparison drawer */}
      {expanded && tienePrecios && <ProviderDrawer precios={precios} bestPrice={bestPrice} />}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────
export function CotizadorHospital() {
  const [step, setStep] = useState<Step>("upload");
  const [loteId, setLoteId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [filename, setFilename] = useState<string | null>(null);
  const [filterText, setFilterText] = useState("");
  const [filterMatch, setFilterMatch] = useState<"all" | "match" | "nomatch" | "noprecio">("all");
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [iniciarCotizacion, { loading: uploading }] = useMutation(IniciarCotizacionDocument);

  const pollInterval = step === "procesando" ? 2000 : 0;
  const { data: cotizData, stopPolling } = useQuery(GetCotizacionDocument, {
    variables: { id: loteId ?? "" },
    skip: !loteId,
    pollInterval,
    fetchPolicy: "network-only",
  });

  const lote = cotizData?.getCotizacion;

  // Watch status to advance steps
  useEffect(() => {
    if (!lote) return;
    if (lote.status === "COMPLETED") {
      stopPolling();
      setStep("resultados");
    } else if (lote.status === "FAILED") {
      stopPolling();
      setError("El proceso falló en el servidor. Por favor vuelve a intentarlo.");
      setStep("upload");
    }
  }, [lote, stopPolling]);

  // File submission
  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      setFilename(file.name);
      try {
        const res = await iniciarCotizacion({ variables: { file, hospitalId: "GLOBAL" } });
        const id = res.data?.iniciarCotizacion?.id;
        if (!id) throw new Error("No se recibió ID del lote");
        setLoteId(id);
        setStep("procesando");
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [iniciarCotizacion]
  );

  const handleExport = (formato: "csv" | "excel") => {
    if (!loteId) return;
    window.open(`/cotizacion/${loteId}/exportar?formato=${formato}`, "_blank");
  };

  const reset = () => {
    setStep("upload");
    setLoteId(null);
    setError(null);
    setFilename(null);
    setFilterText("");
    setFilterMatch("all");
    setSortKey(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };

  // Filter → sort pipeline (memoized)
  const allFilas = lote?.filas ?? [];
  const filas = useMemo(() => {
    let rows = allFilas.filter((f) => {
      if (filterText) {
        const q = filterText.toLowerCase();
        if (!f.nombreInput.toLowerCase().includes(q) && !(f.nombreMatcheado ?? "").toLowerCase().includes(q)) return false;
      }
      if (filterMatch === "match" && (!f.matchStage || f.matchStage === "NO_MATCH")) return false;
      if (filterMatch === "nomatch" && f.matchStage && f.matchStage !== "NO_MATCH") return false;
      if (filterMatch === "noprecio" && (f.preciosCount ?? 0) > 0) return false;
      return true;
    });
    if (sortKey) {
      rows = [...rows].sort((a, b) => {
        let av: number | string = 0, bv: number | string = 0;
        if (sortKey === "nombreInput")        { av = a.nombreInput; bv = b.nombreInput; }
        else if (sortKey === "matchConfidence") { av = a.matchConfidence ?? 0; bv = b.matchConfidence ?? 0; }
        else if (sortKey === "precioUnitario")  { av = getBestPrecio(a.todosPrecios)?.precioUnitario ?? Infinity; bv = getBestPrecio(b.todosPrecios)?.precioUnitario ?? Infinity; }
        else if (sortKey === "preciosCount")    { av = a.preciosCount ?? 0; bv = b.preciosCount ?? 0; }
        else if (sortKey === "fechaPublicacion") { av = getBestPrecio(a.todosPrecios)?.fechaPublicacion ?? ""; bv = getBestPrecio(b.todosPrecios)?.fechaPublicacion ?? ""; }
        const cmp = typeof av === "string" ? av.localeCompare(bv as string) : (av as number) - (bv as number);
        return sortDir === "asc" ? cmp : -cmp;
      });
    }
    return rows;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allFilas, filterText, filterMatch, sortKey, sortDir]);

  // ── Step 1: Upload ──────────────────────────────────────────────────────────
  if (step === "upload") {
    return (
      <section className="mx-auto max-w-2xl space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Cotizador Masivo</h2>
          <p className="mt-1 text-sm text-slate-500">
            Sube un CSV o Excel con la columna{" "}
            <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs text-slate-600">nombre</code> y el
            sistema encontrará automáticamente los mejores precios disponibles.
          </p>
        </div>

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <svg className="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {error}
          </div>
        )}

        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files?.[0]; if (f) handleFile(f); }}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer rounded-2xl border-2 border-dashed px-8 py-14 text-center transition-all duration-150 ${
            dragOver
              ? "scale-[1.01] border-teal-500 bg-teal-50/60"
              : "border-slate-200 bg-white hover:border-teal-300 hover:bg-slate-50/40"
          }`}
        >
          <div className={`mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl transition-colors ${dragOver ? "bg-teal-100" : "bg-slate-100"}`}>
            <svg className={`h-7 w-7 transition-colors ${dragOver ? "text-teal-600" : "text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <p className="text-sm font-medium text-slate-700">
            Arrastra tu archivo aquí o <span className="text-teal-600 underline">selecciona uno</span>
          </p>
          <p className="mt-1 text-xs text-slate-400">
            CSV · Excel (.xlsx / .xls) — Columna requerida: <strong className="font-semibold text-slate-500">nombre</strong>
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />
        </div>

        {uploading && (
          <div className="flex items-center gap-2 text-sm text-teal-600">
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Subiendo archivo…
          </div>
        )}

        {/* Format reference */}
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Formato esperado</p>
          <table className="text-xs">
            <thead>
              <tr>
                <th className="rounded-l bg-slate-200 px-3 py-1 text-left font-semibold text-slate-600">nombre</th>
                <th className="rounded-r bg-slate-100 px-3 py-1 text-left font-normal text-slate-300">otras columnas (ignoradas)</th>
              </tr>
            </thead>
            <tbody>
              {["Acetaminofén 500mg tableta", "Amoxicilina 500mg cápsula", "Metformina 850mg tableta"].map((n) => (
                <tr key={n} className="border-t border-slate-200">
                  <td className="px-3 py-1 text-slate-600">{n}</td>
                  <td className="px-3 py-1 text-slate-300">…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    );
  }

  // ── Step 2: Processing ───────────────────────────────────────────────────────
  if (step === "procesando") {
    const statusMsg =
      lote?.status === "PROCESSING"
        ? "Procesando medicamentos…"
        : lote?.status === "PENDING"
          ? "En cola, iniciando pronto…"
          : "Iniciando…";

    return (
      <section className="mx-auto max-w-sm space-y-8 py-20 text-center">
        {/* Spinner ring */}
        <div className="relative mx-auto h-20 w-20">
          <div className="absolute inset-0 rounded-full border-4 border-teal-100" />
          <div className="absolute inset-0 animate-spin rounded-full border-4 border-transparent border-t-teal-500" />
          <div className="absolute inset-3 flex items-center justify-center rounded-full bg-teal-50">
            <svg className="h-7 w-7 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-800">{statusMsg}</h2>
          {filename && <p className="mt-1 text-sm text-slate-500">{filename}</p>}
          <p className="mt-3 text-xs leading-relaxed text-slate-400">
            Parseando nombres → buscando en catálogo CUM → consultando precios por proveedor
          </p>
        </div>
        <button
          type="button"
          onClick={reset}
          className="text-xs text-slate-400 underline underline-offset-2 hover:text-slate-600"
        >
          Cancelar y volver
        </button>
      </section>
    );
  }

  // ── Step 3: Results ──────────────────────────────────────────────────────────
  const resumen = lote?.resumen;
  const DownloadIcon = () => (
    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  );

  return (
    <section className="flex flex-col gap-5">
      {/* ── Toolbar ── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">Comparativa de Precios</h2>
          {filename && <p className="mt-0.5 text-xs text-slate-400">{filename}</p>}
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => handleExport("csv")}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50">
            <DownloadIcon /> CSV
          </button>
          <button type="button" onClick={() => handleExport("excel")}
            className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-teal-700">
            <DownloadIcon /> Excel
          </button>
          <button type="button" onClick={reset}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-50">
            Nueva cotización
          </button>
        </div>
      </div>

      {/* ── KPI bar ── */}
      {resumen && <KpiBar r={resumen} />}

      {/* ── Filter controls ── */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Search with clear button */}
        <div className="relative">
          <svg className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Buscar medicamento…"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            className="w-56 rounded-lg border border-slate-200 bg-white py-1.5 pl-8 pr-7 text-xs text-slate-700 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-300"
          />
          {filterText && (
            <button type="button" onClick={() => setFilterText("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500">
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Segment filter tabs */}
        <div className="flex divide-x divide-slate-200 overflow-hidden rounded-lg border border-slate-200 text-xs">
          {([
            { key: "all",      label: "Todos"      },
            { key: "match",    label: "Con match"  },
            { key: "nomatch",  label: "Sin match"  },
            { key: "noprecio", label: "Sin precio" },
          ] as const).map(({ key, label }) => (
            <button key={key} type="button" onClick={() => setFilterMatch(key)}
              className={`px-3 py-1.5 transition-colors ${
                filterMatch === key ? "bg-teal-600 text-white" : "bg-white text-slate-500 hover:bg-slate-50"
              }`}>
              {label}
            </button>
          ))}
        </div>

        <span className="ml-auto text-[11px] tabular-nums text-slate-400">
          {filas.length} de {allFilas.length}
        </span>
      </div>

      {/* ── Comparison table — sticky thead + sticky first column ── */}
      <div className="overflow-hidden rounded-xl border border-slate-100 bg-white shadow-sm">
        {/* Constrained height enables thead sticky to work within the scroll container */}
        <div className="overflow-auto" style={{ maxHeight: "calc(100vh - 340px)" }}>
          <table className="w-full min-w-200 border-collapse text-left">
            <thead className="sticky top-0 z-20">
              <tr className="border-b border-slate-100 bg-white shadow-[0_1px_0_var(--color-slate-100)]">
                {/* sticky cols */}
                <th className="sticky left-0 z-30 w-8 bg-white px-2" />
                <th className="sticky left-8 z-30 bg-white px-4 py-3">
                  <button type="button" onClick={() => handleSort("nombreInput")}
                    className={`inline-flex select-none items-center gap-1 text-[11px] font-semibold uppercase tracking-wide transition-colors ${
                      sortKey === "nombreInput" ? "text-teal-600" : "text-slate-400 hover:text-slate-600"
                    }`}>
                    Medicamento
                    <span className={`text-[10px] transition-opacity ${sortKey === "nombreInput" ? "opacity-100" : "opacity-0"}`}>
                      {sortDir === "asc" ? "↑" : "↓"}
                    </span>
                  </button>
                </th>
                <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Match</th>
                <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Forma · Conc.</th>
                <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Mejor Proveedor</th>
                <SortableHeader label="Precio Unit." colKey="precioUnitario" activeSortKey={sortKey} sortDir={sortDir} onSort={handleSort} align="right" />
                <SortableHeader label="Proveedores"  colKey="preciosCount"   activeSortKey={sortKey} sortDir={sortDir} onSort={handleSort} align="center" />
                <SortableHeader label="Publicado"    colKey="fechaPublicacion" activeSortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
                <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Regulado</th>
              </tr>
            </thead>

            <tbody>
              {filas.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-16 text-center text-sm text-slate-300">
                    No hay resultados para los filtros seleccionados.
                  </td>
                </tr>
              ) : (
                filas.map((fila: CotizacionFilaFragment, i: number) => <FilaResultado key={fila.nombreInput + i} fila={fila} />)
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
