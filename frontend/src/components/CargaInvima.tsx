import { useState, type FormEvent } from "react";
import { useMutation } from "@apollo/client";

import {
  CargarInvimaDocument,
  type CargarInvimaMutation,
  type CargarInvimaMutationVariables,
} from "../graphql/generated";

export function CargaInvima() {
  const [file, setFile] = useState<File | null>(null);
  const [cargarInvima, { data, loading, error }] = useMutation<
    CargarInvimaMutation,
    CargarInvimaMutationVariables
  >(CargarInvimaDocument);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      return;
    }
    await cargarInvima({ variables: { file } });
  };

  return (
    <section>
      <h2>CargaInvima</h2>
      <form onSubmit={onSubmit}>
        <input
          type="file"
          accept=".tsv,.csv,.txt"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={!file || loading}>
          Cargar archivo
        </button>
      </form>
      {error ? <p>Error: {error.message}</p> : null}
      {data ? (
        <p>
          Carga {data.cargarMaestroInvima.id}: {data.cargarMaestroInvima.status}
        </p>
      ) : null}
    </section>
  );
}
