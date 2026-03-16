import { gql, useLazyQuery } from "@apollo/client";
import { useEffect, useRef, useState, type FormEvent } from "react";

import {
    ComparativaPreciosDocument,
    type ComparativaPreciosQuery,
    type ComparativaPreciosQueryVariables,
} from "../graphql/generated";

type SearchMedicamentosQueryVariables = {
  texto: string;
  empresa?: string | null;
  soloActivos?: boolean;
  formaFarmaceutica?: string | null;
};

type SearchMedicamentoItem = {
  id: string;
  idCum?: string | null;
  nombreComercial?: string | null;
  marcaComercial?: string | null;
  nombreLimpio: string;
  dosisCantidad?: number | null;
  dosisUnidad?: string | null;
  formaFarmaceutica?: string | null;
  viaAdministracion?: string | null;
  presentacion?: string | null;
  tipoLiberacion?: string | null;
  volumenSolucion?: string | null;
  principioActivo?: string | null;
  laboratorio?: string | null;
  registroInvima?: string | null;
  estadoCum?: string | null;
  activo: boolean;
  esRegulado: boolean;
  precioUnitario?: number | null;
  precioEmpaque?: number | null;
  precioMaximoRegulado?: number | null;
};

type SearchMedicamentosQuery = {
  buscarMedicamentos: SearchMedicamentoItem[];
};

const SearchMedicamentosDocument = gql`
  query SearchMedicamentos(
    $texto: String!
    $empresa: String
    $soloActivos: Boolean
    $formaFarmaceutica: String
  ) {
    buscarMedicamentos(
      texto: $texto
      empresa: $empresa
      soloActivos: $soloActivos
      formaFarmaceutica: $formaFarmaceutica
    ) {
      id
      idCum
      nombreComercial
      marcaComercial
      nombreLimpio
      dosisCantidad
      dosisUnidad
      formaFarmaceutica
      viaAdministracion
      presentacion
      tipoLiberacion
      volumenSolucion
      principioActivo
      laboratorio
      registroInvima
      estadoCum
      activo
      esRegulado
      precioUnitario
      precioMaximoRegulado
    }
  }
`;

const sanitizeDisplayText = (value: string | null | undefined) =>
  (value ?? "")
    .replace(/[�]/g, "")
    .replace(/\?/g, "")
    .replace(/\s+/g, " ")
    .trim();

