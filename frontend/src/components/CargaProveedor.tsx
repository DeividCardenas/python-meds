import { useState, type DragEvent, type FormEvent } from "react";
import { useMutation, useQuery } from "@apollo/client";

import {
  SubirArchivoProveedorDocument,
  ConfirmarMapeoProveedorDocument,
  AprobarStagingFilaDocument,
  GetStagingFilasDocument,
  type SubirArchivoProveedorMutation,
  type SubirArchivoProveedorMutationVariables,
  type ConfirmarMapeoProveedorMutation,
  type ConfirmarMapeoProveedorMutationVariables,
  type AprobarStagingFilaMutation,
  type AprobarStagingFilaMutationVariables,
  type GetStagingFilasQuery,
  type GetStagingFilasQueryVariables,
} from "../graphql/generated";

const STANDARD_FIELDS: { key: string; label: string; description: string }[] = [
  { key: "cum_code", label: "Código CUM", description: "Identificador único de medicamento" },
  { key: "precio_unitario", label: "Precio Unitario", description: "Precio por unidad de dispensación" },
  { key: "descripcion", label: "Descripción / Nombre", description: "Nombre o descripción del producto" },
  { key: "vigente_desde", label: "Vigente Desde", description: "Fecha de inicio de vigencia del precio" },
  { key: "vigente_hasta", label: "Vigente Hasta", description: "Fecha de fin de vigencia del precio" },
];

type Step = "upload" | "mapping" | "review";

type StagingFila = GetStagingFilasQuery["getStagingFilas"][number];

type Sugerencia = {
  id_cum: string;
  nombre: string;
  score: number;
  principio_activo?: string | null;
  laboratorio?: string | null;
};

function parseSugerencias(json: string | null | undefined): Sugerencia[] {
  if (!json) return [];
  try {
    return JSON.parse(json) as Sugerencia[];
  } catch {
    return [];
  }
}

const formatPrice = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 2 }).format(value)
    : "—";

