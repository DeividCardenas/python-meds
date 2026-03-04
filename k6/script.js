/**
 * k6 load-test suite — python-meds backend
 *
 * Escenarios:
 *   comparativaPrecios  — 50 VUs / 60 s  (escenario original)
 *   buscarMedicamentos  — 30 VUs / 60 s  (Escenario A)
 *   sugerenciasCum      — 20 VUs / 30 s  (Escenario B)
 *   healthCheck         — 100 VUs / 30 s (Escenario C)
 */

import { check, sleep } from "k6";
import http from "k6/http";
import { Rate, Trend } from "k6/metrics";

// ── Métricas por escenario ────────────────────────────────────────────────────
const errComparativa  = new Rate("err_comparativa");
const errBuscar       = new Rate("err_buscar");
const errSugerencias  = new Rate("err_sugerencias");
const errHealth       = new Rate("err_health");

const latComparativa  = new Trend("lat_comparativa_ms",  true);
const latBuscar       = new Trend("lat_buscar_ms",       true);
const latSugerencias  = new Trend("lat_sugerencias_ms",  true);
const latHealth       = new Trend("lat_health_ms",       true);

// ── Configuración de escenarios ───────────────────────────────────────────────
export const options = {
  scenarios: {
    // ── Escenario original: comparativaPrecios ────────────────────────────────
    comparativaPrecios: {
      executor: "constant-vus",
      vus: 50,
      duration: "60s",
      exec: "runComparativaPrecios",
      startTime: "0s",
    },
    // ── Escenario A: buscarMedicamentos ───────────────────────────────────────
    buscarMedicamentos: {
      executor: "constant-vus",
      vus: 30,
      duration: "60s",
      exec: "runBuscarMedicamentos",
      startTime: "0s",
    },
    // ── Escenario B: sugerenciasCum ───────────────────────────────────────────
    sugerenciasCum: {
      executor: "constant-vus",
      vus: 20,
      duration: "30s",
      exec: "runSugerenciasCum",
      startTime: "0s",
    },
    // ── Escenario C: /health gateway ─────────────────────────────────────────
    healthCheck: {
      executor: "constant-vus",
      vus: 100,
      duration: "30s",
      exec: "runHealthCheck",
      startTime: "0s",
    },
  },

  thresholds: {
    // Escenario original
    "http_req_duration{scenario:comparativaPrecios}": ["p(95)<2000"],
    "err_comparativa": ["rate<0.05"],
    // Escenario A
    "http_req_duration{scenario:buscarMedicamentos}": ["p(95)<1500"],
    "err_buscar": ["rate<0.02"],
    // Escenario B
    "http_req_duration{scenario:sugerenciasCum}": ["p(95)<800"],
    "err_sugerencias": ["rate<0.02"],
    // Escenario C
    "http_req_duration{scenario:healthCheck}": ["p(99)<200"],
    "err_health": ["rate<0.01"],
  },
};

// ── URLs y helpers ────────────────────────────────────────────────────────────
const GRAPHQL_URL = __ENV.GRAPHQL_URL || "http://localhost:8000/graphql";
const HEALTH_URL  = (__ENV.GRAPHQL_URL || "http://localhost:8000/graphql")
  .replace("/graphql", "/health");

const JSON_HEADERS = { headers: { "Content-Type": "application/json" } };

/** Devuelve true si la respuesta NO tiene errores GraphQL */
function noGqlErrors(res) {
  try {
    const body = JSON.parse(res.body);
    return !body.errors;
  } catch (_) {
    return false;
  }
}

function gqlPost(query, variables) {
  return http.post(GRAPHQL_URL, JSON.stringify({ query, variables }), JSON_HEADERS);
}

// ── Datos de prueba ───────────────────────────────────────────────────────────
const PRINCIPIOS = [
  "acetaminofen", "ibuprofeno", "amoxicilina", "metformina",
  "atorvastatina", "omeprazol", "losartan", "aspirina",
  "diclofenaco", "naproxeno",
];

