import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
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
// Types & helpers
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
  { key: "cum_code",           label: "Código CUM",            description: "Código único de medicamento" },
  { key: "descripcion",        label: "Descripción / Nombre",  description: "Nombre o descripción del producto" },
  { key: "precio_unitario",    label: "Precio Unitario",        description: "Precio por unidad – columna genérica" },
  { key: "precio_unidad",      label: "Precio Unidad Mínima",  description: "Precio UMD / unidad mínima de dispensación" },
  { key: "precio_presentacion",label: "Precio Presentación",   description: "Precio por caja / presentación" },
  { key: "porcentaje_iva",     label: "IVA (%)",               description: "Porcentaje de IVA (ej. 19 o 0.19)" },
  { key: "vigente_desde",      label: "Vigente Desde",         description: "Fecha inicio de vigencia" },
  { key: "vigente_hasta",      label: "Vigente Hasta",         description: "Fecha fin de vigencia" },
];

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
    ? new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 2 }).format(v)
    : "—";

const scoreColor = (s: number) =>
  s >= 0.99 ? "text-emerald-600" : s >= 0.8 ? "text-amber-600" : "text-red-500";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CargaProveedor() {
  const [step, setStep] = useState<Step>("upload");
  const [archivoId, setArchivoId] = useState<string | null>(null);
  const [columnas, setColumnas] = useState<string[]>([]);
  const [mapeo, setMapeo] = useState<Record<string, string>>({});
  const [filas, setFilas] = useState<Fila[]>([]);
  const [filasState, setFilasState] = useState<Record<string, string>>({}); // id → cumCode override
  const [publicado, setPublicado] = useState<{ filasPublicadas: number } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Mutations ─────────────────────────────────────────────────────────────
  const [subirArchivo, { loading: loadingSubir }] = useMutation(SubirArchivoProveedorDocument);
  const [confirmarMapeo, { loading: loadingConfirmar }] = useMutation(ConfirmarMapeoProveedorDocument);
  const [aprobarFila] = useMutation(AprobarStagingFilaDocument);
  const [publicarPrecios, { loading: loadingPublicar }] = useMutation(PublicarPreciosProveedorDocument);

  // ── Polling staging rows ──────────────────────────────────────────────────
  const { data: stagingData, startPolling, stopPolling } = useQuery(GetStagingFilasDocument, {
    variables: { archivoId: archivoId ?? "" },
    skip: !archivoId || step !== "processing",
    fetchPolicy: "network-only",
  });

  useEffect(() => {
    if (step === "processing" && archivoId) {
      startPolling(2000);
    } else {
      stopPolling();
    }
  }, [step, archivoId, startPolling, stopPolling]);

  useEffect(() => {
    if (stagingData && stagingData.getStagingFilas.length > 0) {
      stopPolling();
      setFilas(stagingData.getStagingFilas);
      setStep("review");
    }
  }, [stagingData, stopPolling]);

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleFile = useCallback(async (file: File) => {
    setErrorMsg(null);
    try {
      const { data } = await subirArchivo({ variables: { file } });
      const result = data?.subirArchivoProveedor;
      if (!result) throw new Error("Respuesta vacía del servidor");

      setArchivoId(result.id);
      const cols = result.columnasDetectadas ?? [];
      setColumnas(cols);

      // Parse suggested mapping
      let sugerido: Record<string, string> = {};
      if (result.mapeoSugerido) {
        try { sugerido = JSON.parse(result.mapeoSugerido) as Record<string, string>; } catch { /* ignore */ }
      }
      setMapeo(sugerido);
      setStep("mapping");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Error al subir el archivo");
    }
  }, [subirArchivo]);

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
        prev.map((f: Fila) => (f.id === filaId ? { ...f, estadoHomologacion: "APROBADO", cumCode: idCum } : f)),
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
    setColumnas([]);
    setMapeo({});
    setFilas([]);
    setFilasState({});
    setPublicado(null);
    setErrorMsg(null);
  };

  // ── Computed ──────────────────────────────────────────────────────────────
  const pendientes = filas.filter((f: Fila) => f.estadoHomologacion === "PENDIENTE").length;
  const aprobadas  = filas.filter((f: Fila) => f.estadoHomologacion === "APROBADO").length;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <section className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Carga de Tarifario Proveedor</h2>
        <p className="mt-1 text-sm text-slate-500">
          Sube un archivo CSV o XLSX con precios de proveedor, mapea las columnas y publica al catálogo.
        </p>
      </div>

      {/* Stepper */}
      <ol className="flex items-center gap-3 text-xs font-medium">
        {(["upload", "mapping", "processing", "review", "done"] as Step[]).map((s, idx) => {
          const labels: Record<Step, string> = {
            upload: "Subir", mapping: "Mapear", processing: "Procesando",
            review: "Revisar", done: "Publicado",
          };
          const done  = ["upload","mapping","processing","review","done"].indexOf(step) > idx;
          const active = step === s;
          return (
            <li key={s} className="flex items-center gap-1.5">
              <span className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] ${
                done ? "bg-teal-600 text-white" : active ? "bg-blue-600 text-white" : "bg-slate-200 text-slate-500"
              }`}>
                {done ? "✓" : idx + 1}
              </span>
              <span className={active ? "text-slate-900" : "text-slate-400"}>{labels[s]}</span>
              {idx < 4 && <span className="text-slate-300">›</span>}
            </li>
          );
        })}
      </ol>

      {/* Error banner */}
      {errorMsg && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMsg}
        </div>
      )}

      {/* ── Step: upload ── */}
      {step === "upload" && (
        <div
          onDragOver={(e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-16 transition ${
            dragOver ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50"
          }`}
        >
          <svg viewBox="0 0 24 24" className="h-12 w-12 fill-none stroke-slate-400 stroke-1.5" aria-hidden="true">
            <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
            <polyline points="16 8 12 4 8 8" />
            <line x1="12" y1="4" x2="12" y2="16" />
          </svg>
          {loadingSubir ? (
            <p className="text-sm font-medium text-blue-600 animate-pulse">Subiendo archivo…</p>
          ) : (
            <>
              <p className="text-sm font-medium text-slate-700">
                Arrastra tu archivo aquí, o <span className="text-blue-600 underline">haz clic para seleccionar</span>
              </p>
              <p className="text-xs text-slate-400">CSV · XLSX — máx. 10 MB</p>
            </>
          )}
          <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={onFileChange} />
        </div>
      )}

      {/* ── Step: mapping ── */}
      {step === "mapping" && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-6">
          <div>
            <h3 className="font-semibold text-slate-800">Mapeo de columnas</h3>
            <p className="mt-1 text-sm text-slate-500">
              Asocia cada campo estándar con la columna correspondiente del archivo.
              Las sugerencias automáticas ya están precargadas.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {CAMPOS.map(({ key, label, description }) => (
              <div key={key}>
                <label className="mb-1 block text-xs font-semibold text-slate-600">{label}</label>
                <p className="mb-1.5 text-xs text-slate-400">{description}</p>
                <select
                  value={mapeo[key] ?? ""}
                  onChange={(e) => setMapeo((prev) => ({ ...prev, [key]: e.target.value }))}
                  className="h-9 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
                >
                  <option value="">— No mapear —</option>
                  {columnas.map((col) => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onReset}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => void onConfirmarMapeo()}
              disabled={loadingConfirmar}
              className="rounded-lg bg-teal-600 px-6 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 disabled:opacity-60"
            >
              {loadingConfirmar ? "Enviando…" : "Confirmar y procesar"}
            </button>
          </div>
        </div>
      )}

      {/* ── Step: processing ── */}
      {step === "processing" && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-slate-200 bg-white p-14 shadow-sm">
          <svg className="h-10 w-10 animate-spin text-teal-600" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-sm font-medium text-slate-700">Procesando archivo y homologando CUMs…</p>
          <p className="text-xs text-slate-400">Esto puede tomar algunos segundos</p>
        </div>
      )}

      {/* ── Step: review ── */}
      {step === "review" && (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white px-5 py-3 shadow-sm">
            <div className="flex gap-6 text-sm">
              <span className="text-slate-500">Total: <strong className="text-slate-800">{filas.length}</strong></span>
              <span className="text-emerald-600">Aprobados: <strong>{aprobadas}</strong></span>
              <span className="text-amber-600">Pendientes: <strong>{pendientes}</strong></span>
            </div>
            <button
              type="button"
              onClick={() => void onPublicar()}
              disabled={loadingPublicar || aprobadas === 0}
              className="rounded-lg bg-teal-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loadingPublicar ? "Publicando…" : `Publicar ${aprobadas} filas aprobadas`}
            </button>
          </div>

          {/* Rows */}
          <div className="space-y-3">
            {filas.map((fila) => {
              const sugerencias = parseSugerencias(fila.sugerenciasCum);
              const override = filasState[fila.id] ?? "";
              const isAprobado = fila.estadoHomologacion === "APROBADO";

              return (
                <article
                  key={fila.id}
                  className={`rounded-xl border p-4 shadow-sm ${
                    isAprobado ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"
                  }`}
                >
                  <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-xs text-slate-400">Fila #{fila.filaNumero}</p>
                      <p className="font-medium text-slate-800">{fila.descripcionRaw ?? "Sin descripción"}</p>
                      {fila.cumCode && (
                        <p className="mt-0.5 text-xs text-slate-500">CUM: <strong>{fila.cumCode}</strong></p>
                      )}
                      <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-600">
                        {fila.precioUnitario != null && <span>Precio: {formatPrice(fila.precioUnitario)}</span>}
                        {fila.precioUnidad != null && <span>UMD: {formatPrice(fila.precioUnidad)}</span>}
                        {fila.precioPresentacion != null && <span>Caja: {formatPrice(fila.precioPresentacion)}</span>}
                        {fila.porcentajeIva != null && (
                          <span>IVA: {(fila.porcentajeIva * 100).toFixed(0)}%</span>
                        )}
                      </div>
                    </div>
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      isAprobado ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                    }`}>
                      {fila.estadoHomologacion}
                    </span>
                  </div>

                  {/* CUM suggestions (only for PENDIENTE) */}
                  {!isAprobado && sugerencias.length > 0 && (
                    <div className="mb-3 space-y-1.5">
                      <p className="text-xs font-semibold text-slate-500">Sugerencias CUM:</p>
                      {sugerencias.map((sug) => (
                        <button
                          key={sug.id_cum}
                          type="button"
                          onClick={() => void onAprobar(fila.id, sug.id_cum)}
                          className="flex w-full items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-xs transition hover:border-teal-400 hover:bg-teal-50"
                        >
                          <div>
                            <span className="font-medium text-slate-800">{sug.nombre}</span>
                            {sug.principio_activo && (
                              <span className="ml-2 text-slate-500">{sug.principio_activo}</span>
                            )}
                            {sug.laboratorio && (
                              <span className="ml-2 text-slate-400">· {sug.laboratorio}</span>
                            )}
                          </div>
                          <span className={`shrink-0 font-semibold ${scoreColor(sug.score)}`}>
                            {(sug.score * 100).toFixed(0)}%
                          </span>
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Manual CUM entry */}
                  {!isAprobado && (
                    <div className="flex items-center gap-2">
                      <input
                        value={override}
                        onChange={(e) => setFilasState((prev) => ({ ...prev, [fila.id]: e.target.value }))}
                        placeholder="CUM manual (ej. 52477-01)"
                        className="h-8 flex-1 rounded-lg border border-slate-300 bg-white px-3 text-xs outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
                      />
                      <button
                        type="button"
                        disabled={!override.trim()}
                        onClick={() => void onAprobar(fila.id, override.trim())}
                        className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
                      >
                        Aprobar
                      </button>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Step: done ── */}
      {step === "done" && publicado && (
        <div className="flex flex-col items-center gap-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-14 text-center shadow-sm">
          <svg viewBox="0 0 24 24" className="h-12 w-12 fill-none stroke-emerald-500 stroke-2" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <path d="m9 12 2 2 4-4" />
          </svg>
          <div>
            <p className="text-lg font-semibold text-emerald-800">¡Precios publicados correctamente!</p>
            <p className="mt-1 text-sm text-emerald-700">
              <strong>{publicado.filasPublicadas}</strong> filas fueron publicadas al catálogo de precios.
            </p>
          </div>
          <button
            type="button"
            onClick={onReset}
            className="rounded-lg bg-teal-600 px-6 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700"
          >
            Cargar otro archivo
          </button>
        </div>
      )}
    </section>
  );
}
