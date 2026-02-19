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
