import { gql, useMutation, useQuery } from "@apollo/client";
import { lazy, Suspense, useMemo, useState } from "react";

import ProcessingCenter from "./ProcessingCenter";
import type { OrphanItem } from "./ResultsDashboard";

const ResultsDashboard = lazy(() =>
  import("./ResultsDashboard").then((module) => ({ default: module.ResultsDashboard })),
);
const QuarantineView = lazy(() =>
  import("./QuarantineView").then((module) => ({ default: module.QuarantineView })),
);

function LoaderCard() {
  return (
    <div className="mx-auto w-full max-w-6xl rounded-3xl border border-white/30 bg-white/60 p-6 shadow-[0_8px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <div className="h-4 w-4 animate-pulse rounded-full bg-cyan-500" />
        <p className="text-sm font-medium text-slate-700">Cargando componentes inteligentes...</p>
      </div>
      <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-slate-200/80">
        <div className="h-full w-1/3 animate-[pulse_1.2s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-500" />
      </div>
    </div>
  );
}

const SUBIR_ARCHIVO_PROVEEDOR = gql`
  mutation SubirArchivoProveedorFlow($file: Upload!) {
    subirArchivoProveedor(file: $file) {
      id
      filename
      mapeoSugerido
      status
    }
  }
`;

const CONFIRMAR_MAPEO_PROVEEDOR = gql`
  mutation ConfirmarMapeoProveedorFlow($archivoId: ID!, $mapeo: MapeoColumnasInput!) {
    confirmarMapeoProveedor(archivoId: $archivoId, mapeo: $mapeo) {
      ok
      mensaje
      taskId
      archivo {
        id
        filename
        status
      }
    }
  }
`;

const CONSULTAR_ESTADO_TAREA = gql`
  query ConsultarEstadoTareaFlow($taskId: String!) {
    consultarEstadoTarea(taskId: $taskId) {
      taskId
      status
      mensaje
      progressPct
      resultado
      error
    }
  }
`;

type UploadResponse = {
  subirArchivoProveedor: {
    id: string;
    filename: string;
    status: string;
    mapeoSugerido?: string | null;
  };
};

type ConfirmResponse = {
  confirmarMapeoProveedor: {
    ok: boolean;
    mensaje: string;
    taskId?: string | null;
    archivo: {
      id: string;
      filename: string;
      status: string;
    };
  };
};

type StatusResponse = {
  consultarEstadoTarea: {
    taskId: string;
    status: string;
    mensaje: string;
    progressPct?: number | null;
    resultado?: unknown;
    error?: string | null;
  };
};

type MapeoColumnasInput = {
  cumCode?: string;
  precioUnitario?: string;
  precioUnidad?: string;
  precioPresentacion?: string;
  porcentajeIva?: string;
  descripcion?: string;
  vigenteDesde?: string;
  vigenteHasta?: string;
};

function normalizeMapeo(rawMapeo?: string | null): MapeoColumnasInput {
  if (!rawMapeo) {
    return {
      cumCode: "cum",
      precioUnitario: "precio",
      descripcion: "descripcion",
    };
  }

  try {
    const parsed = JSON.parse(rawMapeo) as Record<string, string>;
    return {
      cumCode: parsed.cumCode ?? parsed.cum_code ?? parsed.cum,
      precioUnitario: parsed.precioUnitario ?? parsed.precio_unitario ?? parsed.precio_proveedor ?? parsed.precio,
      precioUnidad: parsed.precioUnidad ?? parsed.precio_unidad,
      precioPresentacion: parsed.precioPresentacion ?? parsed.precio_presentacion,
      porcentajeIva: parsed.porcentajeIva ?? parsed.porcentaje_iva,
      descripcion: parsed.descripcion ?? parsed.texto_original,
      vigenteDesde: parsed.vigenteDesde ?? parsed.vigente_desde,
      vigenteHasta: parsed.vigenteHasta ?? parsed.vigente_hasta,
    };
  } catch {
    return {
      cumCode: "cum",
      precioUnitario: "precio",
      descripcion: "descripcion",
    };
  }
}

function buildOrphanRows(resultData: unknown): OrphanItem[] {
  const payload = (typeof resultData === "object" && resultData !== null
    ? (resultData as Record<string, unknown>)
    : {}) as Record<string, unknown>;

  const listCandidate = payload.orphanItems ?? payload.topOrphans ?? payload.huerfanos ?? payload.orphans;
  if (Array.isArray(listCandidate)) {
    const parsedRows: OrphanItem[] = [];
    listCandidate.forEach((item, idx) => {
      if (typeof item !== "object" || item === null) return;
      const row = item as Record<string, unknown>;
      const cum = String(row.cum ?? row.cum_recibido ?? `N/A-${idx + 1}`);
      const descripcion = String(row.descripcion ?? row.texto_original ?? "Sin descripcion");
      const frecuencia = Number(row.frecuencia ?? row.count ?? 1);
      parsedRows.push({
        cum,
        descripcion,
        frecuencia: Number.isFinite(frecuencia) ? frecuencia : 1,
        estado: "Pendiente",
      });
    });
    return parsedRows;
  }

  const orphanCountRaw = Number(payload.orphan_rows ?? payload.orphanCount ?? 0);
  const orphanCount = Number.isFinite(orphanCountRaw) ? Math.max(0, orphanCountRaw) : 0;
  return Array.from({ length: Math.min(orphanCount, 10) }, (_, idx) => ({
    cum: `HUERFANO-${String(idx + 1).padStart(3, "0")}`,
    descripcion: "Pendiente de homologacion contra maestro CUM",
    frecuencia: Math.max(1, Math.floor(orphanCount / 3)),
    estado: "Pendiente",
  }));
}

