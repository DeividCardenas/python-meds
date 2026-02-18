import { useState, type DragEvent, type FormEvent } from "react";
import { useMutation } from "@apollo/client";

import {
  CargarInvimaDocument,
  type CargarInvimaMutation,
  type CargarInvimaMutationVariables,
} from "../graphql/generated";

export function CargaInvima() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [historial, setHistorial] = useState<Array<{ id: string; filename: string; status: string }>>([]);
  const [cargarInvima, { data, loading, error }] = useMutation<
    CargarInvimaMutation,
    CargarInvimaMutationVariables
  >(CargarInvimaDocument);

  const currentStatus = data?.cargarMaestroInvima.status;

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      return;
    }
    const result = await cargarInvima({ variables: { file } });
    const payload = result.data?.cargarMaestroInvima;
    if (payload) {
      setHistorial((prev) => [payload, ...prev].slice(0, 5));
    }
  };

  const onDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => {
    setIsDragging(false);
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    setFile(event.dataTransfer.files?.[0] ?? null);
  };

  const statusIcon = (status: string) => {
    if (status === "COMPLETED") {
      return <span className="text-emerald-600">✔</span>;
    }
    if (status === "FAILED") {
      return <span className="text-red-600">✖</span>;
    }
    return <span className="text-blue-600">•</span>;
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-xl font-semibold">Carga Masiva INVIMA</h2>
        <p className="mt-1 text-sm text-slate-600">Sube archivos TSV/CSV/TXT para procesamiento en lote.</p>
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        <label
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          className={`flex min-h-56 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${
            isDragging ? "border-teal-600 bg-teal-50" : "border-slate-300 bg-slate-50 hover:border-blue-600"
          }`}
        >
          <svg viewBox="0 0 24 24" className="mb-4 h-16 w-16 fill-none stroke-current text-slate-500" aria-hidden="true">
            <path d="M12 16V6m0 0-3.5 3.5M12 6l3.5 3.5" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M5 16.5a4.5 4.5 0 0 1 .9-8.9A6.5 6.5 0 0 1 18.6 9h.4a4 4 0 0 1 0 8H6.5" strokeWidth="1.75" strokeLinecap="round" />
          </svg>
          <p className="text-sm font-medium text-slate-700">Arrastra tu archivo aquí o haz clic para seleccionar</p>
          <p className="mt-1 text-xs text-slate-500">Formatos permitidos: .tsv, .csv, .txt</p>
          <input
            type="file"
            accept=".tsv,.csv,.txt"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="hidden"
          />
        </label>

        {file ? <p className="text-sm text-slate-600">Archivo seleccionado: {file.name}</p> : null}

        <button
          type="submit"
          disabled={!file || loading}
          className="h-11 rounded-lg bg-blue-600 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Cargando..." : "Cargar archivo"}
        </button>
      </form>

      {currentStatus === "PROCESSING" ? (
        <div className="mt-5">
          <div className="mb-1 flex items-center justify-between text-xs font-medium text-slate-600">
            <span>Procesando archivo</span>
            <span>66%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
            <div className="h-full w-2/3 rounded-full bg-teal-600 transition-all" />
          </div>
        </div>
      ) : null}

      {error ? <p className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">Error: {error.message}</p> : null}

      <div className="mt-6 rounded-xl border border-slate-200">
        <div className="border-b border-slate-200 px-4 py-3">
          <h3 className="text-sm font-semibold text-slate-700">Historial de cargas</h3>
        </div>
        <ul className="divide-y divide-slate-100">
          {historial.map((item) => (
            <li key={item.id} className="flex items-center justify-between px-4 py-3 text-sm">
              <div className="flex items-center gap-2">
                {statusIcon(item.status)}
                <span className="text-slate-700">{item.filename}</span>
              </div>
              <span className="font-medium text-slate-500">{item.status}</span>
            </li>
          ))}
          {historial.length === 0 ? <li className="px-4 py-6 text-sm text-slate-500">Aún no hay cargas registradas.</li> : null}
        </ul>
      </div>
    </section>
  );
}