const toTitleCase = (value: string | null | undefined) =>
  sanitizeDisplayText(value)
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
  >(SearchMedicamentosDocument, {
    fetchPolicy: "network-only",
    nextFetchPolicy: "network-only",
    errorPolicy: "all",
  });
  const [buscarErrorState, setBuscarErrorState] = useState<string | null>(null);
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
    setBuscarErrorState(null);
    lastQueryRef.current = variables;
    setHasSearched(true);
    buscar({ variables })
      .then((result) => {
        if (result.error || (Array.isArray(result.errors) && result.errors.length > 0)) {
          setBuscarErrorState("No se pudo conectar con el backend. Verifica el servicio e intenta nuevamente.");
        }
      })
      .catch(() => {
        setBuscarErrorState("No se pudo conectar con el backend. Verifica el servicio e intenta nuevamente.");
      });
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
    <section className="overflow-x-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-8">
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
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="filter-ff" className="text-sm text-slate-600">Forma farmacéutica</label>
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
        {buscarErrorState ? (
          <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {buscarErrorState}
          </p>
        ) : null}

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

        {!loading && !buscarErrorState && resultados.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {resultados.map((item) => {
              return (
                <article
                  key={item.id}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:scale-105 hover:shadow-lg"
                >
                  {/* Header: Nombre + Dosis */}
                  <div className="mb-3 flex items-baseline justify-between gap-3">
                    <div className="flex-1">
                      <h3 className="break-words text-lg font-bold text-slate-900">
                        {toTitleCase(item.nombreComercial || item.nombreLimpio || "Nombre no disponible")}
                      </h3>
                      {item.dosisCantidad != null && (
                        <p className="mt-1 text-sm text-slate-500">
                          {item.dosisCantidad} {item.dosisUnidad}
                        </p>
                      )}
                    </div>

                    {/* Badge Regulado */}
                    {item.esRegulado ? (
                      <span className="inline-flex whitespace-nowrap rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-semibold text-orange-700">
                        🔒 Regulado{item.precioMaximoRegulado ? ` · Máx ${formatPrice(item.precioMaximoRegulado)}` : ""}
                      </span>
                    ) : null}
                  </div>

                  {/* Badges: Forma + Vía + Liberación */}
                  <div className="mb-3 flex flex-wrap gap-2">
                    {item.formaFarmaceutica && (
                      <span className="inline-flex rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700">
                        {toTitleCase(item.formaFarmaceutica)}
                      </span>
                    )}

                    {item.viaAdministracion && (
                      <span className="inline-flex rounded-full bg-green-100 px-2.5 py-1 text-xs font-medium text-green-700">
                        {toTitleCase(item.viaAdministracion)}
                      </span>
                    )}

                    {item.tipoLiberacion && (
                      <span className="inline-flex rounded-full bg-purple-100 px-2.5 py-1 text-xs font-medium text-purple-700">
                        {toTitleCase(item.tipoLiberacion)}
                      </span>
                    )}
                  </div>

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
                  ) : null}

                  {/* Principio Activo */}
                  {item.principioActivo && (
                    <p className="mb-2 break-words text-sm text-slate-600">
                      <span className="font-medium">{toTitleCase(item.principioActivo)}</span>
                    </p>
                  )}

                  {/* Laboratorio */}
                  {item.laboratorio && (
                    <p className="mt-2 flex items-start gap-2 break-words text-sm text-slate-600">
                      <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-2" aria-hidden="true">
                        <path d="M3 21h18" />
                        <path d="M5 21V9l7-4 7 4v12" />
                        <path d="M9 21v-4h6v4" />
                      </svg>
                      {toTitleCase(item.laboratorio)}
                    </p>
                  )}

                  {/* Presentación */}
                  {item.presentacion && (
                    <p className="mt-2 break-words text-xs text-slate-500">
                      Presentación: <span className="font-medium">{toTitleCase(item.presentacion)}</span>
                    </p>
                  )}

                  {/* Precio */}
                  {item.precioUnitario && (
                    <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                      <span className="text-xs text-slate-500">Precio unitario</span>
                      <span className="font-semibold text-slate-900">
                        {formatPrice(item.precioUnitario)}
                      </span>
                    </div>
                  )}

                  {/* Botón Comparativa */}
                  <button
                    type="button"
                    onClick={() => abrirComparativa(item.principioActivo)}
                    disabled={!item.principioActivo}
                    className="mt-4 w-full rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Ver comparativa de precios
                  </button>
                </article>
              );
            })}
          </div>
        ) : null}

        {!loading && !buscarErrorState && hasSearched && resultados.length === 0 ? (
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
                    <th className="px-3 py-2 text-right">P. Ref. SISMED</th>
                    <th className="px-3 py-2 text-right">Mejor precio cargado</th>
                    <th className="px-3 py-2 text-center">Regulado</th>
                    <th className="px-3 py-2 text-right">Tope máx.</th>
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
                    (() => {
                      // Determinar la mejor opción: menor precio proveedor primero, luego SISMED
                      // Para regulados, solo considerar precios ≤ tope
                      const getEfectivo = (item: (typeof comparativaResultados)[number]) => {
                        const pp = item.mejorPrecioProveedor ?? null;
                        const ss = item.precioUnitario ?? null;
                        const tope = item.precioMaximoRegulado ?? null;
                        if (item.esRegulado && tope != null) {
                          const ppOk = pp != null && pp <= tope ? pp : null;
                          const ssOk = ss != null && ss <= tope ? ss : null;
                          if (ppOk != null && ssOk != null) return Math.min(ppOk, ssOk);
                          return ppOk ?? ssOk ?? pp ?? ss;
                        }
                        if (pp != null && ss != null) return Math.min(pp, ss);
                        return pp ?? ss;
                      };
                      const efectivos = comparativaResultados.map(getEfectivo);
                      const minEfectivo = efectivos.reduce<number | null>(
                        (m, v) => (v != null && (m == null || v < m) ? v : m),
                        null,
                      );
                      return comparativaResultados.map((item, idx) => {
                        const esMejor = efectivos[idx] != null && efectivos[idx] === minEfectivo;
                        const ppExcede = item.esRegulado && item.precioMaximoRegulado != null
                          && item.mejorPrecioProveedor != null
                          && item.mejorPrecioProveedor > item.precioMaximoRegulado;
                        return (
                          <tr
                            key={item.id}
                            className={`border-t border-slate-100 ${esMejor ? "bg-emerald-50" : ""}`}
                          >
                            <td className="px-3 py-2 font-medium">
                              <span className="flex items-center gap-2">
                                {esMejor && (
                                  <span className="inline-flex items-center rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-700">
                                    ★ Mejor
                                  </span>
                                )}
                                {toTitleCase(item.nombreLimpio)}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-slate-500">{toTitleCase(item.laboratorio) || "-"}</td>
                            <td className="px-3 py-2 text-right text-slate-500 tabular-nums">
                              {formatPrice(item.precioUnitario) || "-"}
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums">
                              {item.mejorPrecioProveedor != null ? (
                                <span className="flex flex-col items-end gap-0.5">
                                  <span className={`font-semibold ${ppExcede ? "text-red-600" : "text-teal-700"}`}>
                                    {formatPrice(item.mejorPrecioProveedor)}
                                  </span>
                                  {item.mejorProveedorNombre && (
                                    <span className="text-[10px] text-slate-400">{item.mejorProveedorNombre}</span>
                                  )}
                                  {ppExcede && (
                                    <span className="text-[10px] font-semibold text-red-500">⚠ Excede tope</span>
                                  )}
                                </span>
                              ) : (
                                <span className="text-slate-300">Sin precio</span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-center">
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
                            <td className="px-3 py-2 text-right tabular-nums text-orange-600">
                              {formatPrice(item.precioMaximoRegulado) || "-"}
                            </td>
                          </tr>
                        );
                      });
                    })()
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
