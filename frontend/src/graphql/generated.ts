import type { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core';
export type Maybe<T> = T | null;
export type InputMaybe<T> = Maybe<T>;
export type Exact<T extends { [key: string]: unknown }> = { [K in keyof T]: T[K] };
export type MakeOptional<T, K extends keyof T> = Omit<T, K> & { [SubKey in K]?: Maybe<T[SubKey]> };
export type MakeMaybe<T, K extends keyof T> = Omit<T, K> & { [SubKey in K]: Maybe<T[SubKey]> };
export type MakeEmpty<T extends { [key: string]: unknown }, K extends keyof T> = { [_ in K]?: never };
export type Incremental<T> = T | { [P in keyof T]?: P extends ' $fragmentName' | '__typename' ? T[P] : never };
/** All built-in and custom scalars, mapped to their actual values */
export type Scalars = {
  ID: { input: string; output: string; }
  String: { input: string; output: string; }
  Boolean: { input: boolean; output: boolean; }
  Int: { input: number; output: number; }
  Float: { input: number; output: number; }
  Upload: { input: any; output: any; }
};

export type CargaArchivoNode = {
  __typename?: 'CargaArchivoNode';
  filename: Scalars['String']['output'];
  id: Scalars['ID']['output'];
  status: Scalars['String']['output'];
};

export type CotizacionFilaNode = {
  __typename?: 'CotizacionFilaNode';
  concentracion?: Maybe<Scalars['String']['output']>;
  cumId?: Maybe<Scalars['String']['output']>;
  esRegulado: Scalars['Boolean']['output'];
  formaFarmaceutica?: Maybe<Scalars['String']['output']>;
  innScore?: Maybe<Scalars['Float']['output']>;
  matchConfidence: Scalars['Float']['output'];
  matchStage: Scalars['String']['output'];
  mejorPrecio?: Maybe<PrecioItemNode>;
  nombreInput: Scalars['String']['output'];
  nombreMatcheado?: Maybe<Scalars['String']['output']>;
  parseWarnings: Array<Scalars['String']['output']>;
  precioMaximoRegulado?: Maybe<Scalars['Float']['output']>;
  preciosCount: Scalars['Int']['output'];
  rejectReason?: Maybe<Scalars['String']['output']>;
  todosPrecios: Array<PrecioItemNode>;
};

export type CotizacionLoteNode = {
  __typename?: 'CotizacionLoteNode';
  fechaCompletado?: Maybe<Scalars['String']['output']>;
  fechaCreacion: Scalars['String']['output'];
  filas?: Maybe<Array<CotizacionFilaNode>>;
  filename: Scalars['String']['output'];
  hospitalId: Scalars['String']['output'];
  id: Scalars['ID']['output'];
  resumen?: Maybe<ResumenCotizacionNode>;
  status: Scalars['String']['output'];
};

export type MapeoColumnasInput = {
  cumCode?: InputMaybe<Scalars['String']['input']>;
  descripcion?: InputMaybe<Scalars['String']['input']>;
  porcentajeIva?: InputMaybe<Scalars['String']['input']>;
  precioPresentacion?: InputMaybe<Scalars['String']['input']>;
  precioUnidad?: InputMaybe<Scalars['String']['input']>;
  precioUnitario?: InputMaybe<Scalars['String']['input']>;
  vigenteDesde?: InputMaybe<Scalars['String']['input']>;
  vigenteHasta?: InputMaybe<Scalars['String']['input']>;
};

export type MedicamentoNode = {
  __typename?: 'MedicamentoNode';
  activo: Scalars['Boolean']['output'];
  distancia: Scalars['Float']['output'];
  esRegulado: Scalars['Boolean']['output'];
  estadoCum?: Maybe<Scalars['String']['output']>;
  formaFarmaceutica?: Maybe<Scalars['String']['output']>;
  id: Scalars['ID']['output'];
  idCum?: Maybe<Scalars['String']['output']>;
  laboratorio?: Maybe<Scalars['String']['output']>;
  mejorPrecioProveedor?: Maybe<Scalars['Float']['output']>;
  mejorProveedorNombre?: Maybe<Scalars['String']['output']>;
  nombreLimpio: Scalars['String']['output'];
  precioEmpaque?: Maybe<Scalars['Float']['output']>;
  precioMaximoRegulado?: Maybe<Scalars['Float']['output']>;
  precioUnitario?: Maybe<Scalars['Float']['output']>;
  principioActivo?: Maybe<Scalars['String']['output']>;
  registroInvima?: Maybe<Scalars['String']['output']>;
};

export type Mutation = {
  __typename?: 'Mutation';
  aprobarStagingFila: StagingFilaNode;
  cargarMaestroInvima: CargaArchivoNode;
  confirmarMapeoProveedor: ProveedorArchivoNode;
  iniciarCotizacion: CotizacionLoteNode;
  publicarPreciosProveedor: PublicarResultadoNode;
  sincronizarCatalogos: SincronizacionCatalogosNode;
  subirArchivo: CargaArchivoNode;
  subirArchivoProveedor: ProveedorArchivoNode;
};


export type MutationAprobarStagingFilaArgs = {
  idCum: Scalars['String']['input'];
  stagingId: Scalars['ID']['input'];
};


export type MutationCargarMaestroInvimaArgs = {
  file: Scalars['Upload']['input'];
};


export type MutationConfirmarMapeoProveedorArgs = {
  archivoId: Scalars['ID']['input'];
  mapeo: MapeoColumnasInput;
};


export type MutationIniciarCotizacionArgs = {
  file: Scalars['Upload']['input'];
  hospitalId?: Scalars['String']['input'];
};


export type MutationPublicarPreciosProveedorArgs = {
  archivoId: Scalars['ID']['input'];
};


export type MutationSincronizarCatalogosArgs = {
  incluirSismed?: Scalars['Boolean']['input'];
};


export type MutationSubirArchivoArgs = {
  file: Scalars['Upload']['input'];
};


export type MutationSubirArchivoProveedorArgs = {
  file: Scalars['Upload']['input'];
};

export type PrecioItemNode = {
  __typename?: 'PrecioItemNode';
  fechaPublicacion?: Maybe<Scalars['String']['output']>;
  porcentajeIva?: Maybe<Scalars['Float']['output']>;
  precioPresentacion?: Maybe<Scalars['Float']['output']>;
  precioUnidad?: Maybe<Scalars['Float']['output']>;
  precioUnitario?: Maybe<Scalars['Float']['output']>;
  proveedorCodigo?: Maybe<Scalars['String']['output']>;
  proveedorId?: Maybe<Scalars['String']['output']>;
  proveedorNombre: Scalars['String']['output'];
  vigenteDesde?: Maybe<Scalars['String']['output']>;
  vigenteHasta?: Maybe<Scalars['String']['output']>;
};

export type ProveedorArchivoNode = {
  __typename?: 'ProveedorArchivoNode';
  columnasDetectadas?: Maybe<Array<Scalars['String']['output']>>;
  filename: Scalars['String']['output'];
  id: Scalars['ID']['output'];
  mapeoSugerido?: Maybe<Scalars['String']['output']>;
  status: Scalars['String']['output'];
};

export type PublicarResultadoNode = {
  __typename?: 'PublicarResultadoNode';
  archivoId: Scalars['ID']['output'];
  filasPublicadas: Scalars['Int']['output'];
  status: Scalars['String']['output'];
};

export type Query = {
  __typename?: 'Query';
  buscarMedicamentos: Array<MedicamentoNode>;
  comparativaPrecios: Array<MedicamentoNode>;
  getCotizacion?: Maybe<CotizacionLoteNode>;
  getStagingFilas: Array<StagingFilaNode>;
  getStatusCarga?: Maybe<CargaArchivoNode>;
  sugerenciasCum: Array<SugerenciaCumNode>;
};


export type QueryBuscarMedicamentosArgs = {
  empresa?: InputMaybe<Scalars['String']['input']>;
  formaFarmaceutica?: InputMaybe<Scalars['String']['input']>;
  soloActivos?: Scalars['Boolean']['input'];
  texto: Scalars['String']['input'];
};


export type QueryComparativaPreciosArgs = {
  principioActivo: Scalars['String']['input'];
};


export type QueryGetCotizacionArgs = {
  id: Scalars['ID']['input'];
};


export type QueryGetStagingFilasArgs = {
  archivoId: Scalars['ID']['input'];
};


export type QueryGetStatusCargaArgs = {
  id: Scalars['ID']['input'];
};


export type QuerySugerenciasCumArgs = {
  texto: Scalars['String']['input'];
};

export type ResumenCotizacionNode = {
  __typename?: 'ResumenCotizacionNode';
  conMatch: Scalars['Int']['output'];
  conPrecio: Scalars['Int']['output'];
  sinMatch: Scalars['Int']['output'];
  sinPrecio: Scalars['Int']['output'];
  tasaMatch: Scalars['Float']['output'];
  tasaPrecio: Scalars['Float']['output'];
  total: Scalars['Int']['output'];
};

export type SincronizacionCatalogosNode = {
  __typename?: 'SincronizacionCatalogosNode';
  cum: SincronizacionTareaNode;
  sismed: SincronizacionTareaNode;
};

export type SincronizacionTareaNode = {
  __typename?: 'SincronizacionTareaNode';
  mensaje: Scalars['String']['output'];
  tarea: Scalars['String']['output'];
  taskId: Scalars['String']['output'];
};

export type StagingFilaNode = {
  __typename?: 'StagingFilaNode';
  confianzaScore?: Maybe<Scalars['Float']['output']>;
  cumCode?: Maybe<Scalars['String']['output']>;
  datosRaw: Scalars['String']['output'];
  descripcionRaw?: Maybe<Scalars['String']['output']>;
  estadoHomologacion: Scalars['String']['output'];
  fechaVigenciaIndefinida: Scalars['Boolean']['output'];
  filaNumero: Scalars['Int']['output'];
  id: Scalars['ID']['output'];
  porcentajeIva?: Maybe<Scalars['Float']['output']>;
  precioPresentacion?: Maybe<Scalars['Float']['output']>;
  precioUnidad?: Maybe<Scalars['Float']['output']>;
  precioUnitario?: Maybe<Scalars['Float']['output']>;
  sugerenciasCum?: Maybe<Scalars['String']['output']>;
};

export type SugerenciaCumNode = {
  __typename?: 'SugerenciaCUMNode';
  idCum: Scalars['String']['output'];
  laboratorio?: Maybe<Scalars['String']['output']>;
  nombre: Scalars['String']['output'];
  principioActivo?: Maybe<Scalars['String']['output']>;
  score: Scalars['Float']['output'];
};

export type SearchMedicamentosQueryVariables = Exact<{
  texto: Scalars['String']['input'];
  empresa?: InputMaybe<Scalars['String']['input']>;
  soloActivos?: InputMaybe<Scalars['Boolean']['input']>;
  formaFarmaceutica?: InputMaybe<Scalars['String']['input']>;
}>;


export type SearchMedicamentosQuery = { __typename?: 'Query', buscarMedicamentos: Array<{ __typename?: 'MedicamentoNode', id: string, nombreLimpio: string, distancia: number, idCum?: string | null, laboratorio?: string | null, formaFarmaceutica?: string | null, registroInvima?: string | null, principioActivo?: string | null, precioUnitario?: number | null, precioEmpaque?: number | null, esRegulado: boolean, precioMaximoRegulado?: number | null, activo: boolean, estadoCum?: string | null }> };

export type ComparativaPreciosQueryVariables = Exact<{
  principioActivo: Scalars['String']['input'];
}>;


export type ComparativaPreciosQuery = { __typename?: 'Query', comparativaPrecios: Array<{ __typename?: 'MedicamentoNode', id: string, nombreLimpio: string, idCum?: string | null, laboratorio?: string | null, formaFarmaceutica?: string | null, principioActivo?: string | null, precioUnitario?: number | null, precioEmpaque?: number | null, esRegulado: boolean, precioMaximoRegulado?: number | null, mejorPrecioProveedor?: number | null, mejorProveedorNombre?: string | null }> };

export type PrecioItemFragment = { __typename?: 'PrecioItemNode', proveedorNombre: string, precioUnitario?: number | null, precioUnidad?: number | null, precioPresentacion?: number | null, porcentajeIva?: number | null, vigenteDesde?: string | null, vigenteHasta?: string | null, fechaPublicacion?: string | null };

export type ResumenCotizacionFragment = { __typename?: 'ResumenCotizacionNode', total: number, conMatch: number, sinMatch: number, conPrecio: number, sinPrecio: number, tasaMatch: number, tasaPrecio: number };

export type CotizacionFilaFragment = { __typename?: 'CotizacionFilaNode', nombreInput: string, matchStage: string, matchConfidence: number, cumId?: string | null, nombreMatcheado?: string | null, formaFarmaceutica?: string | null, concentracion?: string | null, rejectReason?: string | null, innScore?: number | null, preciosCount: number, esRegulado: boolean, precioMaximoRegulado?: number | null, mejorPrecio?: { __typename?: 'PrecioItemNode', proveedorNombre: string, precioUnitario?: number | null, precioUnidad?: number | null, precioPresentacion?: number | null, porcentajeIva?: number | null, vigenteDesde?: string | null, vigenteHasta?: string | null, fechaPublicacion?: string | null } | null, todosPrecios: Array<{ __typename?: 'PrecioItemNode', proveedorNombre: string, precioUnitario?: number | null, precioUnidad?: number | null, precioPresentacion?: number | null, porcentajeIva?: number | null, vigenteDesde?: string | null, vigenteHasta?: string | null, fechaPublicacion?: string | null }> };

export type IniciarCotizacionMutationVariables = Exact<{
  file: Scalars['Upload']['input'];
  hospitalId?: InputMaybe<Scalars['String']['input']>;
}>;


export type IniciarCotizacionMutation = { __typename?: 'Mutation', iniciarCotizacion: { __typename?: 'CotizacionLoteNode', id: string, status: string, filename: string, hospitalId: string, fechaCreacion: string } };

export type GetCotizacionQueryVariables = Exact<{
  id: Scalars['ID']['input'];
}>;


export type GetCotizacionQuery = { __typename?: 'Query', getCotizacion?: { __typename?: 'CotizacionLoteNode', id: string, status: string, filename: string, hospitalId: string, fechaCreacion: string, fechaCompletado?: string | null, resumen?: { __typename?: 'ResumenCotizacionNode', total: number, conMatch: number, sinMatch: number, conPrecio: number, sinPrecio: number, tasaMatch: number, tasaPrecio: number } | null, filas?: Array<{ __typename?: 'CotizacionFilaNode', nombreInput: string, matchStage: string, matchConfidence: number, cumId?: string | null, nombreMatcheado?: string | null, formaFarmaceutica?: string | null, concentracion?: string | null, rejectReason?: string | null, innScore?: number | null, preciosCount: number, esRegulado: boolean, precioMaximoRegulado?: number | null, mejorPrecio?: { __typename?: 'PrecioItemNode', proveedorNombre: string, precioUnitario?: number | null, precioUnidad?: number | null, precioPresentacion?: number | null, porcentajeIva?: number | null, vigenteDesde?: string | null, vigenteHasta?: string | null, fechaPublicacion?: string | null } | null, todosPrecios: Array<{ __typename?: 'PrecioItemNode', proveedorNombre: string, precioUnitario?: number | null, precioUnidad?: number | null, precioPresentacion?: number | null, porcentajeIva?: number | null, vigenteDesde?: string | null, vigenteHasta?: string | null, fechaPublicacion?: string | null }> }> | null } | null };

export type SubirArchivoProveedorMutationVariables = Exact<{
  file: Scalars['Upload']['input'];
}>;


export type SubirArchivoProveedorMutation = { __typename?: 'Mutation', subirArchivoProveedor: { __typename?: 'ProveedorArchivoNode', id: string, filename: string, status: string, columnasDetectadas?: Array<string> | null, mapeoSugerido?: string | null } };

export type ConfirmarMapeoProveedorMutationVariables = Exact<{
  archivoId: Scalars['ID']['input'];
  mapeo: MapeoColumnasInput;
}>;


export type ConfirmarMapeoProveedorMutation = { __typename?: 'Mutation', confirmarMapeoProveedor: { __typename?: 'ProveedorArchivoNode', id: string, filename: string, status: string, columnasDetectadas?: Array<string> | null, mapeoSugerido?: string | null } };

export type AprobarStagingFilaMutationVariables = Exact<{
  stagingId: Scalars['ID']['input'];
  idCum: Scalars['String']['input'];
}>;


export type AprobarStagingFilaMutation = { __typename?: 'Mutation', aprobarStagingFila: { __typename?: 'StagingFilaNode', id: string, filaNumero: number, cumCode?: string | null, precioUnitario?: number | null, precioUnidad?: number | null, precioPresentacion?: number | null, porcentajeIva?: number | null, descripcionRaw?: string | null, estadoHomologacion: string, sugerenciasCum?: string | null, datosRaw: string, fechaVigenciaIndefinida: boolean, confianzaScore?: number | null } };

export type PublicarPreciosProveedorMutationVariables = Exact<{
  archivoId: Scalars['ID']['input'];
}>;


export type PublicarPreciosProveedorMutation = { __typename?: 'Mutation', publicarPreciosProveedor: { __typename?: 'PublicarResultadoNode', filasPublicadas: number, archivoId: string, status: string } };

export type GetStagingFilasQueryVariables = Exact<{
  archivoId: Scalars['ID']['input'];
}>;


export type GetStagingFilasQuery = { __typename?: 'Query', getStagingFilas: Array<{ __typename?: 'StagingFilaNode', id: string, filaNumero: number, cumCode?: string | null, precioUnitario?: number | null, precioUnidad?: number | null, precioPresentacion?: number | null, porcentajeIva?: number | null, descripcionRaw?: string | null, estadoHomologacion: string, sugerenciasCum?: string | null, datosRaw: string, fechaVigenciaIndefinida: boolean, confianzaScore?: number | null }> };

export const ResumenCotizacionFragmentDoc = {"kind":"Document","definitions":[{"kind":"FragmentDefinition","name":{"kind":"Name","value":"ResumenCotizacion"},"typeCondition":{"kind":"NamedType","name":{"kind":"Name","value":"ResumenCotizacionNode"}},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"total"}},{"kind":"Field","name":{"kind":"Name","value":"conMatch"}},{"kind":"Field","name":{"kind":"Name","value":"sinMatch"}},{"kind":"Field","name":{"kind":"Name","value":"conPrecio"}},{"kind":"Field","name":{"kind":"Name","value":"sinPrecio"}},{"kind":"Field","name":{"kind":"Name","value":"tasaMatch"}},{"kind":"Field","name":{"kind":"Name","value":"tasaPrecio"}}]}}]} as unknown as DocumentNode<ResumenCotizacionFragment, unknown>;
export const PrecioItemFragmentDoc = {"kind":"Document","definitions":[{"kind":"FragmentDefinition","name":{"kind":"Name","value":"PrecioItem"},"typeCondition":{"kind":"NamedType","name":{"kind":"Name","value":"PrecioItemNode"}},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"proveedorNombre"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnitario"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnidad"}},{"kind":"Field","name":{"kind":"Name","value":"precioPresentacion"}},{"kind":"Field","name":{"kind":"Name","value":"porcentajeIva"}},{"kind":"Field","name":{"kind":"Name","value":"vigenteDesde"}},{"kind":"Field","name":{"kind":"Name","value":"vigenteHasta"}},{"kind":"Field","name":{"kind":"Name","value":"fechaPublicacion"}}]}}]} as unknown as DocumentNode<PrecioItemFragment, unknown>;
export const CotizacionFilaFragmentDoc = {"kind":"Document","definitions":[{"kind":"FragmentDefinition","name":{"kind":"Name","value":"CotizacionFila"},"typeCondition":{"kind":"NamedType","name":{"kind":"Name","value":"CotizacionFilaNode"}},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"nombreInput"}},{"kind":"Field","name":{"kind":"Name","value":"matchStage"}},{"kind":"Field","name":{"kind":"Name","value":"matchConfidence"}},{"kind":"Field","name":{"kind":"Name","value":"cumId"}},{"kind":"Field","name":{"kind":"Name","value":"nombreMatcheado"}},{"kind":"Field","name":{"kind":"Name","value":"formaFarmaceutica"}},{"kind":"Field","name":{"kind":"Name","value":"concentracion"}},{"kind":"Field","name":{"kind":"Name","value":"rejectReason"}},{"kind":"Field","name":{"kind":"Name","value":"innScore"}},{"kind":"Field","name":{"kind":"Name","value":"preciosCount"}},{"kind":"Field","name":{"kind":"Name","value":"esRegulado"}},{"kind":"Field","name":{"kind":"Name","value":"precioMaximoRegulado"}},{"kind":"Field","name":{"kind":"Name","value":"mejorPrecio"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"FragmentSpread","name":{"kind":"Name","value":"PrecioItem"}}]}},{"kind":"Field","name":{"kind":"Name","value":"todosPrecios"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"FragmentSpread","name":{"kind":"Name","value":"PrecioItem"}}]}}]}},{"kind":"FragmentDefinition","name":{"kind":"Name","value":"PrecioItem"},"typeCondition":{"kind":"NamedType","name":{"kind":"Name","value":"PrecioItemNode"}},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"proveedorNombre"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnitario"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnidad"}},{"kind":"Field","name":{"kind":"Name","value":"precioPresentacion"}},{"kind":"Field","name":{"kind":"Name","value":"porcentajeIva"}},{"kind":"Field","name":{"kind":"Name","value":"vigenteDesde"}},{"kind":"Field","name":{"kind":"Name","value":"vigenteHasta"}},{"kind":"Field","name":{"kind":"Name","value":"fechaPublicacion"}}]}}]} as unknown as DocumentNode<CotizacionFilaFragment, unknown>;
export const SearchMedicamentosDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"SearchMedicamentos"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"texto"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"empresa"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"soloActivos"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"Boolean"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"formaFarmaceutica"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"buscarMedicamentos"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"texto"},"value":{"kind":"Variable","name":{"kind":"Name","value":"texto"}}},{"kind":"Argument","name":{"kind":"Name","value":"empresa"},"value":{"kind":"Variable","name":{"kind":"Name","value":"empresa"}}},{"kind":"Argument","name":{"kind":"Name","value":"soloActivos"},"value":{"kind":"Variable","name":{"kind":"Name","value":"soloActivos"}}},{"kind":"Argument","name":{"kind":"Name","value":"formaFarmaceutica"},"value":{"kind":"Variable","name":{"kind":"Name","value":"formaFarmaceutica"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"nombreLimpio"}},{"kind":"Field","name":{"kind":"Name","value":"distancia"}},{"kind":"Field","name":{"kind":"Name","value":"idCum"}},{"kind":"Field","name":{"kind":"Name","value":"laboratorio"}},{"kind":"Field","name":{"kind":"Name","value":"formaFarmaceutica"}},{"kind":"Field","name":{"kind":"Name","value":"registroInvima"}},{"kind":"Field","name":{"kind":"Name","value":"principioActivo"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnitario"}},{"kind":"Field","name":{"kind":"Name","value":"precioEmpaque"}},{"kind":"Field","name":{"kind":"Name","value":"esRegulado"}},{"kind":"Field","name":{"kind":"Name","value":"precioMaximoRegulado"}},{"kind":"Field","name":{"kind":"Name","value":"activo"}},{"kind":"Field","name":{"kind":"Name","value":"estadoCum"}}]}}]}}]} as unknown as DocumentNode<SearchMedicamentosQuery, SearchMedicamentosQueryVariables>;
export const ComparativaPreciosDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"ComparativaPrecios"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"principioActivo"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"comparativaPrecios"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"principioActivo"},"value":{"kind":"Variable","name":{"kind":"Name","value":"principioActivo"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"nombreLimpio"}},{"kind":"Field","name":{"kind":"Name","value":"idCum"}},{"kind":"Field","name":{"kind":"Name","value":"laboratorio"}},{"kind":"Field","name":{"kind":"Name","value":"formaFarmaceutica"}},{"kind":"Field","name":{"kind":"Name","value":"principioActivo"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnitario"}},{"kind":"Field","name":{"kind":"Name","value":"precioEmpaque"}},{"kind":"Field","name":{"kind":"Name","value":"esRegulado"}},{"kind":"Field","name":{"kind":"Name","value":"precioMaximoRegulado"}},{"kind":"Field","name":{"kind":"Name","value":"mejorPrecioProveedor"}},{"kind":"Field","name":{"kind":"Name","value":"mejorProveedorNombre"}}]}}]}}]} as unknown as DocumentNode<ComparativaPreciosQuery, ComparativaPreciosQueryVariables>;
export const IniciarCotizacionDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"IniciarCotizacion"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"file"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"Upload"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"hospitalId"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"iniciarCotizacion"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"file"},"value":{"kind":"Variable","name":{"kind":"Name","value":"file"}}},{"kind":"Argument","name":{"kind":"Name","value":"hospitalId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"hospitalId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"filename"}},{"kind":"Field","name":{"kind":"Name","value":"hospitalId"}},{"kind":"Field","name":{"kind":"Name","value":"fechaCreacion"}}]}}]}}]} as unknown as DocumentNode<IniciarCotizacionMutation, IniciarCotizacionMutationVariables>;
export const GetCotizacionDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"GetCotizacion"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"id"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"getCotizacion"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"id"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"filename"}},{"kind":"Field","name":{"kind":"Name","value":"hospitalId"}},{"kind":"Field","name":{"kind":"Name","value":"fechaCreacion"}},{"kind":"Field","name":{"kind":"Name","value":"fechaCompletado"}},{"kind":"Field","name":{"kind":"Name","value":"resumen"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"FragmentSpread","name":{"kind":"Name","value":"ResumenCotizacion"}}]}},{"kind":"Field","name":{"kind":"Name","value":"filas"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"FragmentSpread","name":{"kind":"Name","value":"CotizacionFila"}}]}}]}}]}},{"kind":"FragmentDefinition","name":{"kind":"Name","value":"PrecioItem"},"typeCondition":{"kind":"NamedType","name":{"kind":"Name","value":"PrecioItemNode"}},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"proveedorNombre"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnitario"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnidad"}},{"kind":"Field","name":{"kind":"Name","value":"precioPresentacion"}},{"kind":"Field","name":{"kind":"Name","value":"porcentajeIva"}},{"kind":"Field","name":{"kind":"Name","value":"vigenteDesde"}},{"kind":"Field","name":{"kind":"Name","value":"vigenteHasta"}},{"kind":"Field","name":{"kind":"Name","value":"fechaPublicacion"}}]}},{"kind":"FragmentDefinition","name":{"kind":"Name","value":"ResumenCotizacion"},"typeCondition":{"kind":"NamedType","name":{"kind":"Name","value":"ResumenCotizacionNode"}},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"total"}},{"kind":"Field","name":{"kind":"Name","value":"conMatch"}},{"kind":"Field","name":{"kind":"Name","value":"sinMatch"}},{"kind":"Field","name":{"kind":"Name","value":"conPrecio"}},{"kind":"Field","name":{"kind":"Name","value":"sinPrecio"}},{"kind":"Field","name":{"kind":"Name","value":"tasaMatch"}},{"kind":"Field","name":{"kind":"Name","value":"tasaPrecio"}}]}},{"kind":"FragmentDefinition","name":{"kind":"Name","value":"CotizacionFila"},"typeCondition":{"kind":"NamedType","name":{"kind":"Name","value":"CotizacionFilaNode"}},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"nombreInput"}},{"kind":"Field","name":{"kind":"Name","value":"matchStage"}},{"kind":"Field","name":{"kind":"Name","value":"matchConfidence"}},{"kind":"Field","name":{"kind":"Name","value":"cumId"}},{"kind":"Field","name":{"kind":"Name","value":"nombreMatcheado"}},{"kind":"Field","name":{"kind":"Name","value":"formaFarmaceutica"}},{"kind":"Field","name":{"kind":"Name","value":"concentracion"}},{"kind":"Field","name":{"kind":"Name","value":"rejectReason"}},{"kind":"Field","name":{"kind":"Name","value":"innScore"}},{"kind":"Field","name":{"kind":"Name","value":"preciosCount"}},{"kind":"Field","name":{"kind":"Name","value":"esRegulado"}},{"kind":"Field","name":{"kind":"Name","value":"precioMaximoRegulado"}},{"kind":"Field","name":{"kind":"Name","value":"mejorPrecio"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"FragmentSpread","name":{"kind":"Name","value":"PrecioItem"}}]}},{"kind":"Field","name":{"kind":"Name","value":"todosPrecios"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"FragmentSpread","name":{"kind":"Name","value":"PrecioItem"}}]}}]}}]} as unknown as DocumentNode<GetCotizacionQuery, GetCotizacionQueryVariables>;
export const SubirArchivoProveedorDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"SubirArchivoProveedor"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"file"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"Upload"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"subirArchivoProveedor"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"file"},"value":{"kind":"Variable","name":{"kind":"Name","value":"file"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"filename"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"columnasDetectadas"}},{"kind":"Field","name":{"kind":"Name","value":"mapeoSugerido"}}]}}]}}]} as unknown as DocumentNode<SubirArchivoProveedorMutation, SubirArchivoProveedorMutationVariables>;
export const ConfirmarMapeoProveedorDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"ConfirmarMapeoProveedor"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"archivoId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"mapeo"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"MapeoColumnasInput"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"confirmarMapeoProveedor"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"archivoId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"archivoId"}}},{"kind":"Argument","name":{"kind":"Name","value":"mapeo"},"value":{"kind":"Variable","name":{"kind":"Name","value":"mapeo"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"filename"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"columnasDetectadas"}},{"kind":"Field","name":{"kind":"Name","value":"mapeoSugerido"}}]}}]}}]} as unknown as DocumentNode<ConfirmarMapeoProveedorMutation, ConfirmarMapeoProveedorMutationVariables>;
export const AprobarStagingFilaDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"AprobarStagingFila"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"stagingId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"idCum"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"aprobarStagingFila"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"stagingId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"stagingId"}}},{"kind":"Argument","name":{"kind":"Name","value":"idCum"},"value":{"kind":"Variable","name":{"kind":"Name","value":"idCum"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"filaNumero"}},{"kind":"Field","name":{"kind":"Name","value":"cumCode"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnitario"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnidad"}},{"kind":"Field","name":{"kind":"Name","value":"precioPresentacion"}},{"kind":"Field","name":{"kind":"Name","value":"porcentajeIva"}},{"kind":"Field","name":{"kind":"Name","value":"descripcionRaw"}},{"kind":"Field","name":{"kind":"Name","value":"estadoHomologacion"}},{"kind":"Field","name":{"kind":"Name","value":"sugerenciasCum"}},{"kind":"Field","name":{"kind":"Name","value":"datosRaw"}},{"kind":"Field","name":{"kind":"Name","value":"fechaVigenciaIndefinida"}},{"kind":"Field","name":{"kind":"Name","value":"confianzaScore"}}]}}]}}]} as unknown as DocumentNode<AprobarStagingFilaMutation, AprobarStagingFilaMutationVariables>;
export const PublicarPreciosProveedorDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"PublicarPreciosProveedor"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"archivoId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"publicarPreciosProveedor"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"archivoId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"archivoId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"filasPublicadas"}},{"kind":"Field","name":{"kind":"Name","value":"archivoId"}},{"kind":"Field","name":{"kind":"Name","value":"status"}}]}}]}}]} as unknown as DocumentNode<PublicarPreciosProveedorMutation, PublicarPreciosProveedorMutationVariables>;
export const GetStagingFilasDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"GetStagingFilas"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"archivoId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ID"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"getStagingFilas"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"archivoId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"archivoId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"filaNumero"}},{"kind":"Field","name":{"kind":"Name","value":"cumCode"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnitario"}},{"kind":"Field","name":{"kind":"Name","value":"precioUnidad"}},{"kind":"Field","name":{"kind":"Name","value":"precioPresentacion"}},{"kind":"Field","name":{"kind":"Name","value":"porcentajeIva"}},{"kind":"Field","name":{"kind":"Name","value":"descripcionRaw"}},{"kind":"Field","name":{"kind":"Name","value":"estadoHomologacion"}},{"kind":"Field","name":{"kind":"Name","value":"sugerenciasCum"}},{"kind":"Field","name":{"kind":"Name","value":"datosRaw"}},{"kind":"Field","name":{"kind":"Name","value":"fechaVigenciaIndefinida"}},{"kind":"Field","name":{"kind":"Name","value":"confianzaScore"}}]}}]}}]} as unknown as DocumentNode<GetStagingFilasQuery, GetStagingFilasQueryVariables>;