export interface HealthResponse {
  status: string;
  version: string;
  pipeline_loaded: boolean;
  match_rate: string;
}

export interface DeterministicPass {
  matched: number;
  rate: string;
  full_triples: number;
  amount_disagreements: number;
  date_drifts: number;
}

export interface FuzzyPass {
  additional_matched: number;
  split_detected: number;
  batch_detected: number;
  fuzzy_amount_date_edit: number;
}

export interface FinalStats {
  matched: number;
  rate: string;
}

export interface UnmatchedStats {
  gateway: number;
  exceptions_total: number;
}

export interface SummaryResponse {
  gateway_total: number;
  bank_total: number;
  ledger_total: number;
  deterministic_pass: DeterministicPass;
  fuzzy_pass: FuzzyPass;
  final: FinalStats;
  improvement_pp: string;
  unmatched: UnmatchedStats;
}

export interface PipelineResponse {
  gateway_total: number;
  bank_total: number;
  ledger_total: number;
  deterministic_matched: number;
  fuzzy_matched: number;
  total_matched: number;
  exceptions_total: number;
  exception_types: Record<string, number>;
  deterministic_rate: string;
  final_rate: string;
}

export interface ExceptionItem {
  exception_id: string;
  type: string;
  source: string;
  record_id: string;
  amount?: string;
  date?: string;
  reason: string;
}

export interface ExceptionsResponse {
  filter_applied: string;
  total: number;
  by_type: Record<string, number>;
  exceptions: ExceptionItem[];
}

export interface BankSettlementInfo {
  utr: string;
  settlement_amount: string;
  settlement_date: string;
}

export interface MerchantLedgerInfo {
  order_id: string;
  expected_amount: string;
  entry_date: string;
  notes: string;
}

export interface TransactionMatchedResponse {
  txn_id: string;
  status: string;
  match_pass: string;
  method: string;
  confidence: number;
  gateway_amount: string;
  gateway_date: string;
  gateway_fee: string;
  amount_agrees: boolean;
  date_lag_days?: number;
  bank_settlement?: BankSettlementInfo;
  merchant_ledger?: MerchantLedgerInfo;
}

export interface TransactionExceptionResponse {
  txn_id: string;
  status: string;
  exception_id: string;
  exception_type: string;
  source: string;
  amount?: string;
  date?: string;
  reason: string;
  evidence: Record<string, unknown>;
  linked_record_ids: string[];
}

export interface TransactionNotFoundResponse {
  txn_id: string;
  status: string;
  error: string;
  hint?: string;
}

export interface CashComponent {
  description: string;
  count: number;
  order_ids: string[];
  exposure_inr: string;
}

export interface BatchPendingComponent {
  description: string;
  count: number;
  exposure_inr: string;
}

export interface CashPositionResponse {
  as_of: string;
  missing_settlement: CashComponent;
  orphan_ledger: CashComponent;
  batch_settlement_pending: BatchPendingComponent;
  total_unreconciled_inr: string;
}

export interface ForecastEntry {
  forecast_date: string;
  order_id: string;
  amount_inr: string;
  confidence: number;
  reason: string;
  source_exception_type: string;
}

export interface ForecastResponse {
  generated_at: string;
  horizon_days: number;
  total_forecast_inr: string;
  by_date: Record<string, string>;
  by_exception_type: Record<string, string>;
  entries: ForecastEntry[];
}

export interface ToolUsed {
  name: string;
  input: Record<string, unknown>;
  result_summary: string;
}

export interface ChatResponse {
  answer: string;
  tools_used: ToolUsed[];
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
}

export interface RunDemoResponse {
  status: string;
  message: string;
  match_rate: string;
  exceptions: number;
  tests_passed: boolean;
}

export interface ReconciliationReportResponse {
  generated_at?: string;
  pipeline?: string;
  record_counts?: Record<string, number>;
  match_rates?: Record<string, unknown>;
  exceptions?: Record<string, unknown>;
  ground_truth_comparison?: Record<string, unknown>;
}
