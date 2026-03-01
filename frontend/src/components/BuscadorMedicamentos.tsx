import { useLazyQuery } from "@apollo/client";
import { useEffect, useRef, useState, type FormEvent } from "react";

import {
    ComparativaPreciosDocument,
    SearchMedicamentosDocument,
    type ComparativaPreciosQuery,
    type ComparativaPreciosQueryVariables,
    type SearchMedicamentosQuery,
    type SearchMedicamentosQueryVariables,
} from "../graphql/generated";

const toTitleCase = (value: string | null | undefined) =>
  (value ?? "")
    .toLowerCase()
    .replace(/\b\p{L}/gu, (match) => match.toUpperCase())
    .trim();

const escapeCsvCell = (value: string) => `"${value.replace(/"/g, '""')}"`;
const formatPrice = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 2 }).format(value)
    : "";

export function BuscadorMedicamentos() {
  const [texto, setTexto] = useState("");
  const [empresa, setEmpresa] = useState("");
  const [soloActivos, setSoloActivos] = useState(true);
  const [formaFarmaceutica, setFormaFarmaceutica] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const lastQueryRef = useRef<{ texto: string; empresa: string | null; soloActivos: boolean; formaFarmaceutica: string | null } | null>(null);
  const [showCopiedToast, setShowCopiedToast] = useState(false);
  const [modalPrincipioActivo, setModalPrincipioActivo] = useState<string | null>(null);
  const [buscar, { data, loading }] = useLazyQuery<
    SearchMedicamentosQuery,
    SearchMedicamentosQueryVariables
  >(SearchMedicamentosDocument);
  const [buscarComparativa, { data: comparativaData, loading: loadingComparativa, error: comparativaError }] = useLazyQuery<
    ComparativaPreciosQuery,
    ComparativaPreciosQueryVariables
  >(ComparativaPreciosDocument);
  const resultados = data?.buscarMedicamentos ?? [];
  const comparativaResultados = comparativaData?.comparativaPrecios ?? [];

  // Re-execute the last query if the component remounts (e.g. StrictMode or navigation)
  // and we already had a pending/completed search.
  useEffect(() => {
    if (lastQueryRef.current) {
      setHasSearched(true);
      buscar({ variables: lastQueryRef.current });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const exportRows = resultados.map((item) => ({
    cum: item.idCum ?? "",
    nombre: toTitleCase(item.nombreLimpio),
    principioActivo: toTitleCase(item.principioActivo),
    formaFarmaceuticaExport: toTitleCase(item.formaFarmaceutica),
    laboratorio: toTitleCase(item.laboratorio),
    registroInvima: item.registroInvima ?? "",
    precioUnitario: formatPrice(item.precioUnitario),
    precioEmpaque: formatPrice(item.precioEmpaque),
    esRegulado: item.esRegulado ? "SI" : "NO",
    precioMaximoRegulado: formatPrice(item.precioMaximoRegulado),
    estadoCum: item.estadoCum ?? "",
    activo: item.activo ? "SI" : "NO",
  }));

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!texto.trim()) {
      return;
    }
    const variables = {
      texto: texto.trim(),
      empresa: empresa.trim() || null,
      soloActivos,
      formaFarmaceutica: formaFarmaceutica.trim() || null,
    };
    lastQueryRef.current = variables;
    setHasSearched(true);
    buscar({ variables });
  };

  const abrirComparativa = (principioActivo: string | null | undefined) => {
    const normalized = (principioActivo ?? "").trim();
    if (!normalized) {
      return;
    }
    setModalPrincipioActivo(normalized);
    buscarComparativa({ variables: { principioActivo: normalized } });
  };

  const onDescargarCsv = () => {
    if (exportRows.length === 0) {
      return;
    }
    const headers = [
      "CUM",
      "Nombre",
      "Principio Activo",
      "Forma Farmacéutica",
      "Laboratorio",
      "Registro INVIMA",
      "Precio Unitario",
      "Precio Empaque",
      "Es Regulado",
      "Precio Máximo",
    ];
    const body = exportRows.map((row) =>
      [
        row.cum,
        row.nombre,
        row.principioActivo,
        row.formaFarmaceuticaExport,
        row.laboratorio,
        row.registroInvima,
        row.precioUnitario,
        row.precioEmpaque,
        row.esRegulado,
        row.precioMaximoRegulado,
      ]
        .map(escapeCsvCell)
        .join(","),
    );
    const csv = [headers.map(escapeCsvCell).join(","), ...body].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "medicamentos.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const onCopiarDatos = async () => {
    if (exportRows.length === 0 || !navigator.clipboard) {
      return;
    }
    const headers = [
      "CUM",
      "Nombre",
      "Principio Activo",
      "Forma Farmacéutica",
      "Laboratorio",
      "Registro INVIMA",
      "Precio Unitario",
      "Precio Empaque",
      "Es Regulado",
      "Precio Máximo",
      "Estado CUM",
      "Activo",
    ].join("\t");
    const body = exportRows
      .map((row) =>
        [
          row.cum,
          row.nombre,
          row.principioActivo,
          row.formaFarmaceuticaExport,
          row.laboratorio,
          row.registroInvima,
          row.precioUnitario,
          row.precioEmpaque,
          row.esRegulado,
          row.precioMaximoRegulado,
          row.estadoCum,
          row.activo,
        ].join("\t"),
      )
      .join("\n");
    await navigator.clipboard.writeText(`${headers}\n${body}`);
    setShowCopiedToast(true);
    setTimeout(() => setShowCopiedToast(false), 2000);
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

      {/* Filtros avanzados */}
      <div className="mt-4 flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Filtros</span>
        {/* Forma farmacéutica */}
        <div className="flex items-center gap-2">
          <label htmlFor="filter-ff" className="whitespace-nowrap text-sm text-slate-600">Forma farmacéutica</label>
          <input
            id="filter-ff"
            value={formaFarmaceutica}
            onChange={(e) => setFormaFarmaceutica(e.target.value)}
            placeholder="ej. tableta, capsula..."
            className="h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
          />
        </div>
        {/* Solo activos */}
        <label className="flex cursor-pointer items-center gap-2 select-none">
          <div
            role="checkbox"
            aria-checked={soloActivos}
            tabIndex={0}
            onClick={() => setSoloActivos((v) => !v)}
            onKeyDown={(e) => e.key === " " && setSoloActivos((v) => !v)}
            className={`relative h-5 w-9 rounded-full transition-colors ${
              soloActivos ? "bg-teal-600" : "bg-slate-300"
            }`}
          >
            <span
              className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
                soloActivos ? "translate-x-4" : "translate-x-0.5"
              }`}
            />
          </div>
          <span className="text-sm text-slate-700">Solo CUM vigentes</span>
        </label>
      </div>

      <div className="mt-8">
        <div className="mb-4 flex flex-wrap items-center justify-end gap-2">
          <button
            type="button"
            onClick={onDescargarCsv}
            disabled={resultados.length === 0}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-2" aria-hidden="true">
              <path d="M12 3v12" />
              <path d="m7 10 5 5 5-5" />
              <path d="M4 21h16" />
            </svg>
            Descargar CSV
          </button>
          <button
            type="button"
            onClick={() => void onCopiarDatos()}
            disabled={resultados.length === 0}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-2" aria-hidden="true">
              <rect x="9" y="9" width="13" height="13" rx="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
            Copiar Datos
          </button>
        </div>

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

        {!loading && resultados.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {resultados.map((item) => {
              const nombreComercial = toTitleCase(item.nombreLimpio) || "Nombre comercial no disponible";
              const principioActivo = toTitleCase(item.principioActivo);
              const mostrarPrincipioActivo =
                principioActivo.length > 0 && !nombreComercial.toLowerCase().includes(principioActivo.toLowerCase());

              return (
                <article
                  key={item.id}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:scale-105 hover:shadow-lg"
                >
                  {item.esRegulado ? (
                    <p className="mb-3 inline-flex rounded-full bg-orange-100 px-2.5 py-1 text-xs font-semibold text-orange-700">
                      🔒 Regulado CNPMDM{item.precioMaximoRegulado ? ` · Máx ${formatPrice(item.precioMaximoRegulado)}` : ""}
                    </p>
                  ) : null}
                  {/* Badge de estado CUM */}
                  {item.estadoCum ? (
                    <span
                      className={`mb-2 mr-2 inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        item.activo
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {item.activo ? "✓" : "✗"} {item.estadoCum}
                    </span>
                  ) : null}                  <h3 className="text-lg font-bold text-slate-900">{nombreComercial}</h3>
                  {mostrarPrincipioActivo ? (
                    <p className="mt-2 text-sm text-slate-500">
                      Principio activo: <span className="font-medium text-slate-600">{principioActivo}</span>
                    </p>
                  ) : null}
                  {item.formaFarmaceutica ? (
                    <p className="mt-2 text-xs font-medium text-slate-500">{toTitleCase(item.formaFarmaceutica)}</p>
                  ) : null}
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
                  <button
                    type="button"
                    onClick={() => abrirComparativa(item.principioActivo)}
                    disabled={!item.principioActivo}
                    className="mt-4 rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Ver comparativa
                  </button>
                </article>
              );
            })}
          </div>
        ) : null}

        {!loading && hasSearched && resultados.length === 0 ? (
          <p className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
            No hay resultados para mostrar.
          </p>
        ) : null}

        {!hasSearched && !loading ? (
          <p className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
            Ingresa un término para buscar medicamentos.
          </p>
        ) : null}
      </div>

      {showCopiedToast ? (
        <div className="fixed bottom-4 right-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-lg">¡Copiado!</div>
      ) : null}
      {modalPrincipioActivo ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-4xl rounded-xl bg-white p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900">Comparativa de precios · {toTitleCase(modalPrincipioActivo)}</h3>
              <button
                type="button"
                onClick={() => setModalPrincipioActivo(null)}
                className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-600 hover:bg-slate-50"
              >
                Cerrar
              </button>
            </div>
            {comparativaError ? <p className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{comparativaError.message}</p> : null}
            <div className="max-h-[60vh] overflow-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2">Medicamento</th>
                    <th className="px-3 py-2">Laboratorio</th>
                    <th className="px-3 py-2">Precio Unitario</th>
                    <th className="px-3 py-2">Precio Empaque</th>
                    <th className="px-3 py-2">Regulado</th>
                    <th className="px-3 py-2">Precio Máximo</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingComparativa ? (
                    <tr>
                      <td colSpan={6} className="px-3 py-5 text-center text-slate-500">
                        Cargando comparativa...
                      </td>
                    </tr>
                  ) : comparativaResultados.length > 0 ? (
                    comparativaResultados.map((item) => (
                      <tr key={item.id} className="border-t border-slate-100">
                        <td className="px-3 py-2">{toTitleCase(item.nombreLimpio)}</td>
                        <td className="px-3 py-2">{toTitleCase(item.laboratorio) || "-"}</td>
                        <td className="px-3 py-2">{formatPrice(item.precioUnitario) || "-"}</td>
                        <td className="px-3 py-2">{formatPrice(item.precioEmpaque) || "-"}</td>
                        <td className="px-3 py-2">
                          {item.esRegulado ? (
                            <span className="inline-flex rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-orange-700">
                              🔒 Regulado
                            </span>
                          ) : (
                            <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-400">
                              No regulado
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2">{formatPrice(item.precioMaximoRegulado) || "-"}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="px-3 py-5 text-center text-slate-500">
                        No hay registros con precio para este principio activo.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
