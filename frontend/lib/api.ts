import type { ChatRequest, ChatResponse, HealthResponse } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

function buildHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "x-payjack-user-id": process.env.NEXT_PUBLIC_DEFAULT_USER_ID || "dev-user",
    "x-payjack-tenant-id": process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID || "dev-tenant",
    "x-payjack-account-ids": process.env.NEXT_PUBLIC_DEFAULT_ACCOUNT_IDS || ""
  };
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

  return response.json() as Promise<HealthResponse>;
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

  return response.json() as Promise<ChatResponse>;
}
