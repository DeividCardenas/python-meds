import { useMemo, useState } from "react";

import { BuscadorMedicamentos } from "./components/BuscadorMedicamentos";
import { CargaInvima } from "./components/CargaInvima";
import { CargaProveedor } from "./components/CargaProveedor";

const sections = ["Buscador", "Carga Masiva", "Proveedores", "Auditoría"] as const;
type Section = (typeof sections)[number];

function App() {
  const [activeSection, setActiveSection] = useState<Section>("Buscador");
  const breadcrumb = useMemo(() => `Inicio / ${activeSection}`, [activeSection]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <aside className="fixed inset-y-0 left-0 w-64 border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-6 py-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-teal-600">Python Meds</p>
          <h1 className="mt-1 text-lg font-semibold">Dashboard Médico</h1>
        </div>
        <nav className="p-4">
          <ul className="space-y-2">
            {sections.map((section) => {
              const isActive = section === activeSection;
              return (
                <li key={section}>
                  <button
                    type="button"
                    onClick={() => setActiveSection(section)}
                    className={`w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors ${
                      isActive ? "bg-blue-600 text-white shadow-sm" : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {section}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>

      <div className="ml-64 min-h-screen">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 px-8 py-4 backdrop-blur">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">{breadcrumb}</p>
            <div className="flex items-center gap-3 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-teal-600 text-sm font-semibold text-white">
                DR
              </span>
              <div className="text-sm leading-tight">
                <p className="font-medium text-slate-800">Dra. Rivera</p>
                <p className="text-xs text-slate-500">Administrador</p>
              </div>
            </div>
          </div>
        </header>

        <main className="space-y-6 p-8">
          {activeSection === "Buscador" ? <BuscadorMedicamentos /> : null}
          {activeSection === "Carga Masiva" ? <CargaInvima /> : null}
          {activeSection === "Proveedores" ? <CargaProveedor /> : null}
          {activeSection === "Auditoría" ? (
            <section className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
              <h2 className="text-lg font-semibold">Auditoría</h2>
              <p className="mt-2 text-sm text-slate-600">Próximamente: bitácora de trazabilidad y eventos de carga.</p>
            </section>
          ) : null}
        </main>
      </div>
    </div>
  );
}

export default App;
