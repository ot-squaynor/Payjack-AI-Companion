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
}
