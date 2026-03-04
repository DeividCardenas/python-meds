import type { GetStagingFilasQuery } from "../../graphql/generated";

// ---------------------------------------------------------------------------
// Domain types re-exported for subcomponents
// ---------------------------------------------------------------------------

/** A single row from the pricing staging table. */
export type Fila = GetStagingFilasQuery["getStagingFilas"][number];

/** A single CUM homologation suggestion returned by the engine. */
export type Sugerencia = {
  id_cum: string;
  nombre: string;
  score: number;
  principio_activo?: string | null;
  laboratorio?: string | null;
};

/** Shape returned by the publish mutation result used in DoneStep. */
export type PublicadoResult = {
  filasPublicadas: number;
};
