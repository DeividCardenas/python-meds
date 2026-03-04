import { useMutation, useQuery } from "@apollo/client";
import { useEffect, useState } from "react";

import {
    AprobarStagingFilaDocument,
    GetStagingFilasDocument,
} from "../../../graphql/generated";

import type { Fila } from "../types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface UseStagingFilasProps {
  archivoId: string | null;
  /** True while the engine is running (step === "processing"). */
  active: boolean;
  /** Called once polling detects that rows are ready. */
  onFilasLoaded: () => void;
}

// ---------------------------------------------------------------------------
// Return shape
// ---------------------------------------------------------------------------

export interface UseStagingFilasReturn {
  filas: Fila[];
  /** Per-row manual CUM override values keyed by fila.id */
  filasState: Record<string, string>;
  setFilasState: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  expandedRow: string | null;
  setExpandedRow: React.Dispatch<React.SetStateAction<string | null>>;
  loading: boolean;
  aprobarFila: (filaId: string, idCum: string) => Promise<void>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useStagingFilas({
  archivoId,
  active,
  onFilasLoaded,
}: UseStagingFilasProps): UseStagingFilasReturn {
  const [filas, setFilas] = useState<Fila[]>([]);
  const [filasState, setFilasState] = useState<Record<string, string>>({});
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const { data, startPolling, stopPolling } = useQuery(GetStagingFilasDocument, {
    variables: { archivoId: archivoId ?? "" },
    skip: !archivoId || !active,
    fetchPolicy: "network-only",
  });

  // Start / stop polling based on active flag
  useEffect(() => {
    if (active && archivoId) {
      startPolling(2000);
    } else {
      stopPolling();
    }
  }, [active, archivoId, startPolling, stopPolling]);

  // Consume polling result — once we have rows, stop and signal parent
  useEffect(() => {
    if (data && data.getStagingFilas.length > 0) {
      stopPolling();
      setFilas(data.getStagingFilas);
      onFilasLoaded();
    }
    // onFilasLoaded intentionally excluded to avoid re-runs on parent re-renders
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, stopPolling]);

  // Reset local state when archivoId changes (new upload)
  useEffect(() => {
    if (!archivoId) {
      setFilas([]);
      setFilasState({});
      setExpandedRow(null);
    }
  }, [archivoId]);

  const [aprobarFilaMutation] = useMutation(AprobarStagingFilaDocument);

  const aprobarFila = async (filaId: string, idCum: string) => {
    await aprobarFilaMutation({ variables: { stagingId: filaId, idCum } });
    setFilas((prev) =>
      prev.map((f) =>
        f.id === filaId
          ? { ...f, estadoHomologacion: "APROBADO", cumCode: idCum }
          : f,
      ),
    );
  };

  return {
    filas,
    filasState,
    setFilasState,
    expandedRow,
    setExpandedRow,
    loading: active && filas.length === 0,
    aprobarFila,
  };
}
