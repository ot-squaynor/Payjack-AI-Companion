import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";


describe("frontend API client", () => {
  beforeEach(() => {
    vi.resetModules();
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    process.env.NEXT_PUBLIC_DEFAULT_USER_ID = "dev-user";
    process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID = "dev-tenant";
    process.env.NEXT_PUBLIC_DEFAULT_ACCOUNT_IDS = "acc-001";
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.NEXT_PUBLIC_DEFAULT_USER_ID;
    delete process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID;
    delete process.env.NEXT_PUBLIC_DEFAULT_ACCOUNT_IDS;
    vi.unstubAllEnvs();
  });

  it("returns backend health when the request succeeds", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", environment: "local" }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { getHealth } = await import("@/lib/api");
    const response = await getHealth();

    expect(response).toEqual({ status: "ok", environment: "local" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/health",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );
  });

  it("defaults to the CloudFront API prefix when no API base URL is configured", async () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", environment: "dev" }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { getHealth } = await import("@/lib/api");
    await getHealth();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );
  });

  it("defaults to the local FastAPI server during frontend development", async () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    vi.stubEnv("NODE_ENV", "development");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", environment: "local" }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { getHealth } = await import("@/lib/api");
    await getHealth();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/health",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );
  });

  it("returns chat responses when the request succeeds", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          request_id: "req-1",
          session_id: "session-1",
          route: "tool",
          answer: "Here are your last two transactions.",
          tool_traces: [],
          citations: [],
          refusal: null,
          debug: {}
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const { sendChat } = await import("@/lib/api");
    const response = await sendChat({ message: "Show my last 2 transactions" });

    expect(response.answer).toContain("last two transactions");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/chat",
      expect.objectContaining({
        method: "POST",
        cache: "no-store"
      })
    );
  });

  it("raises a useful error for non-200 chat responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("Backend failure", { status: 500 }))
    );

    const { sendChat } = await import("@/lib/api");

    await expect(sendChat({ message: "Show my last 2 transactions" })).rejects.toThrow("Backend failure");
  });

  it("raises a useful error when chat returns frontend HTML", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<!DOCTYPE html><html><body>Not the API</body></html>", {
          status: 200,
          headers: { "Content-Type": "text/html" }
        })
      )
    );

    const { sendChat } = await import("@/lib/api");

    await expect(sendChat({ message: "Show my last 2 transactions" })).rejects.toThrow(
      "The request likely reached the frontend HTML app or an HTML error page instead of FastAPI."
    );
  });

  it("raises the original network error when fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Failed to fetch")));

    const { getHealth } = await import("@/lib/api");

    await expect(getHealth()).rejects.toThrow("Failed to fetch");
  });

  it("invokes /tools/invoke with correct body and auth headers", async () => {
    const mockResult = {
      request_id: "req-tool-1",
      tool: "balances",
      arguments: { account_ids: ["acc-001"] },
      payload: { records: [], warnings: [] },
      warnings: [],
      artifact_version: "v1",
      latency_ms: 8.5
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockResult), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { invokeToolDirect } = await import("@/lib/api");
    const result = await invokeToolDirect({ tool: "balances", arguments: {} });

    expect(result.tool).toBe("balances");
    expect(result.request_id).toBe("req-tool-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/tools/invoke",
      expect.objectContaining({
        method: "POST",
        cache: "no-store"
      })
    );
    const callArgs = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(callArgs.body as string);
    expect(body).toEqual({ tool: "balances", arguments: {} });
    const headers = callArgs.headers as Record<string, string>;
    expect(headers["x-payjack-user-id"]).toBe("dev-user");
    expect(headers["x-payjack-account-ids"]).toBe("acc-001");
  });

  it("returns parsed ToolInvokeResponse on 200", async () => {
    const mockResult = {
      request_id: "req-tool-2",
      tool: "transaction_lookup",
      arguments: { limit: 5 },
      payload: { records: [], match_count: 0, applied_filters: {}, warnings: [] },
      warnings: [],
      artifact_version: null,
      latency_ms: 3.2
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(mockResult), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
    );

    const { invokeToolDirect } = await import("@/lib/api");
    const result = await invokeToolDirect({ tool: "transaction_lookup", arguments: { limit: 5 } });

    expect(result.tool).toBe("transaction_lookup");
    expect(result.latency_ms).toBe(3.2);
    expect(result.artifact_version).toBeNull();
  });

  it("throws on non-200 tool invocation response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("Tool not found", { status: 422 }))
    );

    const { invokeToolDirect } = await import("@/lib/api");

    await expect(
      invokeToolDirect({ tool: "transaction_lookup", arguments: {} })
    ).rejects.toThrow("Tool not found");
  });

  it("throws on non-JSON content-type from tool endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<!DOCTYPE html><html></html>", {
          status: 200,
          headers: { "Content-Type": "text/html" }
        })
      )
    );

    const { invokeToolDirect } = await import("@/lib/api");

    await expect(
      invokeToolDirect({ tool: "balances", arguments: {} })
    ).rejects.toThrow("Tool invocation returned");
  });
});
