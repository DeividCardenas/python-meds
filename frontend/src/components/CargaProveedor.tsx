import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { useMutation, useQuery } from "@apollo/client";

import {
  SubirArchivoProveedorDocument,
  ConfirmarMapeoProveedorDocument,
  GetStagingFilasDocument,
  AprobarStagingFilaDocument,
  PublicarPreciosProveedorDocument,
  type GetStagingFilasQuery,
} from "../graphql/generated";

// ---------------------------------------------------------------------------
// Types & constants
// ---------------------------------------------------------------------------

type Step = "upload" | "mapping" | "processing" | "review" | "done";

type Fila = GetStagingFilasQuery["getStagingFilas"][number];

type Sugerencia = {
  id_cum: string;
  nombre: string;
  score: number;
  principio_activo?: string | null;
  laboratorio?: string | null;
};

const CAMPOS: Array<{ key: string; label: string; description: string }> = [
  { key: "cum_code",            label: "Código CUM",           description: "Código único de medicamento" },
  { key: "descripcion",         label: "Descripción / Nombre", description: "Nombre o descripción del producto" },
  { key: "precio_unitario",     label: "Precio Unitario",      description: "Precio por unidad – columna genérica" },
  { key: "precio_unidad",       label: "Precio Unidad Mínima", description: "Precio UMD / unidad mínima de dispensación" },
  { key: "precio_presentacion", label: "Precio Presentación",  description: "Precio por caja / presentación" },
  { key: "porcentaje_iva",      label: "IVA (%)",              description: "Porcentaje de IVA (ej. 19 o 0.19)" },
  { key: "vigente_desde",       label: "Vigente Desde",        description: "Fecha inicio de vigencia" },
  { key: "vigente_hasta",       label: "Vigente Hasta",        description: "Fecha fin de vigencia" },
];

const STEP_ORDER: Step[] = ["upload", "mapping", "processing", "review", "done"];
const STEP_LABELS: Record<Step, string> = {
  upload: "Ingestión", mapping: "Mapeo", processing: "Motor",
  review: "Revisión", done: "Publicado",
};

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

function parseSugerencias(json: string | null | undefined): Sugerencia[] {
  if (!json) return [];
  try {
    const val = JSON.parse(json);
    return Array.isArray(val) ? (val as Sugerencia[]) : [];
  } catch {
    return [];
  }
}

const formatPrice = (v: number | null | undefined) =>
  typeof v === "number" && Number.isFinite(v)
    ? new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        maximumFractionDigits: 2,
      }).format(v)
    : "—";

const scoreColor = (s: number) =>
  s >= 0.99 ? "text-emerald-600" : s >= 0.8 ? "text-amber-500" : "text-red-500";
const scoreBg = (s: number) =>
  s >= 0.99 ? "bg-emerald-50 border-emerald-200" : s >= 0.8 ? "bg-amber-50 border-amber-200" : "bg-red-50 border-red-200";

function detectSupplier(filename: string | null): string | null {
  if (!filename) return null;
  const lower = filename.toLowerCase();
  if (lower.includes("la_sante") || lower.includes("lasante") || lower.includes("la sante")) return "La Santé";
  if (lower.includes("megalabs")) return "Megalabs";
  if (lower.includes("genfar")) return "Genfar";
  if (lower.includes("pfizer")) return "Pfizer";
  if (lower.includes("bayer")) return "Bayer";
  return null;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Circular SVG progress ring */
function ProgressRing({
  value, max, size = 88, strokeWidth = 6,
}: { value: number; max: number; size?: number; strokeWidth?: number }) {
  const r = (size - strokeWidth) / 2;
  const circ = 2 * Math.PI * r;
  const pct = max > 0 ? Math.min(value / max, 1) : 0;
  const offset = circ * (1 - pct);
  const color = pct >= 1 ? "#059669" : pct >= 0.5 ? "#0d9488" : "#3b82f6";
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }} aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={strokeWidth} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={color} strokeWidth={strokeWidth} strokeLinecap="round"
        strokeDasharray={circ} strokeDashoffset={offset}
        style={{ transition: "stroke-dashoffset 0.5s ease, stroke 0.5s ease" }}
      />
    </svg>
  );
}

