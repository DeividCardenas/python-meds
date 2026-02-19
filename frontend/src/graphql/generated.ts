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
    }
  }
` as TypedDocumentNode<SearchMedicamentosQuery, SearchMedicamentosQueryVariables>;

export const CargarInvimaDocument = gql`
  mutation CargarInvima($file: Upload!) {
    cargarMaestroInvima(file: $file) {
      id
      filename
      status
    }
  }
` as TypedDocumentNode<CargarInvimaMutation, CargarInvimaMutationVariables>;