export function TarifasProcessingModule() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);

  const [subirArchivoProveedor, { loading: loadingUpload }] = useMutation<UploadResponse>(SUBIR_ARCHIVO_PROVEEDOR);
  const [confirmarMapeoProveedor, { loading: loadingConfirm }] = useMutation<ConfirmResponse>(CONFIRMAR_MAPEO_PROVEEDOR);

  const { data: taskData } = useQuery<StatusResponse>(CONSULTAR_ESTADO_TAREA, {
    variables: { taskId: taskId ?? "" },
    skip: !taskId,
    pollInterval: taskId ? 2000 : 0,
    fetchPolicy: "network-only",
  });

  const taskStatus = taskData?.consultarEstadoTarea;
  const progressPct = taskStatus?.progressPct ?? 0;
  const status = taskStatus?.status ?? "PENDING";
  const isCompleted = status === "SUCCESS" || progressPct >= 100;

  const metrics = useMemo(() => {
    const result = taskStatus?.resultado;
    const payload = (typeof result === "object" && result !== null
      ? (result as Record<string, unknown>)
      : {}) as Record<string, unknown>;

    const matchedCount = Number(payload.matched_rows ?? payload.matchedCount ?? 0);
    const orphanCount = Number(payload.orphan_rows ?? payload.orphanCount ?? 0);

    return {
      matchedCount: Number.isFinite(matchedCount) ? Math.max(0, matchedCount) : 0,
      orphanCount: Number.isFinite(orphanCount) ? Math.max(0, orphanCount) : 0,
      orphanRows: buildOrphanRows(result),
    };
  }, [taskStatus?.resultado]);

  const handleStartFlow = async (file: File | null) => {
    if (!file) {
      setErrorMsg("Selecciona un archivo de lista de precios antes de iniciar el cruce.");
      return;
    }

    setErrorMsg(null);
    setSelectedFileName(file.name);

    try {
      const uploadResponse = await subirArchivoProveedor({ variables: { file } });
      const uploadData = uploadResponse.data?.subirArchivoProveedor;
      if (!uploadData?.id) {
        throw new Error("No fue posible registrar el archivo en el backend.");
      }

      const mapeo = normalizeMapeo(uploadData.mapeoSugerido);
      const confirmResponse = await confirmarMapeoProveedor({
        variables: {
          archivoId: uploadData.id,
          mapeo,
        },
      });

      const nextTaskId = confirmResponse.data?.confirmarMapeoProveedor?.taskId;
      if (!nextTaskId) {
        throw new Error("No se recibio taskId para seguimiento del procesamiento.");
      }

      setTaskId(nextTaskId);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Error inesperado al iniciar el cruce.";
      setErrorMsg(msg);
    }
  };

  return (
    <section className="space-y-4">
      <header className="mx-auto w-full max-w-6xl px-2">
        <p className="text-xs font-semibold uppercase tracking-widest text-teal-600">Python Meds</p>
        <h2 className="text-2xl font-bold text-slate-900">Ingesta y Cruce Inteligente de Tarifas</h2>
        <p className="mt-1 text-sm text-slate-600">
          Centro de procesamiento en tiempo real con seguimiento de Celery y resultados del grafo.
        </p>
      </header>

      {(errorMsg || taskStatus?.error) && (
        <div className="mx-auto w-full max-w-6xl rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {errorMsg ?? taskStatus?.error}
        </div>
      )}

      {selectedFileName && (
        <div className="mx-auto w-full max-w-6xl rounded-2xl border border-slate-200 bg-white/70 px-4 py-2 text-sm text-slate-600 backdrop-blur-sm">
          Archivo activo: <span className="font-medium text-slate-900">{selectedFileName}</span>
        </div>
      )}

      <ProcessingCenter
        progressPct={progressPct}
        isProcessing={Boolean(taskId) && !isCompleted}
        isCompleted={isCompleted}
        onStartAudit={handleStartFlow}
      />

      {Boolean(taskId) && (
        <div className="mx-auto w-full max-w-6xl rounded-2xl border border-slate-200 bg-white/70 px-4 py-2 text-xs text-slate-500 backdrop-blur-sm">
          Estado: {taskStatus?.status ?? "PENDING"} · {taskStatus?.mensaje ?? "Preparando flujo"}
          {(loadingUpload || loadingConfirm) && <span> · Inicializando pipeline...</span>}
        </div>
      )}

      {isCompleted && (
        <Suspense fallback={<LoaderCard />}>
          <>
            <ResultsDashboard
              matchedCount={metrics.matchedCount}
              orphanCount={metrics.orphanCount}
              topOrphans={metrics.orphanRows}
            />
            <QuarantineView rows={metrics.orphanRows.filter((row) => row.estado === "Pendiente")} />
          </>
        </Suspense>
      )}
    </section>
  );
}
