import { useRef, type ChangeEvent, type DragEvent } from "react";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface UploadStepProps {
  onFileSelected: (file: File) => void;
  isLoading: boolean;
  dragOver: boolean;
  onDragOver: () => void;
  onDragLeave: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function UploadStep({
  onFileSelected,
  isLoading,
  dragOver,
  onDragOver,
  onDragLeave,
}: UploadStepProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelected(file);
    e.target.value = "";
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    onDragLeave();
    const file = e.dataTransfer.files[0];
    if (file) onFileSelected(file);
  };

  return (
    <div
      onDragOver={(e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        onDragOver();
      }}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => fileInputRef.current?.click()}
      className={`relative flex cursor-pointer flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-12 transition-all duration-300 ${
        dragOver
          ? "scale-[1.02] border-blue-400 bg-blue-50/70 shadow-lg shadow-blue-100"
          : "border-slate-200 bg-slate-50/50 hover:border-teal-300 hover:bg-teal-50/30"
      }`}
    >
      {/* Upload icon */}
      <div
        className={`rounded-2xl p-4 transition-all duration-300 ${
          dragOver ? "bg-blue-100" : "bg-white shadow-sm border border-slate-200"
        }`}
      >
        <svg
          className={`h-8 w-8 transition-colors duration-300 ${dragOver ? "text-blue-500" : "text-slate-400"}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center gap-2">
          <svg
            className="h-5 w-5 animate-spin text-teal-600"
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <p className="text-sm font-semibold text-teal-600 animate-pulse">
            Analizando estructura del archivo…
          </p>
        </div>
      ) : (
        <div className="text-center space-y-1">
          <p className="text-sm font-semibold text-slate-700">
            {dragOver
              ? "Suelta para cargar el tarifario"
              : "Arrastra tu archivo aquí"}
          </p>
          <p className="text-xs text-slate-400">
            o{" "}
            <span className="text-teal-600 underline underline-offset-2 font-medium">
              haz clic para explorar
            </span>
          </p>
          <p className="text-[10px] text-slate-300 pt-1">
            CSV · XLSX · XLS — máx. 10 MB
          </p>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="hidden"
        onChange={onFileChange}
      />
    </div>
  );
}
