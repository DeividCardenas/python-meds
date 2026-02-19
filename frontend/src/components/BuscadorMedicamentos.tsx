import { useState, type FormEvent } from "react";
import { useLazyQuery } from "@apollo/client";

import { SearchMedicamentosDocument, type SearchMedicamentosQuery, type SearchMedicamentosQueryVariables } from "../graphql/generated";

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
    <section className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-slate-900">Buscador de Medicamentos</h2>
        <p className="mt-2 text-sm text-slate-500">Consulta coincidencias por nombre y filtra por laboratorio.</p>
      </div>

      <form onSubmit={onSubmit} className="grid gap-4 lg:grid-cols-[2fr_1fr_auto]">
        <div className="relative">
          <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-slate-400">
            <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-2" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
          </span>
          <input
            value={texto}
            onChange={(event) => setTexto(event.target.value)}
            placeholder="Buscar medicamento..."
            className="h-12 w-full rounded-lg border border-slate-300 bg-white pl-12 pr-4 text-base shadow-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
          />
        </div>
        <input
          value={empresa}
          onChange={(event) => setEmpresa(event.target.value)}
          placeholder="Empresa (opcional)"
          className="h-12 rounded-lg border border-slate-300 bg-white px-4 text-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
        />
        <button
          type="submit"
          disabled={loading}
          className="h-12 rounded-lg bg-teal-600 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Buscando..." : "Buscar"}
        </button>
      </form>

      {error ? <p className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">Error: {error.message}</p> : null}

      <div className="mt-8">
        {loading ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <article key={index} className="animate-pulse rounded-2xl border border-slate-200 bg-slate-100 p-5">
                <div className="h-6 w-2/3 rounded bg-slate-200" />
                <div className="mt-3 h-4 w-3/4 rounded bg-slate-200" />
                <div className="mt-4 h-6 w-28 rounded-md bg-slate-200" />
                <div className="mt-6 h-4 w-1/2 rounded bg-slate-200" />
              </article>
            ))}
          </div>
        ) : null}

        {!loading && (data?.buscarMedicamentos ?? []).length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {(data?.buscarMedicamentos ?? []).map((item) => (
              <article
                key={item.id}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:scale-105 hover:shadow-lg"
              >
                <h3 className="text-lg font-bold text-slate-900">{item.nombreLimpio}</h3>
                <p className="mt-2 text-sm text-slate-500">
                  Principio activo: <span className="font-medium text-slate-600">{item.nombreLimpio}</span>
                </p>
                <p className="mt-4 inline-flex rounded-md border border-slate-300 bg-slate-100 px-2.5 py-1 font-mono text-xs text-slate-700">
                  {item.idCum ?? "ID CUM N/D"}
                </p>
                <p className="mt-5 flex items-center gap-2 text-sm text-slate-600">
                  <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-2" aria-hidden="true">
                    <path d="M3 21h18" />
                    <path d="M5 21V9l7-4 7 4v12" />
                    <path d="M9 21v-4h6v4" />
                  </svg>
                  {item.laboratorio ?? "Laboratorio no disponible"}
                </p>
              </article>
            ))}
          </div>
        ) : null}

        {!loading && (data?.buscarMedicamentos ?? []).length === 0 ? (
          <p className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
            No hay resultados para mostrar.
          </p>
        ) : null}
      </div>
    </section>
  );
}
