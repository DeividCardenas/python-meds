import { useState, type FormEvent } from "react";
import { useLazyQuery } from "@apollo/client";

import {
  SearchMedicamentosDocument,
  type SearchMedicamentosQuery,
  type SearchMedicamentosQueryVariables,
} from "../graphql/generated";

export function BuscadorMedicamentos() {
  const [texto, setTexto] = useState("");
  const [empresa, setEmpresa] = useState("");
  const [buscar, { data, loading, error }] = useLazyQuery<
    SearchMedicamentosQuery,
    SearchMedicamentosQueryVariables
  >(SearchMedicamentosDocument);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!texto.trim()) {
      return;
    }
    buscar({
      variables: {
        texto: texto.trim(),
        empresa: empresa.trim() || null,
      },
    });
  };

  return (
    <section>
      <h2>BuscadorMedicamentos</h2>
      <form onSubmit={onSubmit}>
        <input
          value={texto}
          onChange={(event) => setTexto(event.target.value)}
          placeholder="Texto de búsqueda"
        />
        <input
          value={empresa}
          onChange={(event) => setEmpresa(event.target.value)}
          placeholder="Empresa (opcional)"
        />
        <button type="submit" disabled={loading}>
          Buscar
        </button>
      </form>
      {error ? <p>Error: {error.message}</p> : null}
      <ul>
        {(data?.buscarMedicamentos ?? []).map((item) => (
          <li key={item.id}>
            {item.nombreLimpio} — {item.distancia.toFixed(4)}
          </li>
        ))}
      </ul>
    </section>
  );
}