const TEXTOS_BUSQUEDA = [
  "acetaminofen tabletas", "ibuprofeno 400mg", "amoxicilina 500mg capsula",
  "metformina 850", "omeprazol 20mg", "losartan potasico 50mg",
  "sildenafil 100", "enalapril 10mg", "furosemida inyectable", "insulina glargina",
  "clonazepam 2mg", "azitromicina 500", "ranitidina", "salbutamol inhalador",
  "prednisona", "hidroclorotiazida", "warfarina 5mg", "morfina sulfato",
];

const TEXTOS_CUM = [
  "acetaminofen 500mg tableta oral",
  "ibuprofeno 400 mg tableta recubierta",
  "amoxicilina 500mg capsula",
  "metformina 850mg tableta",
  "atorvastatina 20mg tableta",
  "omeprazol 20mg capsula",
  "losartan potasico 50mg tableta",
  "aspirina 100mg tableta",
];

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

// ── Queries GQL ───────────────────────────────────────────────────────────────
const COMPARATIVA_QUERY = `
  query ComparativaPrecios($principioActivo: String!) {
    comparativaPrecios(principioActivo: $principioActivo) {
      id
      nombreLimpio
      laboratorio
      principioActivo
      precioUnitario
      precioEmpaque
      esRegulado
      precioMaximoRegulado
    }
  }
`;

const BUSCAR_QUERY = `
  query BuscarMedicamentos($texto: String!) {
    buscarMedicamentos(texto: $texto) {
      id
      nombreLimpio
      laboratorio
      principioActivo
      formaFarmaceutica
    }
  }
`;

const SUGERENCIAS_QUERY = `
  query SugerenciasCum($texto: String!) {
    sugerenciasCum(texto: $texto) {
      idCum
      nombre
      score
      principioActivo
      laboratorio
    }
  }
`;

// ── Funciones de escenario ────────────────────────────────────────────────────

/** Escenario original — comparativaPrecios */
export function runComparativaPrecios() {
  const res = gqlPost(COMPARATIVA_QUERY, { principioActivo: pick(PRINCIPIOS) });
  const ok = check(res, {
    "comparativa: HTTP 200":     (r) => r.status === 200,
    "comparativa: sin errores GQL": noGqlErrors,
  });
  errComparativa.add(!ok);
  latComparativa.add(res.timings.duration);
  sleep(1);
}

/** Escenario A — buscarMedicamentos bajo carga */
export function runBuscarMedicamentos() {
  const res = gqlPost(BUSCAR_QUERY, { texto: pick(TEXTOS_BUSQUEDA) });
  const ok = check(res, {
    "buscar: HTTP 200":          (r) => r.status === 200,
    "buscar: sin errores GQL":   noGqlErrors,
    "buscar: body no vacío":     (r) => {
      try {
        const b = JSON.parse(r.body);
        return Array.isArray(b?.data?.buscarMedicamentos);
      } catch (_) { return false; }
    },
  });
  errBuscar.add(!ok);
  latBuscar.add(res.timings.duration);
  sleep(1);
}

/** Escenario B — sugerenciasCum */
export function runSugerenciasCum() {
  const res = gqlPost(SUGERENCIAS_QUERY, { texto: pick(TEXTOS_CUM) });
  const ok = check(res, {
    "sugerencias: HTTP 200":     (r) => r.status === 200,
    "sugerencias: sin errores GQL": noGqlErrors,
  });
  errSugerencias.add(!ok);
  latSugerencias.add(res.timings.duration);
  sleep(0.5);
}

/** Escenario C — /health gateway */
export function runHealthCheck() {
  const res = http.get(HEALTH_URL);
  const ok = check(res, {
    "health: HTTP 200":          (r) => r.status === 200,
    "health: status=ok":         (r) => {
      try { return JSON.parse(r.body)?.status === "ok"; }
      catch (_) { return false; }
    },
  });
  errHealth.add(!ok);
  latHealth.add(res.timings.duration);
  sleep(0.1);
}

// Export requerido por k6 (fallback vacío — los escenarios tienen exec explícito)
export default function () {}

