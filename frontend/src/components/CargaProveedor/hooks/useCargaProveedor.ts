import { useMutation } from "@apollo/client";
import { useCallback, useEffect, useRef, useState } from "react";

import {
    ConfirmarMapeoProveedorDocument,
    PublicarPreciosProveedorDocument,
    SubirArchivoProveedorDocument,
} from "../../../graphql/generated";

import type { Step } from "../constants";
import type { PublicadoResult } from "../types";

// ---------------------------------------------------------------------------
// Return shape
// ---------------------------------------------------------------------------

export interface UseCargaProveedorReturn {
  // ── Flow state ─────────────────────────────────────────────────────────
  step: Step;
  setStep: (s: Step) => void;
  archivoId: string | null;
  filename: string | null;
  columnas: string[];
  mapeo: Record<string, string>;
  setMapeo: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  dragOver: boolean;
  setDragOver: React.Dispatch<React.SetStateAction<boolean>>;
  errorMsg: string | null;
  publicado: PublicadoResult | null;
  // ── Timing ────────────────────────────────────────────────────────────
  elapsedMs: number;
  finalElapsedMs: number | null;
  // ── Loading flags ─────────────────────────────────────────────────────
  loadingSubir: boolean;
  loadingConfirmar: boolean;
  loadingPublicar: boolean;
  // ── Handlers ──────────────────────────────────────────────────────────
  handleUpload: (file: File) => Promise<void>;
  handleConfirmarMapeo: () => Promise<void>;
  handlePublicar: () => Promise<void>;
  handleReset: () => void;
  /** Called by useStagingFilas when polling detects rows are ready. */
  handleProcessingComplete: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCargaProveedor(): UseCargaProveedorReturn {
  const [step, setStep] = useState<Step>("upload");
  const [archivoId, setArchivoId] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [columnas, setColumnas] = useState<string[]>([]);
  const [mapeo, setMapeo] = useState<Record<string, string>>({});
  const [publicado, setPublicado] = useState<PublicadoResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // ── Elapsed timer ──────────────────────────────────────────────────────
  const [elapsedMs, setElapsedMs] = useState(0);
  const [finalElapsedMs, setFinalElapsed] = useState<number | null>(null);
  const processingStartRef = useRef<number | null>(null);
  const elapsedIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  // ── Mutations ─────────────────────────────────────────────────────────
  const [subirArchivo, { loading: loadingSubir }] = useMutation(
    SubirArchivoProveedorDocument,
  );
  const [confirmarMapeo, { loading: loadingConfirmar }] = useMutation(
    ConfirmarMapeoProveedorDocument,
  );
  const [publicarPrecios, { loading: loadingPublicar }] = useMutation(
    PublicarPreciosProveedorDocument,
  );

  // ── Handlers ──────────────────────────────────────────────────────────

  const handleUpload = useCallback(
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
          try {
            sugerido = JSON.parse(result.mapeoSugerido) as Record<
              string,
              string
            >;
          } catch {
            /* ignore */
          }
        }
        setMapeo(sugerido);
        setStep("mapping");
      } catch (e) {
        setErrorMsg(
          e instanceof Error ? e.message : "Error al subir el archivo",
        );
      }
    },
    [subirArchivo],
  );

  const handleConfirmarMapeo = async () => {
    if (!archivoId) return;
    setErrorMsg(null);
    try {
      await confirmarMapeo({
        variables: {
          archivoId,
          mapeo: {
            cumCode: mapeo.cum_code ?? null,
            precioUnitario: mapeo.precio_unitario ?? null,
            precioUnidad: mapeo.precio_unidad ?? null,
            precioPresentacion: mapeo.precio_presentacion ?? null,
            porcentajeIva: mapeo.porcentaje_iva ?? null,
            descripcion: mapeo.descripcion ?? null,
            vigenteDesde: mapeo.vigente_desde ?? null,
            vigenteHasta: mapeo.vigente_hasta ?? null,
          },
        },
      });
      setStep("processing");
    } catch (e) {
      setErrorMsg(
        e instanceof Error ? e.message : "Error al confirmar el mapeo",
      );
    }
  };

  const handlePublicar = async () => {
    if (!archivoId) return;
    setErrorMsg(null);
    try {
      const { data } = await publicarPrecios({ variables: { archivoId } });
      setPublicado({
        filasPublicadas: data?.publicarPreciosProveedor.filasPublicadas ?? 0,
      });
      setStep("done");
    } catch (e) {
      setErrorMsg(
        e instanceof Error ? e.message : "Error al publicar los precios",
      );
    }
  };

  const handleProcessingComplete = useCallback(() => {
    if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
    setFinalElapsed(elapsedMs);
    setStep("review");
  }, [elapsedMs]);

  const handleReset = () => {
    setStep("upload");
    setArchivoId(null);
    setFilename(null);
    setColumnas([]);
    setMapeo({});
    setPublicado(null);
    setErrorMsg(null);
    setElapsedMs(0);
    setFinalElapsed(null);
  };

  return {
    step,
    setStep,
    archivoId,
    filename,
    columnas,
    mapeo,
    setMapeo,
    dragOver,
    setDragOver,
    errorMsg,
    publicado,
    elapsedMs,
    finalElapsedMs,
    loadingSubir,
    loadingConfirmar,
    loadingPublicar,
    handleUpload,
    handleConfirmarMapeo,
    handlePublicar,
    handleReset,
    handleProcessingComplete,
  };
}
