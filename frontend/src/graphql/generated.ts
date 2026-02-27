import { gql, type TypedDocumentNode } from "@apollo/client";

export type SearchMedicamentosQueryVariables = {
  texto: string;
  empresa?: string | null;
  soloActivos?: boolean | null;
  formaFarmaceutica?: string | null;
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
    activo: boolean;
    estadoCum?: string | null;
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

export const SearchMedicamentosDocument = gql`
  query SearchMedicamentos($texto: String!, $empresa: String, $soloActivos: Boolean, $formaFarmaceutica: String) {
    buscarMedicamentos(texto: $texto, empresa: $empresa, soloActivos: $soloActivos, formaFarmaceutica: $formaFarmaceutica) {
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
      activo
      estadoCum
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

export type ConfirmarMapeoProveedorMutationVariables = {
  archivoId: string;
  cumCode?: string | null;
  precioUnitario?: string | null;
  precioUnidad?: string | null;
  precioPresentacion?: string | null;
  porcentajeIva?: string | null;
  descripcion?: string | null;
  vigentDesde?: string | null;
  vigenteHasta?: string | null;
};

export type ConfirmarMapeoProveedorMutation = {
  confirmarMapeoProveedor: {
    id: string;
    filename: string;
    status: string;
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
    fechaVigenciaIndefinida: boolean;
    confianzaScore?: number | null;
  }>;
};

export type AprobarStagingFilaMutationVariables = {
  stagingId: string;
  idCum: string;
};

export type AprobarStagingFilaMutation = {
  aprobarStagingFila: {
    id: string;
    estadoHomologacion: string;
    cumCode?: string | null;
  };
};

export type PublicarPreciosProveedorMutationVariables = {
  archivoId: string;
};

export type PublicarPreciosProveedorMutation = {
  publicarPreciosProveedor: {
    filasPublicadas: number;
    archivoId: string;
    status: string;
  };
};

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
  mutation ConfirmarMapeoProveedor(
    $archivoId: ID!
    $cumCode: String
    $precioUnitario: String
    $precioUnidad: String
    $precioPresentacion: String
    $porcentajeIva: String
    $descripcion: String
    $vigenteDesde: String
    $vigenteHasta: String
  ) {
    confirmarMapeoProveedor(
      archivoId: $archivoId
      mapeo: {
        cumCode: $cumCode
        precioUnitario: $precioUnitario
        precioUnidad: $precioUnidad
        precioPresentacion: $precioPresentacion
        porcentajeIva: $porcentajeIva
        descripcion: $descripcion
        vigenteDesde: $vigenteDesde
        vigenteHasta: $vigenteHasta
      }
    ) {
      id
      filename
      status
    }
  }
` as TypedDocumentNode<ConfirmarMapeoProveedorMutation, ConfirmarMapeoProveedorMutationVariables>;

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
      fechaVigenciaIndefinida
      confianzaScore
    }
  }
` as TypedDocumentNode<GetStagingFilasQuery, GetStagingFilasQueryVariables>;

export const AprobarStagingFilaDocument = gql`
  mutation AprobarStagingFila($stagingId: ID!, $idCum: String!) {
    aprobarStagingFila(stagingId: $stagingId, idCum: $idCum) {
      id
      estadoHomologacion
      cumCode
    }
  }
` as TypedDocumentNode<AprobarStagingFilaMutation, AprobarStagingFilaMutationVariables>;

export const PublicarPreciosProveedorDocument = gql`
  mutation PublicarPreciosProveedor($archivoId: ID!) {
    publicarPreciosProveedor(archivoId: $archivoId) {
      filasPublicadas
      archivoId
      status
    }
  }
` as TypedDocumentNode<PublicarPreciosProveedorMutation, PublicarPreciosProveedorMutationVariables>;

