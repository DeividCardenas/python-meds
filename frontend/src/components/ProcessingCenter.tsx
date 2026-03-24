"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileUp, Play, Sparkles } from "lucide-react";

type ProcessingCenterProps = {
  progressPct: number;
  isProcessing?: boolean;
  isCompleted?: boolean;
  onStartAudit?: (file: File | null) => void;
  className?: string;
};

function clampPct(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Number(value)));
}

function getProgressMessage(progress: number): string {
  if (progress >= 100) return "Cruce completado!";
  if (progress >= 71) return "Calculando mejores ofertas...";
  if (progress >= 31) return "Cruzando tarifas en el grafo...";
  return "Leyendo lista de precios...";
}

export default function ProcessingCenter({
  progressPct,
  isProcessing = false,
  isCompleted = false,
  onStartAudit,
  className,
}: ProcessingCenterProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [localProcessing, setLocalProcessing] = useState(false);

  const showProcessing = isProcessing || localProcessing || isCompleted;
  const safeProgress = clampPct(progressPct);
  const progressMessage = useMemo(() => getProgressMessage(safeProgress), [safeProgress]);

  const handleFiles = (files: FileList | null) => {
    const nextFile = files && files.length > 0 ? files[0] : null;
    setSelectedFile(nextFile);
  };

  const handleStart = () => {
    setLocalProcessing(true);
    onStartAudit?.(selectedFile);
  };

  return (
    <section className={[
      "relative w-full max-w-4xl mx-auto p-4 sm:p-6 lg:p-8",
      className ?? "",
    ].join(" ")}
    >
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden rounded-3xl">
        <div className="absolute -top-24 -left-10 h-52 w-52 rounded-full bg-cyan-400/20 blur-3xl" />
        <div className="absolute -bottom-24 -right-8 h-56 w-56 rounded-full bg-blue-500/20 blur-3xl" />
      </div>

      <AnimatePresence mode="wait">
        {!showProcessing ? (
          <motion.div
            key="upload"
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.98 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="rounded-3xl border border-white/30 bg-white/55 p-5 shadow-[0_8px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl sm:p-8"
          >
            <div
              className={[
                "relative rounded-2xl border-2 border-dashed p-8 text-center transition-all sm:p-12",
                isDragOver
                  ? "border-cyan-500/70 bg-cyan-100/40"
                  : "border-slate-300/70 bg-white/50 hover:border-cyan-400/70 hover:bg-cyan-50/40",
              ].join(" ")}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={(event) => {
                event.preventDefault();
                setIsDragOver(false);
                handleFiles(event.dataTransfer.files);
              }}
            >
              <input
                id="contrato-upload"
                type="file"
                className="sr-only"
                accept=".csv,.xlsx,.xls,.tsv"
                onChange={(event) => handleFiles(event.target.files)}
              />

              <label htmlFor="contrato-upload" className="cursor-pointer">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg shadow-slate-900/20">
                  <FileUp className="h-7 w-7" />
                </div>
                <h3 className="text-lg font-semibold tracking-tight text-slate-900 sm:text-xl">
                  Arrastra tu lista de precios aqui
                </h3>
                <p className="mt-2 text-sm text-slate-600 sm:text-base">
                  o haz click para cargar CSV/Excel y lanzar el cruce inteligente de tarifas.
                </p>
              </label>

              {selectedFile && (
                <p className="mt-5 inline-flex items-center rounded-full border border-slate-200 bg-white/70 px-3 py-1 text-xs font-medium text-slate-700 sm:text-sm">
                  Archivo seleccionado: {selectedFile.name}
                </p>
              )}
            </div>

            <div className="mt-6 flex items-center justify-center">
              <button
                type="button"
                onClick={handleStart}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-800 hover:shadow-lg hover:shadow-slate-900/25 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
              >
                <Play className="h-4 w-4" />
                Iniciar Cruce de Tarifas
              </button>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="processing"
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.98 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="rounded-3xl border border-white/30 bg-white/55 p-5 shadow-[0_8px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl sm:p-8"
          >
            <div className="grid gap-4 sm:grid-cols-[auto,1fr] sm:items-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg shadow-slate-900/20">
                <Sparkles className="h-7 w-7" />
              </div>
              <div>
                <h3 className="text-lg font-semibold tracking-tight text-slate-900 sm:text-xl">
                  Centro de Procesamiento
                </h3>
                <p className="text-sm text-slate-600 sm:text-base">
                  Seguimiento en tiempo real del cruce inteligente de tarifas.
                </p>
              </div>
            </div>

            <div className="mt-6 rounded-2xl border border-slate-200/70 bg-white/70 p-4 backdrop-blur-md sm:p-5">
              <div className="mb-3 flex items-center justify-between text-sm">
                <span className="font-medium text-slate-700">Progreso</span>
                <span className="font-semibold text-slate-900">{safeProgress.toFixed(2)}%</span>
              </div>

              <div className="relative h-3 overflow-hidden rounded-full bg-slate-200/80">
                <motion.div
                  className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-500"
                  initial={{ width: "0%" }}
                  animate={{ width: `${safeProgress}%` }}
                  transition={{ duration: 0.45, ease: "easeOut" }}
                />
                <motion.div
                  className="pointer-events-none absolute inset-y-0 w-24 bg-gradient-to-r from-transparent via-white/60 to-transparent"
                  animate={{ x: ["-40%", "220%"] }}
                  transition={{ duration: 1.8, ease: "linear", repeat: Infinity }}
                />
              </div>

              <motion.p
                key={progressMessage}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className="mt-3 text-sm font-medium text-slate-700"
              >
                {progressMessage}
              </motion.p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
