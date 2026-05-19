import type { ChatRequest, ChatResponse, HealthResponse } from "@/lib/types";

const DEFAULT_API_BASE_URL =
  process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : "/api";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL;

function buildHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "x-payjack-user-id": process.env.NEXT_PUBLIC_DEFAULT_USER_ID || "dev-user",
    "x-payjack-tenant-id": process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID || "dev-tenant",
    "x-payjack-account-ids": process.env.NEXT_PUBLIC_DEFAULT_ACCOUNT_IDS || ""
  };
}

async function readJsonResponse<T>(response: Response, endpointName: string): Promise<T> {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("application/json")) {
    const body = await response.text();
    const preview = body.trim().slice(0, 80);
    throw new Error(
      `${endpointName} returned ${contentType || "a non-JSON response"} instead of JSON.` +
        (preview.startsWith("<!DOCTYPE") || preview.startsWith("<html")
          ? " The request likely reached the frontend HTML app or an HTML error page instead of FastAPI."
          : "")
    );
  }

  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    method: "GET",
    headers: buildHeaders(),
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Health request failed: ${response.status}`);
  }

  return readJsonResponse<HealthResponse>(response, "Health request");
}

export async function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(payload),
    cache: "no-store"
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Chat request failed: ${response.status}`);
  }

  return readJsonResponse<ChatResponse>(response, "Chat request");
}
