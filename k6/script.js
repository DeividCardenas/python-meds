import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate = new Rate("errors");
const comparativaLatency = new Trend("comparativa_precios_latency", true);

export const options = {
  stages: [
    { duration: "10s", target: 50 },
    { duration: "40s", target: 50 },
    { duration: "10s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<2000"],
    errors: ["rate<0.05"],
  },
};

const GRAPHQL_URL = __ENV.GRAPHQL_URL || "http://backend:8000/graphql";

const ACTIVE_INGREDIENTS = [
  "acetaminofen",
  "ibuprofeno",
  "amoxicilina",
  "metformina",
  "atorvastatina",
  "omeprazol",
  "losartan",
  "aspirina",
  "diclofenaco",
  "naproxeno",
];

const COMPARATIVA_PRECIOS_QUERY = `
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

export default function () {
  const principioActivo =
    ACTIVE_INGREDIENTS[Math.floor(Math.random() * ACTIVE_INGREDIENTS.length)];

  const payload = JSON.stringify({
    query: COMPARATIVA_PRECIOS_QUERY,
    variables: { principioActivo },
  });

  const params = {
    headers: { "Content-Type": "application/json" },
  };

  const res = http.post(GRAPHQL_URL, payload, params);

  const success = check(res, {
    "status is 200": (r) => r.status === 200,
    "no GraphQL errors": (r) => {
      try {
        const body = JSON.parse(r.body);
        return !body.errors;
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!success);
  comparativaLatency.add(res.timings.duration);

  sleep(1);
}
