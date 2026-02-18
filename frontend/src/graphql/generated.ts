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
