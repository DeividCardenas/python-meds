// ---------------------------------------------------------------------------
// Step types & constants
// ---------------------------------------------------------------------------

export type Step = "upload" | "mapping" | "processing" | "review" | "done";

export const STEP_ORDER: Step[] = [
  "upload",
  "mapping",
  "processing",
  "review",
  "done",
];

export const STEP_LABELS: Record<Step, string> = {
  upload: "Ingestión",
  mapping: "Mapeo",
  processing: "Motor",
  review: "Revisión",
  done: "Publicado",
};

// ---------------------------------------------------------------------------
// Field definitions for the column mapping form
// ---------------------------------------------------------------------------

export const CAMPOS: Array<{
  key: string;
  label: string;
  description: string;
}> = [
  {
    key: "cum_code",
    label: "Código CUM",
    description: "Código único de medicamento",
  },
  {
    key: "descripcion",
    label: "Descripción / Nombre",
    description: "Nombre o descripción del producto",
  },
  {
    key: "precio_unitario",
    label: "Precio Unitario",
    description: "Precio por unidad – columna genérica",
  },
  {
    key: "precio_unidad",
    label: "Precio Unidad Mínima",
    description: "Precio UMD / unidad mínima de dispensación",
  },
  {
    key: "precio_presentacion",
    label: "Precio Presentación",
    description: "Precio por caja / presentación",
  },
  {
    key: "porcentaje_iva",
    label: "IVA (%)",
    description: "Porcentaje de IVA (ej. 19 o 0.19)",
  },
  {
    key: "vigente_desde",
    label: "Vigente Desde",
    description: "Fecha inicio de vigencia",
  },
  {
    key: "vigente_hasta",
    label: "Vigente Hasta",
    description: "Fecha fin de vigencia",
  },
];
