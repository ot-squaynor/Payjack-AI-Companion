export interface Citation {
  doc_id: string;
  title: string;
  snippet: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface ToolTrace {
  name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
  warnings: string[];
  artifact_version: string | null;
}

export interface Refusal {
  category: string;
  message: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string | null;
  client_request_id?: string | null;
}

export interface ChatResponse {
  request_id: string;
  session_id: string;
  route: string;
  answer: string;
  tool_traces: ToolTrace[];
  citations: Citation[];
  refusal: Refusal | null;
  debug: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
  app?: string;
  environment?: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
  toolResult?: ToolInvokeResponse;
}

// --- Direct Tool Invocation ---

export type ToolName =
  | "transaction_lookup"
  | "spend_summary"
  | "recurring_detection"
  | "balances"
  | "status_explanation"
  | "fee_breakdown";

export interface ToolInvokeRequest {
  tool: ToolName;
  arguments: Record<string, unknown>;
}

export interface ToolInvokeResponse {
  request_id: string;
  tool: ToolName;
  arguments: Record<string, unknown>;
  payload: Record<string, unknown>;
  warnings: string[];
  artifact_version: string | null;
  latency_ms: number;
}

// --- Per-tool argument types (used by form components) ---

export interface TransactionLookupArgs {
  date_from?: string;
  date_to?: string;
  merchant?: string;
  category?: string;
  direction?: "debit" | "credit";
  amount_min?: number;
  amount_max?: number;
  limit?: number;
  sort_by?: string;
  sort_descending?: boolean;
}

export interface SpendSummaryArgs {
  date_from?: string;
  date_to?: string;
  categories?: string[];
  merchants?: string[];
  direction?: "debit" | "credit";
  group_by?: "category" | "merchant" | "month" | "currency";
}

export interface RecurringDetectionArgs {
  cadence?: "weekly" | "biweekly" | "monthly" | "irregular";
  confidence?: "low" | "medium" | "high";
  merchants?: string[];
  categories?: string[];
  include_irregular?: boolean;
  min_average_amount?: number;
}

export interface BalancesArgs {
  account_ids?: string[];
}

export interface StatusExplanationArgs {
  date_from?: string;
  date_to?: string;
}

export interface FeeBreakdownArgs {
  date_from?: string;
  date_to?: string;
  transaction_ids?: string[];
  limit?: number;
}

// --- Per-tool payload types (used by ToolResultCard renderer) ---
// All monetary amounts are serialized as decimal strings by the backend.

export interface TransactionRecord {
  transaction_id: string;
  account_id: string;
  timestamp: string;
  amount: string;
  currency: string;
  direction: string;
  merchant: string;
  category: string;
  subcategory: string;
}

export interface TransactionLookupPayload {
  records: TransactionRecord[];
  match_count: number;
  applied_filters: Record<string, unknown>;
  warnings: string[];
}

export interface SpendSummaryPayload {
  total_amount: string;
  transaction_count: number;
  currency_breakdown: Record<string, string>;
  grouped_breakdown: Array<{
    key: string;
    total_amount: string;
    transaction_count: number;
    currency: string;
  }>;
  applied_filters: Record<string, unknown>;
  warnings: string[];
}

export interface RecurringRecord {
  merchant: string;
  category: string;
  subcategory: string;
  account_id: string;
  direction: string;
  cadence: string;
  confidence: string;
  transaction_count: number;
  first_seen_timestamp: string;
  last_seen_timestamp: string;
  average_amount: string;
  currency: string;
  is_irregular: boolean;
}

export interface RecurringDetectionPayload {
  records: RecurringRecord[];
  match_count: number;
  summary: Record<string, unknown>;
  applied_filters: Record<string, unknown>;
  warnings: string[];
}

export interface BalanceRecord {
  account_id: string;
  account_name: string | null;
  currency: string | null;
  current_balance: string | null;
  available_balance: string | null;
}

export interface BalancesPayload {
  records: BalanceRecord[];
  warnings: string[];
}

export interface StatusExplanationPayload {
  counts_by_status: Record<string, number>;
  warnings: string[];
}

export interface FeeRecord {
  transaction_id: string;
  account_id: string;
  timestamp: string;
  amount: string;
  currency: string;
  direction: string;
  merchant: string;
  category: string;
  subcategory: string;
  matched_reason: string;
}

export interface FeeBreakdownPayload {
  records: FeeRecord[];
  total_amount: string;
  transaction_count: number;
  currency_breakdown: Record<string, string>;
  applied_filters: Record<string, unknown>;
  warnings: string[];
}