/** An individual Bento card shell */
function BentoBox({
  children, className = "",
}: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-2xl bg-white border border-slate-200/80 shadow-sm ring-1 ring-slate-900/5 overflow-hidden transition-all duration-500 ${className}`}
    >
      {children}
    </div>
  );
}

/** Small badge pill */
function Pill({
  label, color = "slate",
}: { label: string; color?: "emerald" | "amber" | "blue" | "slate" | "violet" }) {
  const map: Record<string, string> = {
    emerald: "bg-emerald-100 text-emerald-700 border-emerald-200",
    amber:   "bg-amber-100 text-amber-700 border-amber-200",
    blue:    "bg-blue-100 text-blue-700 border-blue-200",
    slate:   "bg-slate-100 text-slate-600 border-slate-200",
    violet:  "bg-violet-100 text-violet-700 border-violet-200",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide ${map[color]}`}>
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CargaProveedor() {
  // ── Core state ────────────────────────────────────────────────────────────
  const [step, setStep]           = useState<Step>("upload");
  const [archivoId, setArchivoId] = useState<string | null>(null);
  const [filename, setFilename]   = useState<string | null>(null);
  const [columnas, setColumnas]   = useState<string[]>([]);
  const [mapeo, setMapeo]         = useState<Record<string, string>>({});
  const [filas, setFilas]         = useState<Fila[]>([]);
  const [filasState, setFilasState] = useState<Record<string, string>>({});
  const [publicado, setPublicado] = useState<{ filasPublicadas: number } | null>(null);
  const [dragOver, setDragOver]   = useState(false);
  const [errorMsg, setErrorMsg]   = useState<string | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  // ── Engine metrics state ──────────────────────────────────────────────────
  const [elapsedMs, setElapsedMs]       = useState(0);
  const processingStartRef              = useRef<number | null>(null);
  const elapsedIntervalRef              = useRef<ReturnType<typeof setInterval> | null>(null);
  const [finalElapsedMs, setFinalElapsed] = useState<number | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Mutations ─────────────────────────────────────────────────────────────
  const [subirArchivo,  { loading: loadingSubir }]    = useMutation(SubirArchivoProveedorDocument);
  const [confirmarMapeo, { loading: loadingConfirmar }] = useMutation(ConfirmarMapeoProveedorDocument);
  const [aprobarFila]                                 = useMutation(AprobarStagingFilaDocument);
  const [publicarPrecios, { loading: loadingPublicar }] = useMutation(PublicarPreciosProveedorDocument);

  // ── Polling staging rows ──────────────────────────────────────────────────
  const { data: stagingData, startPolling, stopPolling } = useQuery(GetStagingFilasDocument, {
    variables: { archivoId: archivoId ?? "" },
    skip: !archivoId || step !== "processing",
    fetchPolicy: "network-only",
  });

  // Start / stop polling based on step
  useEffect(() => {
    if (step === "processing" && archivoId) {
      startPolling(2000);
    } else {
      stopPolling();
    }
  }, [step, archivoId, startPolling, stopPolling]);

  // Consume polling result
  useEffect(() => {
    if (stagingData && stagingData.getStagingFilas.length > 0) {
      stopPolling();
      if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
      setFinalElapsed(elapsedMs);
      setFilas(stagingData.getStagingFilas);
      setStep("review");
    }
  }, [stagingData, stopPolling, elapsedMs]);

  // Start / stop the elapsed-time counter when entering "processing"
  useEffect(() => {
    if (step === "processing") {
      processingStartRef.current = Date.now();
      setElapsedMs(0);
      elapsedIntervalRef.current = setInterval(() => {
        setElapsedMs(Date.now() - (processingStartRef.current ?? Date.now()));
      }, 50);
    } else if (step !== "review") {
      setElapsedMs(0);
      setFinalElapsed(null);
      processingStartRef.current = null;
    }
    return () => {
      if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
    };
  }, [step]);

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleFile = useCallback(
    async (file: File) => {
      setErrorMsg(null);
      try {
        const { data } = await subirArchivo({ variables: { file } });
        const result = data?.subirArchivoProveedor;
        if (!result) throw new Error("Respuesta vacía del servidor");

        setArchivoId(result.id);
        setFilename(result.filename);
        const cols = result.columnasDetectadas ?? [];
        setColumnas(cols);

        let sugerido: Record<string, string> = {};
        if (result.mapeoSugerido) {
          try { sugerido = JSON.parse(result.mapeoSugerido) as Record<string, string>; } catch { /* ignore */ }
        }
        setMapeo(sugerido);
        setStep("mapping");
      } catch (e) {
        setErrorMsg(e instanceof Error ? e.message : "Error al subir el archivo");
      }
    },
    [subirArchivo],
  );

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleFile(file);
    e.target.value = "";
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) void handleFile(file);
  };

  const onConfirmarMapeo = async () => {
    if (!archivoId) return;
    setErrorMsg(null);
    try {
      await confirmarMapeo({
        variables: {
          archivoId,
          cumCode:            mapeo.cum_code            ?? null,
          precioUnitario:     mapeo.precio_unitario     ?? null,
          precioUnidad:       mapeo.precio_unidad       ?? null,
          precioPresentacion: mapeo.precio_presentacion ?? null,
          porcentajeIva:      mapeo.porcentaje_iva      ?? null,
          descripcion:        mapeo.descripcion         ?? null,
          vigentDesde:        mapeo.vigente_desde       ?? null,
          vigenteHasta:       mapeo.vigente_hasta       ?? null,
        },
      });
      setStep("processing");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Error al confirmar el mapeo");
    }
  };

  const onAprobar = async (filaId: string, idCum: string) => {
    try {
      await aprobarFila({ variables: { stagingId: filaId, idCum } });
      setFilas((prev: Fila[]) =>
        prev.map((f: Fila) =>
          f.id === filaId ? { ...f, estadoHomologacion: "APROBADO", cumCode: idCum } : f,
        ),
      );
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Error al aprobar la fila");
    }
  };

  const onPublicar = async () => {
    if (!archivoId) return;
    setErrorMsg(null);
    try {
      const { data } = await publicarPrecios({ variables: { archivoId } });
      setPublicado({ filasPublicadas: data?.publicarPreciosProveedor.filasPublicadas ?? 0 });
      setStep("done");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Error al publicar los precios");
    }
  };

  const onReset = () => {
    setStep("upload");
    setArchivoId(null);
    setFilename(null);
    setColumnas([]);
    setMapeo({});
    setFilas([]);
    setFilasState({});
    setPublicado(null);
    setErrorMsg(null);
    setExpandedRow(null);
    setElapsedMs(0);
    setFinalElapsed(null);
  };

  // ── Computed values ───────────────────────────────────────────────────────
  const pendientes     = filas.filter((f) => f.estadoHomologacion === "PENDIENTE").length;
  const aprobadas      = filas.filter((f) => f.estadoHomologacion === "APROBADO").length;
  const indefinidos    = filas.filter((f) => f.fechaVigenciaIndefinida).length;
  const detectedSupplier = detectSupplier(filename);
  const mappedCount    = Object.values(mapeo).filter(Boolean).length;
  const stepIdx        = STEP_ORDER.indexOf(step);
  const elapsedSec     = ((finalElapsedMs ?? elapsedMs) / 1000).toFixed(2);
  const avgConfidence  = filas.length > 0
    ? filas.reduce((acc, f) => acc + (f.confianzaScore ?? 0), 0) / filas.length
    : 0;

  // ── Bento Grid Render ─────────────────────────────────────────────────────
  return (
    <section className="space-y-4">

      {/* ── Page header & stepper ── */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-teal-600 mb-0.5">
            Pipeline de Precios
          </p>
          <h2 className="text-2xl font-bold text-slate-900 leading-tight">
            Centro de Comando — Tarifario Proveedor
          </h2>
        </div>
        {/* Step tracker pill */}
        <nav aria-label="Progreso del flujo" className="flex items-center gap-1">
          {STEP_ORDER.map((s, idx) => {
            const isDone   = stepIdx > idx;
            const isActive = step === s;
            return (
              <div key={s} className="flex items-center gap-1">
                <div
                  className={`flex h-6 items-center gap-1.5 rounded-full px-2.5 text-[10px] font-bold transition-all duration-300 ${
                    isDone
                      ? "bg-teal-600 text-white"
                      : isActive
                      ? "bg-blue-600 text-white ring-2 ring-blue-300"
                      : "bg-slate-100 text-slate-400"
                  }`}
                >
                  {isDone ? (
                    <svg className="h-2.5 w-2.5" viewBox="0 0 10 10" fill="currentColor">
                      <path d="M8.5 2.5 4 7.5 1.5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                    </svg>
                  ) : (
                    <span>{idx + 1}</span>
                  )}
                  <span className="hidden sm:inline">{STEP_LABELS[s]}</span>
                </div>
                {idx < STEP_ORDER.length - 1 && (
                  <div className={`h-px w-3 transition-colors duration-300 ${stepIdx > idx ? "bg-teal-400" : "bg-slate-200"}`} />
                )}
              </div>
            );
          })}
        </nav>
      </div>

      {/* ── Error banner ── */}
      {errorMsg && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <svg className="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm.75 9.5h-1.5v-1.5h1.5v1.5zm0-3h-1.5v-4h1.5v4z"/>
          </svg>
          <span>{errorMsg}</span>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          DONE STATE — full-width success celebration
      ═══════════════════════════════════════════════════════════════════ */}
      {step === "done" && publicado && (
        <BentoBox className="relative overflow-hidden">
          {/* Glow rings decoration */}
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="h-64 w-64 rounded-full bg-emerald-400/10 animate-ping" style={{ animationDuration: "2s" }} />
          </div>
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="h-96 w-96 rounded-full bg-teal-400/5" />
          </div>
          <div className="relative flex flex-col items-center gap-6 py-16 text-center px-8">
            {/* Animated check */}
            <div className="relative">
              <div className="h-20 w-20 rounded-full bg-emerald-100 flex items-center justify-center animate-bounce" style={{ animationDuration: "0.8s", animationIterationCount: 3 }}>
                <svg className="h-10 w-10 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-2xl font-bold text-slate-900">¡Precios publicados en el catálogo!</p>
              <p className="text-slate-500 text-sm max-w-sm mx-auto">
                El motor Polars procesó y publicó exitosamente las filas del tarifario al catálogo empresarial.
              </p>
            </div>
            {/* Success metric pills */}
            <div className="flex flex-wrap justify-center gap-3">
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-6 py-3 text-center">
                <p className="text-2xl font-bold text-emerald-700">{publicado.filasPublicadas}</p>
                <p className="text-xs text-emerald-600 font-medium">Filas publicadas</p>
              </div>
              {detectedSupplier && (
                <div className="rounded-2xl border border-violet-200 bg-violet-50 px-6 py-3 text-center">
                  <p className="text-lg font-bold text-violet-700">{detectedSupplier}</p>
                  <p className="text-xs text-violet-600 font-medium">Proveedor</p>
                </div>
              )}
              {finalElapsedMs !== null && (
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
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          MAIN BENTO GRID (upload → review)
      ═══════════════════════════════════════════════════════════════════ */}
      {step !== "done" && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">

          {/* ╔══════════════════════════════════════════════════════╗
              ║  BOX 1 — INGESTION PORTAL  (col-span-7)            ║
              ╚══════════════════════════════════════════════════════╝ */}
          <BentoBox className="lg:col-span-7">
            {/* ── Header bar for box ── */}
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
              <div className="flex items-center gap-2">
                <div className={`h-2 w-2 rounded-full transition-colors duration-500 ${
                  step === "upload" ? "bg-slate-400" :
                  step === "mapping" ? "bg-blue-500 animate-pulse" :
                  step === "processing" ? "bg-amber-500 animate-pulse" : "bg-emerald-500"
                }`} />
                <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Portal de Ingestión
                </span>
              </div>
              {filename && (
                <span className="max-w-[200px] truncate rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-medium text-slate-600">
                  {filename}
                </span>
              )}
            </div>

            <div className="p-5">

              {/* ── UPLOAD STATE ── */}
              {step === "upload" && (
                <div
                  onDragOver={(e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={onDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`relative flex cursor-pointer flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-12 transition-all duration-300 ${
                    dragOver
                      ? "scale-[1.02] border-blue-400 bg-blue-50/70 shadow-lg shadow-blue-100"
                      : "border-slate-200 bg-slate-50/50 hover:border-teal-300 hover:bg-teal-50/30"
                  }`}
                >
                  {/* Background icon */}
                  <div className={`rounded-2xl p-4 transition-all duration-300 ${dragOver ? "bg-blue-100" : "bg-white shadow-sm border border-slate-200"}`}>
                    <svg className={`h-8 w-8 transition-colors duration-300 ${dragOver ? "text-blue-500" : "text-slate-400"}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  </div>
                  {loadingSubir ? (
                    <div className="flex flex-col items-center gap-2">
                      <svg className="h-5 w-5 animate-spin text-teal-600" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      <p className="text-sm font-semibold text-teal-600 animate-pulse">Analizando estructura del archivo…</p>
                    </div>
                  ) : (
                    <div className="text-center space-y-1">
                      <p className="text-sm font-semibold text-slate-700">
                        {dragOver ? "Suelta para cargar el tarifario" : "Arrastra tu archivo aquí"}
                      </p>
                      <p className="text-xs text-slate-400">
                        o{" "}
                        <span className="text-teal-600 underline underline-offset-2 font-medium">
                          haz clic para explorar
                        </span>
                      </p>
                      <p className="text-[10px] text-slate-300 pt-1">CSV · XLSX · XLS — máx. 10 MB</p>
                    </div>
                  )}
                  <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={onFileChange} />
                </div>
              )}

              {/* ── MAPPING STATE ── */}
              {step === "mapping" && (
                <div className="space-y-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="font-bold text-slate-800">Mapeo de Columnas</h3>
                      <p className="mt-0.5 text-xs text-slate-500">
                        El motor de IA pre-mapeó <strong className="text-teal-600">{mappedCount} de {CAMPOS.length}</strong> campos.
                        Ajusta los que necesites.
                      </p>
                    </div>
                    <Pill label={`${columnas.length} cols detectadas`} color="blue" />
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {CAMPOS.map(({ key, label, description }) => {
                      const isMapped = Boolean(mapeo[key]);
                      return (
                        <div key={key} className={`rounded-xl border p-3 transition-all duration-200 ${isMapped ? "border-teal-200 bg-teal-50/50" : "border-slate-200 bg-white"}`}>
                          <div className="mb-1.5 flex items-center justify-between">
                            <label className="text-xs font-bold text-slate-700">{label}</label>
                            {isMapped && (
                              <span className="text-[9px] font-bold uppercase tracking-wider text-teal-600">✓ mapeado</span>
                            )}
                          </div>
                          <p className="mb-2 text-[10px] text-slate-400 leading-snug">{description}</p>
                          <select
                            value={mapeo[key] ?? ""}
                            onChange={(e) => setMapeo((prev) => ({ ...prev, [key]: e.target.value }))}
                            className="h-8 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-xs outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
                          >
                            <option value="">— No mapear —</option>
                            {columnas.map((col) => (
                              <option key={col} value={col}>{col}</option>
                            ))}
                          </select>
                        </div>
                      );
                    })}
                  </div>

                  <div className="flex items-center justify-between border-t border-slate-100 pt-4">
                    <button
                      type="button"
                      onClick={onReset}
                      className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50"
                    >
                      ← Cancelar
                    </button>
                    <button
                      type="button"
                      onClick={() => void onConfirmarMapeo()}
                      disabled={loadingConfirmar}
                      className="inline-flex items-center gap-2 rounded-xl bg-teal-600 px-6 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-teal-700 hover:shadow-md disabled:opacity-60 active:scale-95"
                    >
                      {loadingConfirmar ? (
                        <>
                          <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                          </svg>
                          Enviando al motor…
                        </>
                      ) : (
                        "Confirmar y lanzar ETL →"
                      )}
                    </button>
                  </div>
                </div>
              )}

              {/* ── PROCESSING STATE ── */}
              {(step === "processing" || step === "review") && filename && (
                <div className="space-y-4">
                  {/* File summary card */}
                  <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white border border-slate-200 shadow-sm">
                      <svg className="h-5 w-5 text-teal-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                        <polyline points="10 9 9 9 8 9"/>
                      </svg>
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-slate-800">{filename}</p>
                      <p className="text-xs text-slate-500">{columnas.length} columnas detectadas</p>
                    </div>
                    <Pill label={step === "processing" ? "En proceso" : "Procesado"} color={step === "processing" ? "amber" : "emerald"} />
                  </div>

                  {/* Mapped columns summary */}
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
                      Mapeo activo
                    </p>
                    <div className="grid grid-cols-2 gap-1.5">
                      {CAMPOS.filter(c => mapeo[c.key]).map(({ key, label }) => (
                        <div key={key} className="flex items-center gap-2 rounded-lg bg-teal-50 border border-teal-100 px-2.5 py-1.5">
                          <div className="h-1.5 w-1.5 rounded-full bg-teal-500" />
                          <span className="truncate text-[10px] font-medium text-teal-700">
                            {label}: <span className="text-teal-900 font-bold">{mapeo[key]}</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Review metrics row */}
                  {step === "review" && (
                    <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-100">
                      <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-center">
                        <p className="text-xl font-bold text-slate-800">{filas.length}</p>
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

          {/* ╔══════════════════════════════════════════════════════╗
              ║  BOX 2 — ENGINE METRICS  (col-span-5)              ║
              ╚══════════════════════════════════════════════════════╝ */}
          <BentoBox className="lg:col-span-5">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
              <div className="flex items-center gap-2">
                <div className={`h-2 w-2 rounded-full ${step === "processing" ? "bg-amber-500 animate-pulse" : step === "review" ? "bg-emerald-500" : "bg-slate-300"}`} />
                <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Motor Polars
                </span>
              </div>
              <Pill
                label={step === "upload" ? "En espera" : step === "mapping" ? "Listo" : step === "processing" ? "Activo" : "Completado"}
                color={step === "processing" ? "amber" : step === "review" ? "emerald" : "slate"}
              />
            </div>

            <div className="flex flex-col items-center justify-center p-5 gap-5">

              {/* Idle */}
              {(step === "upload" || step === "mapping") && (
                <div className="flex flex-col items-center gap-4 py-4 text-center">
                  <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-slate-100 border-2 border-slate-200">
                    <svg className="h-8 w-8 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                    </svg>
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-slate-600">
                      {step === "upload" ? "Esperando archivo" : "Motor listo para ejecutar"}
                    </p>
                    <p className="text-xs text-slate-400">
                      {step === "upload"
                        ? "Sube un tarifario para iniciar el pipeline"
                        : "Confirma el mapeo para lanzar el ETL Polars + Celery"}
                    </p>
                  </div>
                  {step === "mapping" && columnas.length > 0 && (
                    <div className="w-full rounded-xl border border-blue-100 bg-blue-50 p-3 text-center">
                      <p className="text-2xl font-bold text-blue-700">{columnas.length}</p>
                      <p className="text-xs text-blue-600 font-medium">Columnas detectadas en el archivo</p>
                    </div>
                  )}
                </div>
              )}

              {/* Processing — live thermometer */}
              {step === "processing" && (
                <div className="flex flex-col items-center gap-4 w-full">
                  {/* Pulsing glow + spinner ring */}
                  <div className="relative flex items-center justify-center">
                    <div className="absolute h-24 w-24 rounded-full bg-amber-400/20 animate-ping" style={{ animationDuration: "1.5s" }} />
                    <div className="absolute h-20 w-20 rounded-full bg-amber-400/10 animate-ping" style={{ animationDuration: "2s" }} />
                    <div className="relative z-10 flex h-16 w-16 items-center justify-center rounded-full bg-white border-2 border-amber-200 shadow-md">
                      <svg className="h-7 w-7 animate-spin text-amber-500" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                      </svg>
                    </div>
                  </div>
                  {/* Timer */}
                  <div className="text-center">
                    <p className="text-3xl font-bold tabular-nums text-slate-800">
                      {(elapsedMs / 1000).toFixed(2)}
                      <span className="text-base font-medium text-slate-400">s</span>
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">Tiempo de procesamiento</p>
                  </div>
                  {/* Status pills */}
                  <div className="w-full space-y-2">
                    <div className="flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                      <p className="text-xs text-amber-700 font-medium">Homologando códigos CUM via pgvector…</p>
                    </div>
                    <div className="flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-200 px-3 py-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" style={{ animationDelay: "0.3s" }} />
                      <p className="text-xs text-blue-700 font-medium">Celery worker procesando filas…</p>
                    </div>
                    <div className="flex items-center gap-2 rounded-lg bg-violet-50 border border-violet-200 px-3 py-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-pulse" style={{ animationDelay: "0.6s" }} />
                      <p className="text-xs text-violet-700 font-medium">Aplicando reglas de negocio…</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Review — results dashboard */}
              {step === "review" && (
                <div className="flex flex-col items-center gap-4 w-full">
                  {/* Progress ring */}
                  <div className="relative flex items-center justify-center">
                    <ProgressRing value={aprobadas} max={filas.length} size={96} strokeWidth={7} />
                    <div className="absolute text-center">
                      <p className="text-lg font-bold text-slate-800 leading-none">
                        {filas.length > 0 ? Math.round((aprobadas / filas.length) * 100) : 0}%
                      </p>
                      <p className="text-[9px] text-slate-400 font-medium">listo</p>
                    </div>
                  </div>
                  {/* Metric grid */}
                  <div className="grid grid-cols-2 gap-2 w-full">
                    <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-center">
                      <div className="flex items-center justify-center gap-1 mb-0.5">
                        <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">Auto-aprobadas</p>
                      </div>
                      <p className="text-2xl font-bold text-emerald-700">{aprobadas}</p>
                    </div>
                    <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-center">
                      <div className="flex items-center justify-center gap-1 mb-0.5">
                        <div className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                        <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600">Pendientes</p>
                      </div>
                      <p className="text-2xl font-bold text-amber-700">{pendientes}</p>
                    </div>
                  </div>
                  {/* Engine stats */}
                  <div className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500">Tiempo de motor</span>
                      <span className="font-bold tabular-nums text-slate-800">{elapsedSec}s</span>
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
                        <span className="font-bold text-violet-700">{indefinidos} filas</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </BentoBox>

          {/* ╔══════════════════════════════════════════════════════╗
              ║  BOX 3 — CO-PILOT INSIGHTS  (col-span-12)          ║
              ╚══════════════════════════════════════════════════════╝ */}
          {(detectedSupplier || indefinidos > 0 || step === "processing") && (
            <BentoBox className="lg:col-span-12">
              <div className="flex items-center gap-3 border-b border-violet-100 bg-violet-50/60 px-5 py-3">
                <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-600">
                  <svg className="h-3.5 w-3.5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm0 6v4l3 3"/>
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
                {detectedSupplier && (
                  <div className="flex-1 min-w-64 rounded-xl border border-violet-200 bg-violet-50 p-4">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-100">
                        <svg className="h-4 w-4 text-violet-600" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
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
                {indefinidos > 0 && (
                  <div className="flex-1 min-w-64 rounded-xl border border-teal-200 bg-teal-50 p-4">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-teal-100">
                        <svg className="h-4 w-4 text-teal-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M9 11l3 3L22 4"/>
                          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                        </svg>
                      </div>
                      <div>
                        <p className="text-xs font-bold text-teal-800">
                          {indefinidos} filas con vigencia indefinida
                        </p>
                        <p className="mt-0.5 text-xs text-teal-600 leading-snug">
                          El motor Polars marcó estas filas con <code className="rounded bg-teal-100 px-1 font-mono text-[10px]">fecha_vigencia_indefinida = true</code> y sustituyó las fechas vacías.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
                {step === "processing" && !detectedSupplier && !indefinidos && (
                  <div className="flex-1 min-w-64 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-200 animate-pulse">
                        <svg className="h-4 w-4 text-slate-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="11" cy="11" r="8"/>
                          <path d="m21 21-4.35-4.35"/>
                        </svg>
                      </div>
                      <div>
                        <p className="text-xs font-bold text-slate-700">Analizando firma del proveedor…</p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          El Co-Pilot está identificando el proveedor y las reglas aplicables.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </BentoBox>
          )}

          {/* ╔══════════════════════════════════════════════════════╗
              ║  BOX 4 — COMMAND CENTER  (col-span-12)             ║
              ╚══════════════════════════════════════════════════════╝ */}
          {step === "review" && (
            <BentoBox className="lg:col-span-12">
              {/* Command center header with publish CTA */}
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-800">
                    <svg className="h-4 w-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="3" y="3" width="18" height="18" rx="2"/>
                      <path d="M3 9h18M9 21V9"/>
                    </svg>
                  </div>
                  <div>
                    <span className="text-sm font-bold text-slate-800">Centro de Comandos</span>
                    <span className="ml-2 text-xs text-slate-400">— {filas.length} filas en staging</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => void onPublicar()}
                  disabled={loadingPublicar || aprobadas === 0}
                  className={`inline-flex items-center gap-2 rounded-xl px-6 py-2.5 text-sm font-bold text-white shadow-md transition-all duration-200 active:scale-95 ${
                    aprobadas > 0
                      ? "bg-teal-600 hover:bg-teal-700 hover:shadow-lg shadow-teal-200"
                      : "bg-slate-300 cursor-not-allowed"
                  } disabled:opacity-60`}
                >
                  {loadingPublicar ? (
                    <>
                      <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                      </svg>
                      Publicando al catálogo…
                    </>
                  ) : (
                    <>
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="m22 2-7 20-4-9-9-4 20-7z"/>
                      </svg>
                      Publicar {aprobadas} precio{aprobadas !== 1 ? "s" : ""} al catálogo
                    </>
                  )}
                </button>
              </div>

              {/* Rows table */}
              <div className="divide-y divide-slate-100">
                {filas.map((fila) => {
                  const sugerencias  = parseSugerencias(fila.sugerenciasCum);
                  const override     = filasState[fila.id] ?? "";
                  const isAprobado   = fila.estadoHomologacion === "APROBADO";
                  const isExpanded   = expandedRow === fila.id;
                  const topSugerencia = sugerencias[0];

                  return (
                    <div key={fila.id} className={`transition-colors duration-200 ${isAprobado ? "bg-white" : "bg-amber-50/40"}`}>
                      {/* Row summary — always visible */}
                      <button
                        type="button"
                        onClick={() => setExpandedRow(isExpanded ? null : fila.id)}
                        className="flex w-full cursor-pointer items-center gap-3 px-5 py-3 text-left hover:bg-slate-50/80 transition-colors"
                        aria-expanded={isExpanded}
                      >
                        {/* Status indicator */}
                        <div className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${
                          isAprobado ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                        }`}>
                          {isAprobado ? "✓" : "!"}
                        </div>
                        {/* Row number */}
                        <span className="w-12 shrink-0 text-[10px] font-medium text-slate-400 tabular-nums">
                          #{fila.filaNumero}
                        </span>
                        {/* Description */}
                        <span className="flex-1 truncate text-sm font-medium text-slate-700">
                          {fila.descripcionRaw ?? "Sin descripción"}
                        </span>
                        {/* CUM code */}
                        {fila.cumCode && (
                          <span className="hidden shrink-0 rounded bg-slate-100 px-2 py-0.5 font-mono text-[10px] text-slate-600 sm:inline">
                            {fila.cumCode}
                          </span>
                        )}
                        {/* Prices inline summary */}
                        <div className="hidden shrink-0 items-center gap-3 text-xs text-slate-500 lg:flex">
                          {fila.precioUnitario != null && <span>{formatPrice(fila.precioUnitario)}</span>}
                          {fila.porcentajeIva != null && (
                            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                              IVA {(fila.porcentajeIva * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                        {/* Confidence badge */}
                        {fila.confianzaScore != null && (
                          <span className={`hidden shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold sm:inline ${scoreBg(fila.confianzaScore)} ${scoreColor(fila.confianzaScore)}`}>
                            {(fila.confianzaScore * 100).toFixed(0)}%
                          </span>
                        )}
                        {/* Chevron */}
                        <svg
                          className={`h-4 w-4 shrink-0 text-slate-300 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                        >
                          <polyline points="6 9 12 15 18 9"/>
                        </svg>
                      </button>

                      {/* Expanded detail panel */}
                      {isExpanded && (
                        <div className="border-t border-slate-100 bg-slate-50/60 px-5 py-4 space-y-4">
                          {/* Price pills row */}
                          <div className="flex flex-wrap gap-2">
                            {fila.precioUnitario   != null && <span className="rounded-lg bg-white border border-slate-200 px-3 py-1 text-xs"><span className="text-slate-400">Unitario </span><strong>{formatPrice(fila.precioUnitario)}</strong></span>}
                            {fila.precioUnidad     != null && <span className="rounded-lg bg-white border border-slate-200 px-3 py-1 text-xs"><span className="text-slate-400">UMD </span><strong>{formatPrice(fila.precioUnidad)}</strong></span>}
                            {fila.precioPresentacion != null && <span className="rounded-lg bg-white border border-slate-200 px-3 py-1 text-xs"><span className="text-slate-400">Caja </span><strong>{formatPrice(fila.precioPresentacion)}</strong></span>}
                            {fila.fechaVigenciaIndefinida && <Pill label="Vigencia indefinida" color="violet" />}
                          </div>

                          {/* CUM suggestions — only for PENDIENTE */}
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
                                  className={`flex w-full items-center justify-between gap-2 rounded-xl border bg-white px-4 py-2.5 text-left text-xs transition-all duration-150 hover:border-teal-300 hover:bg-teal-50 hover:shadow-sm ${sug === topSugerencia ? "border-teal-200" : "border-slate-200"}`}
                                >
                                  <div className="min-w-0">
                                    <span className="font-semibold text-slate-800">{sug.nombre}</span>
                                    {sug.principio_activo && (
                                      <span className="ml-2 text-slate-500">{sug.principio_activo}</span>
                                    )}
                                    {sug.laboratorio && (
                                      <span className="ml-2 text-slate-400">· {sug.laboratorio}</span>
                                    )}
                                    <span className="ml-2 rounded bg-slate-100 px-1 py-px font-mono text-[10px] text-slate-500">{sug.id_cum}</span>
                                  </div>
                                  <div className="flex shrink-0 items-center gap-2">
                                    {sug === topSugerencia && (
                                      <span className="rounded-full bg-teal-100 px-2 py-px text-[9px] font-bold text-teal-700">TOP</span>
                                    )}
                                    <span className={`w-10 text-right font-bold tabular-nums ${scoreColor(sug.score)}`}>
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

                          {/* Manual CUM input — only for PENDIENTE */}
                          {!isAprobado && (
                            <div className="flex items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white p-3">
                              <svg className="h-4 w-4 shrink-0 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                              </svg>
                              <input
                                value={override}
                                onChange={(e) =>
                                  setFilasState((prev) => ({ ...prev, [fila.id]: e.target.value }))
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

                          {/* Approved state */}
                          {isAprobado && (
                            <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5">
                              <svg className="h-4 w-4 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                <polyline points="20 6 9 17 4 12"/>
                              </svg>
                              <span className="text-xs font-semibold text-emerald-700">
                                CUM aprobado: <code className="rounded bg-emerald-100 px-1.5 py-px font-mono text-emerald-800">{fila.cumCode}</code>
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
                    {pendientes} fila{pendientes !== 1 ? "s" : ""} requiere{pendientes === 1 ? "" : "n"} revisión manual
                  </p>
                )}
              </div>
            </BentoBox>
          )}
        </div>
      )}
    </section>
  );
}
