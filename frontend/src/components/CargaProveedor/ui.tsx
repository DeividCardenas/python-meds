import type { ReactNode } from "react";
import type { Sugerencia } from "./types";

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

export function parseSugerencias(json: string | null | undefined): Sugerencia[] {
  if (!json) return [];
  try {
    const val = JSON.parse(json);
    return Array.isArray(val) ? (val as Sugerencia[]) : [];
  } catch {
    return [];
  }
}

export const formatPrice = (v: number | null | undefined): string =>
  typeof v === "number" && Number.isFinite(v)
    ? new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        maximumFractionDigits: 2,
      }).format(v)
    : "—";

export const scoreColor = (s: number): string =>
  s >= 0.99
    ? "text-emerald-600"
    : s >= 0.8
    ? "text-amber-500"
    : "text-red-500";

export const scoreBg = (s: number): string =>
  s >= 0.99
    ? "bg-emerald-50 border-emerald-200"
    : s >= 0.8
    ? "bg-amber-50 border-amber-200"
    : "bg-red-50 border-red-200";

export function detectSupplier(filename: string | null): string | null {
  if (!filename) return null;
  const lower = filename.toLowerCase();
  if (
    lower.includes("la_sante") ||
    lower.includes("lasante") ||
    lower.includes("la sante")
  )
    return "La Santé";
  if (lower.includes("megalabs")) return "Megalabs";
  if (lower.includes("genfar")) return "Genfar";
  if (lower.includes("pfizer")) return "Pfizer";
  if (lower.includes("bayer")) return "Bayer";
  return null;
}

// ---------------------------------------------------------------------------
// Shared UI atoms
// ---------------------------------------------------------------------------

/** Circular SVG progress ring */
export function ProgressRing({
  value,
  max,
  size = 88,
  strokeWidth = 6,
}: {
  value: number;
  max: number;
  size?: number;
  strokeWidth?: number;
}) {
  const r = (size - strokeWidth) / 2;
  const circ = 2 * Math.PI * r;
  const pct = max > 0 ? Math.min(value / max, 1) : 0;
  const offset = circ * (1 - pct);
  const color = pct >= 1 ? "#059669" : pct >= 0.5 ? "#0d9488" : "#3b82f6";
  return (
    <svg
      width={size}
      height={size}
      style={{ transform: "rotate(-90deg)" }}
      aria-hidden="true"
    >
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="#e2e8f0"
        strokeWidth={strokeWidth}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        style={{
          transition: "stroke-dashoffset 0.5s ease, stroke 0.5s ease",
        }}
      />
    </svg>
  );
}

/** Generic Bento card shell */
export function BentoBox({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl bg-white border border-slate-200/80 shadow-sm ring-1 ring-slate-900/5 overflow-hidden transition-all duration-500 ${className}`}
    >
      {children}
    </div>
  );
}

/** Small colored badge pill */
export function Pill({
  label,
  color = "slate",
}: {
  label: string;
  color?: "emerald" | "amber" | "blue" | "slate" | "violet";
}) {
  const map: Record<string, string> = {
    emerald: "bg-emerald-100 text-emerald-700 border-emerald-200",
    amber: "bg-amber-100 text-amber-700 border-amber-200",
    blue: "bg-blue-100 text-blue-700 border-blue-200",
    slate: "bg-slate-100 text-slate-600 border-slate-200",
    violet: "bg-violet-100 text-violet-700 border-violet-200",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide ${map[color]}`}
    >
      {label}
    </span>
  );
}