export function CargaProveedor() {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [archivoId, setArchivoId] = useState<string | null>(null);
  const [columnas, setColumnas] = useState<string[]>([]);
  // mapping: standard field key → selected column name
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [manualCumInputs, setManualCumInputs] = useState<Record<string, string>>({});

  const [subirArchivo, { loading: loadingUpload, error: uploadError }] = useMutation<
    SubirArchivoProveedorMutation,
    SubirArchivoProveedorMutationVariables
  >(SubirArchivoProveedorDocument);

  const [confirmarMapeo, { loading: loadingMapeo, error: mapeoError }] = useMutation<
    ConfirmarMapeoProveedorMutation,
    ConfirmarMapeoProveedorMutationVariables
  >(ConfirmarMapeoProveedorDocument);

  const [aprobarFila, { loading: loadingApprove }] = useMutation<
    AprobarStagingFilaMutation,
    AprobarStagingFilaMutationVariables
  >(AprobarStagingFilaDocument);

  const { data: stagingData, loading: loadingStaging, refetch: refetchStaging } = useQuery<
    GetStagingFilasQuery,
    GetStagingFilasQueryVariables
  >(GetStagingFilasDocument, {
    variables: { archivoId: archivoId ?? "" },
    skip: !archivoId || step !== "review",
    fetchPolicy: "network-only",
  });

  const filas = stagingData?.getStagingFilas ?? [];
  const filasConCum = filas.filter((f) => f.cumCode);
  const filasSinCum = filas.filter((f) => !f.cumCode || f.estadoHomologacion === "PENDIENTE");

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------
  const onDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };
  const onDragLeave = () => setIsDragging(false);
  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    setFile(event.dataTransfer.files?.[0] ?? null);
  };

  const onUploadSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) return;
    const result = await subirArchivo({ variables: { file } });
    const payload = result.data?.subirArchivoProveedor;
    if (!payload) return;
    setArchivoId(payload.id);
    const cols = payload.columnasDetectadas ?? [];
    setColumnas(cols);
    // Pre-fill mapping from auto-detected suggestions
    if (payload.mapeoSugerido) {
      try {
        const suggested = JSON.parse(payload.mapeoSugerido) as Record<string, string>;
        // Backend returns {field: column}, we store as {field: column}
        setMapping(suggested);
      } catch {
        // ignore parse errors
      }
    }
    setStep("mapping");
  };

  const onMappingSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!archivoId) return;
    await confirmarMapeo({
      variables: {
        archivoId,
        mapeo: {
          cumCode: mapping["cum_code"] ?? null,
          precioUnitario: mapping["precio_unitario"] ?? null,
          descripcion: mapping["descripcion"] ?? null,
          vigentDesde: mapping["vigente_desde"] ?? null,
          vigentHasta: mapping["vigente_hasta"] ?? null,
        },
      },
    });
    setStep("review");
  };

  const onAprobarFila = async (fila: StagingFila, cumCode: string) => {
    if (!cumCode.trim()) return;
    setApprovingId(fila.id);
    await aprobarFila({ variables: { stagingId: fila.id, idCum: cumCode.trim() } });
    setApprovingId(null);
    setManualCumInputs((prev) => ({ ...prev, [fila.id]: "" }));
    await refetchStaging();
  };

  // -------------------------------------------------------------------------
  // Render helpers
  // -------------------------------------------------------------------------
  const stepIndicator = (label: string, current: Step, target: Step) => {
    const isActive = current === target;
    const isDone =
      (target === "upload" && (current === "mapping" || current === "review")) ||
      (target === "mapping" && current === "review");
    return (
      <div className={`flex items-center gap-2 text-sm font-medium ${isActive ? "text-blue-600" : isDone ? "text-teal-600" : "text-slate-400"}`}>
        <span
          className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
            isActive ? "bg-blue-600 text-white" : isDone ? "bg-teal-600 text-white" : "bg-slate-200 text-slate-500"
          }`}
        >
          {isDone ? "✓" : target === "upload" ? "1" : target === "mapping" ? "2" : "3"}
        </span>
        {label}
      </div>
    );
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-slate-900">Homologación de Precios Proveedor</h2>
        <p className="mt-1 text-sm text-slate-500">
          Carga listas de precios heterogéneas, mapea columnas a campos estándar y resuelve CUM faltantes.
        </p>
      </div>

      {/* Step indicator */}
      <div className="mb-8 flex items-center gap-6 border-b border-slate-100 pb-4">
        {stepIndicator("Cargar Archivo", step, "upload")}
        <span className="text-slate-300">→</span>
        {stepIndicator("Mapear Columnas", step, "mapping")}
        <span className="text-slate-300">→</span>
        {stepIndicator("Revisar &amp; Aprobar", step, "review")}
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Step 1: Upload                                                    */}
      {/* ---------------------------------------------------------------- */}
      {step === "upload" ? (
        <form onSubmit={(e) => void onUploadSubmit(e)} className="space-y-4">
          <label
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            className={`flex min-h-52 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${
              isDragging ? "border-blue-600 bg-blue-50" : "border-slate-300 bg-slate-50 hover:border-blue-500"
            }`}
          >
            <svg viewBox="0 0 24 24" className="mb-4 h-14 w-14 fill-none stroke-current text-slate-400" aria-hidden="true">
              <path d="M12 16V6m0 0-3.5 3.5M12 6l3.5 3.5" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M5 16.5a4.5 4.5 0 0 1 .9-8.9A6.5 6.5 0 0 1 18.6 9h.4a4 4 0 0 1 0 8H6.5" strokeWidth="1.75" strokeLinecap="round" />
            </svg>
            <p className="text-sm font-medium text-slate-700">Arrastra tu lista de precios aquí o haz clic para seleccionar</p>
            <p className="mt-1 text-xs text-slate-500">Formatos: .xlsx, .xls, .csv, .tsv, .txt</p>
            <input
              type="file"
              accept=".xlsx,.xls,.csv,.tsv,.txt"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="hidden"
            />
          </label>
          {file ? (
            <p className="text-sm text-slate-600">
              Archivo seleccionado: <span className="font-medium">{file.name}</span>
            </p>
          ) : null}
          {uploadError ? (
            <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">Error: {uploadError.message}</p>
          ) : null}
          <button
            type="submit"
            disabled={!file || loadingUpload}
            className="h-11 rounded-lg bg-blue-600 px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loadingUpload ? "Analizando columnas..." : "Cargar y detectar columnas"}
          </button>
        </form>
      ) : null}

      {/* ---------------------------------------------------------------- */}
      {/* Step 2: Column Mapper                                             */}
      {/* ---------------------------------------------------------------- */}
      {step === "mapping" ? (
        <form onSubmit={(e) => void onMappingSubmit(e)} className="space-y-6">
          <p className="text-sm text-slate-600">
            Selecciona qué columna del archivo del proveedor corresponde a cada campo estándar.
            Los campos con{" "}
            <span className="rounded bg-teal-100 px-1.5 py-0.5 text-xs font-semibold text-teal-700">Auto</span>{" "}
            fueron detectados automáticamente.
          </p>

          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Campo Estándar</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Descripción</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Columna del Proveedor</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {STANDARD_FIELDS.map((field) => {
                  const currentValue = mapping[field.key] ?? "";
                  const isAutoDetected = !!mapping[field.key];
                  return (
                    <tr key={field.key} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-medium text-slate-800">
                        {field.label}
                        {isAutoDetected ? (
                          <span className="ml-2 rounded bg-teal-100 px-1.5 py-0.5 text-xs font-semibold text-teal-700">
                            Auto
                          </span>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-slate-500">{field.description}</td>
                      <td className="px-4 py-3">
                        <select
                          value={currentValue}
                          onChange={(e) =>
                            setMapping((prev) => ({
                              ...prev,
                              [field.key]: e.target.value,
                            }))
                          }
                          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                        >
                          <option value="">— No mapear —</option>
                          {columnas.map((col) => (
                            <option key={col} value={col}>
                              {col}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {mapeoError ? (
            <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">Error: {mapeoError.message}</p>
          ) : null}

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setStep("upload")}
              className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              ← Volver
            </button>
            <button
              type="submit"
              disabled={loadingMapeo}
              className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loadingMapeo ? "Procesando filas..." : "Confirmar mapeo y procesar"}
            </button>
          </div>
        </form>
      ) : null}

      {/* ---------------------------------------------------------------- */}
      {/* Step 3: Review & Approve                                          */}
      {/* ---------------------------------------------------------------- */}
      {step === "review" ? (
        <div className="space-y-6">
          {loadingStaging ? (
            <p className="text-sm text-slate-500">Cargando filas de staging...</p>
          ) : (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-center">
                  <p className="text-2xl font-bold text-slate-900">{filas.length}</p>
                  <p className="mt-1 text-xs text-slate-500">Total en staging</p>
                </div>
                <div className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-center">
                  <p className="text-2xl font-bold text-teal-700">{filasConCum.length}</p>
                  <p className="mt-1 text-xs text-teal-600">Con CUM resuelto</p>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-center">
                  <p className="text-2xl font-bold text-amber-700">{filasSinCum.length}</p>
                  <p className="mt-1 text-xs text-amber-600">Requieren resolución</p>
                </div>
              </div>

              {/* Rows needing CUM resolution */}
              {filasSinCum.length > 0 ? (
                <div>
                  <h3 className="mb-3 text-base font-semibold text-slate-800">
                    Filas sin CUM — Resolución requerida
                  </h3>
                  <div className="space-y-3">
                    {filasSinCum.map((fila) => {
                      const sugerencias = parseSugerencias(fila.sugerenciasCum);
                      const isApproving = approvingId === fila.id;
                      return (
                        <div
                          key={fila.id}
                          className="rounded-xl border border-amber-200 bg-white p-4 shadow-sm"
                        >
                          <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                            <div>
                              <p className="text-xs text-slate-400">Fila #{fila.filaNumero}</p>
                              <p className="font-medium text-slate-800">
                                {fila.descripcionRaw ?? "Sin descripción"}
                              </p>
                              {fila.precioUnitario != null ? (
                                <p className="mt-0.5 text-sm text-slate-600">{formatPrice(fila.precioUnitario)}</p>
                              ) : null}
                            </div>
                            <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
                              {fila.estadoHomologacion}
                            </span>
                          </div>

                          {sugerencias.length > 0 ? (
                            <div className="mb-3">
                              <p className="mb-1.5 text-xs font-semibold text-slate-500">
                                Sugerencias de CUM (top {sugerencias.length}):
                              </p>
                              <div className="flex flex-wrap gap-2">
                                {sugerencias.map((sug) => (
                                  <button
                                    key={sug.id_cum}
                                    type="button"
                                    disabled={isApproving || loadingApprove}
                                    onClick={() => void onAprobarFila(fila, sug.id_cum)}
                                    className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-left transition hover:bg-blue-100 disabled:opacity-50"
                                  >
                                    <p className="text-xs font-bold text-blue-700">{sug.id_cum}</p>
                                    <p className="text-xs text-slate-700">{sug.nombre}</p>
                                    {sug.laboratorio ? (
                                      <p className="text-xs text-slate-400">{sug.laboratorio}</p>
                                    ) : null}
                                  </button>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <p className="mb-3 text-xs text-slate-400">
                              No se encontraron sugerencias automáticas de CUM.
                            </p>
                          )}

                          {/* Manual CUM entry */}
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              placeholder="Ingresar CUM manualmente..."
                              value={manualCumInputs[fila.id] ?? ""}
                              onChange={(e) =>
                                setManualCumInputs((prev) => ({ ...prev, [fila.id]: e.target.value }))
                              }
                              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                            />
                            <button
                              type="button"
                              disabled={!manualCumInputs[fila.id]?.trim() || isApproving || loadingApprove}
                              onClick={() => void onAprobarFila(fila, manualCumInputs[fila.id] ?? "")}
                              className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {isApproving ? "..." : "Aprobar"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {/* Approved rows table */}
              {filasConCum.length > 0 ? (
                <div>
                  <h3 className="mb-3 text-base font-semibold text-slate-800">Filas con CUM resuelto</h3>
                  <div className="overflow-auto rounded-xl border border-slate-200">
                    <table className="min-w-full text-sm">
                      <thead className="bg-slate-50">
                        <tr>
                          <th className="px-3 py-2.5 text-left font-semibold text-slate-600">Fila #</th>
                          <th className="px-3 py-2.5 text-left font-semibold text-slate-600">CUM</th>
                          <th className="px-3 py-2.5 text-left font-semibold text-slate-600">Descripción</th>
                          <th className="px-3 py-2.5 text-right font-semibold text-slate-600">Precio</th>
                          <th className="px-3 py-2.5 text-center font-semibold text-slate-600">Estado</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {filasConCum.map((fila) => (
                          <tr key={fila.id} className="hover:bg-slate-50">
                            <td className="px-3 py-2.5 text-slate-500">#{fila.filaNumero}</td>
                            <td className="px-3 py-2.5 font-mono text-xs text-slate-700">
                              {fila.cumCode}
                            </td>
                            <td className="px-3 py-2.5 text-slate-700">
                              {fila.descripcionRaw ?? "—"}
                            </td>
                            <td className="px-3 py-2.5 text-right text-slate-700">
                              {formatPrice(fila.precioUnitario)}
                            </td>
                            <td className="px-3 py-2.5 text-center">
                              <span
                                className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                                  fila.estadoHomologacion === "APROBADO"
                                    ? "bg-teal-100 text-teal-700"
                                    : "bg-slate-100 text-slate-600"
                                }`}
                              >
                                {fila.estadoHomologacion}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              <button
                type="button"
                onClick={() => {
                  setStep("upload");
                  setFile(null);
                  setArchivoId(null);
                  setColumnas([]);
                  setMapping({});
                  setManualCumInputs({});
                }}
                className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              >
                Cargar otro archivo
              </button>
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
