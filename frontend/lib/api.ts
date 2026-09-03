import type {
  HealthResponse,
  SummaryResponse,
  PipelineResponse,
  ExceptionsResponse,
  TransactionMatchedResponse,
  TransactionExceptionResponse,
  TransactionNotFoundResponse,
  CashPositionResponse,
  ForecastResponse,
  ChatResponse,
  RunDemoResponse,
  ReconciliationReportResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

export const api = {
  health: () => fetchApi<HealthResponse>("/api/v1/health"),

  summary: () => fetchApi<SummaryResponse>("/api/v1/summary"),

  pipeline: () => fetchApi<PipelineResponse>("/api/v1/pipeline"),

  exceptions: (type?: string) => {
    const params = type ? `?type=${encodeURIComponent(type)}` : "";
    return fetchApi<ExceptionsResponse>(`/api/v1/exceptions${params}`);
  },

  transaction: (txnId: string) =>
    fetchApi<
      TransactionMatchedResponse | TransactionExceptionResponse | TransactionNotFoundResponse
    >(`/api/v1/transactions/${encodeURIComponent(txnId)}`),

  cashPosition: () => fetchApi<CashPositionResponse>("/api/v1/cash-position"),

  forecast: () => fetchApi<ForecastResponse>("/api/v1/forecast"),

  chat: (question: string, provider?: string) =>
    fetchApi<ChatResponse>("/api/v1/chat", {
      method: "POST",
      body: JSON.stringify({ question, provider }),
    }),

  runDemo: () =>
    fetchApi<RunDemoResponse>("/api/v1/runs/demo", { method: "POST" }),

  report: () =>
    fetchApi<ReconciliationReportResponse>("/api/v1/reports/reconciliation"),
};
