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

  it("raises the original network error when fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Failed to fetch")));

    const { getHealth } = await import("@/lib/api");

    await expect(getHealth()).rejects.toThrow("Failed to fetch");
  });
});
