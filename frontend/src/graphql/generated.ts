import { gql, type TypedDocumentNode } from "@apollo/client";

export type SearchMedicamentosQueryVariables = {
  texto: string;
  empresa?: string | null;
};

export type SearchMedicamentosQuery = {
  buscarMedicamentos: Array<{
    id: string;
    nombreLimpio: string;
    distancia: number;
    idCum?: string | null;
    laboratorio?: string | null;
    formaFarmaceutica?: string | null;
    registroInvima?: string | null;
    principioActivo?: string | null;
    precioUnitario?: number | null;
    precioEmpaque?: number | null;
    esRegulado: boolean;
    precioMaximoRegulado?: number | null;
  }>;
};

export type ComparativaPreciosQueryVariables = {
  principioActivo: string;
};

export type ComparativaPreciosQuery = {
  comparativaPrecios: Array<{
    id: string;
    nombreLimpio: string;
    idCum?: string | null;
    laboratorio?: string | null;
    formaFarmaceutica?: string | null;
    principioActivo?: string | null;
    precioUnitario?: number | null;
    precioEmpaque?: number | null;
    esRegulado: boolean;
    precioMaximoRegulado?: number | null;
  }>;
};

export type CargarInvimaMutationVariables = {
  file: File;
};

export type CargarInvimaMutation = {
  cargarMaestroInvima: {
    id: string;
    filename: string;
    status: string;
  };
};

// ---------------------------------------------------------------------------
// Supplier pricing pipeline
// ---------------------------------------------------------------------------

export type SubirArchivoProveedorMutationVariables = {
  file: File;
};

export type SubirArchivoProveedorMutation = {
  subirArchivoProveedor: {
    id: string;
    filename: string;
    status: string;
    columnasDetectadas?: string[] | null;
    mapeoSugerido?: string | null;
  };
};

export type MapeoColumnasInput = {
  cumCode?: string | null;
  precioUnitario?: string | null;
  precioUnidad?: string | null;
  precioPresentacion?: string | null;
  porcentajeIva?: string | null;
  descripcion?: string | null;
  vigenteDesde?: string | null;
  vigenteHasta?: string | null;
};

export type ConfirmarMapeoProveedorMutationVariables = {
  archivoId: string;
  mapeo: MapeoColumnasInput;
};

export type ConfirmarMapeoProveedorMutation = {
  confirmarMapeoProveedor: {
    id: string;
    filename: string;
    status: string;
    columnasDetectadas?: string[] | null;
    mapeoSugerido?: string | null;
  };
};

export type AprobarStagingFilaMutationVariables = {
  stagingId: string;
  idCum: string;
};

export type AprobarStagingFilaMutation = {
  aprobarStagingFila: {
    id: string;
    filaNumero: number;
    cumCode?: string | null;
    precioUnitario?: number | null;
    precioUnidad?: number | null;
    precioPresentacion?: number | null;
    porcentajeIva?: number | null;
    descripcionRaw?: string | null;
    estadoHomologacion: string;
    sugerenciasCum?: string | null;
    datosRaw: string;
  };
};

export type GetStagingFilasQueryVariables = {
  archivoId: string;
};

export type GetStagingFilasQuery = {
  getStagingFilas: Array<{
    id: string;
    filaNumero: number;
    cumCode?: string | null;
    precioUnitario?: number | null;
    precioUnidad?: number | null;
    precioPresentacion?: number | null;
    porcentajeIva?: number | null;
    descripcionRaw?: string | null;
    estadoHomologacion: string;
    sugerenciasCum?: string | null;
    datosRaw: string;
  }>;
};

export type SugerenciasCUMQueryVariables = {
  texto: string;
};

export type SugerenciasCUMQuery = {
  sugerenciasCum: Array<{
    idCum: string;
    nombre: string;
    score: number;
    principioActivo?: string | null;
    laboratorio?: string | null;
  }>;
};

export const SearchMedicamentosDocument = gql`
  query SearchMedicamentos($texto: String!, $empresa: String) {
    buscarMedicamentos(texto: $texto, empresa: $empresa) {
      id
      nombreLimpio
      distancia
      idCum
      laboratorio
      formaFarmaceutica
      registroInvima
      principioActivo
      precioUnitario
      precioEmpaque
      esRegulado
      precioMaximoRegulado
    }
  }
` as TypedDocumentNode<SearchMedicamentosQuery, SearchMedicamentosQueryVariables>;

export const ComparativaPreciosDocument = gql`
  query ComparativaPrecios($principioActivo: String!) {
    comparativaPrecios(principioActivo: $principioActivo) {
      id
      nombreLimpio
      idCum
      laboratorio
      formaFarmaceutica
      principioActivo
      precioUnitario
      precioEmpaque
      esRegulado
      precioMaximoRegulado
    }
  }
` as TypedDocumentNode<ComparativaPreciosQuery, ComparativaPreciosQueryVariables>;

export const CargarInvimaDocument = gql`
  mutation CargarInvima($file: Upload!) {
    cargarMaestroInvima(file: $file) {
      id
      filename
      status
    }
  }
` as TypedDocumentNode<CargarInvimaMutation, CargarInvimaMutationVariables>;

export const SubirArchivoProveedorDocument = gql`
  mutation SubirArchivoProveedor($file: Upload!) {
    subirArchivoProveedor(file: $file) {
      id
      filename
      status
      columnasDetectadas
      mapeoSugerido
    }
  }
` as TypedDocumentNode<SubirArchivoProveedorMutation, SubirArchivoProveedorMutationVariables>;

export const ConfirmarMapeoProveedorDocument = gql`
  mutation ConfirmarMapeoProveedor($archivoId: ID!, $mapeo: MapeoColumnasInput!) {
    confirmarMapeoProveedor(archivoId: $archivoId, mapeo: $mapeo) {
      id
      filename
      status
      columnasDetectadas
      mapeoSugerido
    }
  }
` as TypedDocumentNode<ConfirmarMapeoProveedorMutation, ConfirmarMapeoProveedorMutationVariables>;

export const AprobarStagingFilaDocument = gql`
  mutation AprobarStagingFila($stagingId: ID!, $idCum: String!) {
    aprobarStagingFila(stagingId: $stagingId, idCum: $idCum) {
      id
      filaNumero
      cumCode
      precioUnitario
      precioUnidad
      precioPresentacion
      porcentajeIva
      descripcionRaw
      estadoHomologacion
      sugerenciasCum
      datosRaw
    }
  }
` as TypedDocumentNode<AprobarStagingFilaMutation, AprobarStagingFilaMutationVariables>;

export const GetStagingFilasDocument = gql`
  query GetStagingFilas($archivoId: ID!) {
    getStagingFilas(archivoId: $archivoId) {
      id
      filaNumero
      cumCode
      precioUnitario
      precioUnidad
      precioPresentacion
      porcentajeIva
      descripcionRaw
      estadoHomologacion
      sugerenciasCum
      datosRaw
    }
  }
` as TypedDocumentNode<GetStagingFilasQuery, GetStagingFilasQueryVariables>;

export const SugerenciasCUMDocument = gql`
  query SugerenciasCUM($texto: String!) {
    sugerenciasCum(texto: $texto) {
      idCum
      nombre
      score
      principioActivo
      laboratorio
    }
  }
` as TypedDocumentNode<SugerenciasCUMQuery, SugerenciasCUMQueryVariables>;

