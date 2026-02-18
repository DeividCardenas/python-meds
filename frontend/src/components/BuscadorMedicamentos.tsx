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

  const getBadgeStatus = (distancia: number) => (distancia <= 0.2 ? "ACTIVO" : "INACTIVO/VENCIDO");

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-xl font-semibold">Buscador de Medicamentos</h2>
        <p className="mt-1 text-sm text-slate-600">Consulta coincidencias por nombre y filtra por laboratorio.</p>
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

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200">
        <div className="max-h-[420px] overflow-auto">
          <table className="min-w-full border-separate border-spacing-0 text-sm">
            <thead className="sticky top-0 z-10 bg-slate-100 text-left text-slate-600">
              <tr>
                <th className="border-b border-slate-200 px-4 py-3 font-semibold">Medicamento</th>
                <th className="border-b border-slate-200 px-4 py-3 font-semibold">Distancia</th>
                <th className="border-b border-slate-200 px-4 py-3 font-semibold">Estado INVIMA</th>
                <th className="border-b border-slate-200 px-4 py-3 text-right font-semibold">Precio</th>
              </tr>
            </thead>
            <tbody>
              {(data?.buscarMedicamentos ?? []).map((item) => {
                const status = getBadgeStatus(item.distancia);
                return (
                  <tr key={item.id} className="bg-white transition hover:bg-slate-50">
                    <td className="border-b border-slate-100 px-4 py-3 text-slate-800">{item.nombreLimpio}</td>
                    <td className="border-b border-slate-100 px-4 py-3 text-slate-600">{item.distancia.toFixed(4)}</td>
                    <td className="border-b border-slate-100 px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                          status === "ACTIVO" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
                        }`}
                      >
                        {status}
                      </span>
                    </td>
                    <td className="border-b border-slate-100 px-4 py-3 text-right font-mono text-slate-700">
                      {(item.distancia * 100000).toFixed(2)}
                    </td>
                  </tr>
                );
              })}
              {!loading && (data?.buscarMedicamentos ?? []).length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-sm text-slate-500">
                    No hay resultados para mostrar.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
