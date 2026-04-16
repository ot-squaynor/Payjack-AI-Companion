import { expect, test } from "@playwright/test";


const apiBaseUrl = "http://127.0.0.1:8000";


test("shows healthy backend status and completes a chat flow", async ({ page }) => {
  await page.route(`${apiBaseUrl}/health`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        environment: "local"
      })
    });
  });

  await page.route(`${apiBaseUrl}/chat`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "req-e2e-1",
        session_id: "session-e2e-1",
        route: "tool",
        answer: "Here are your last 2 transactions.",
        tool_traces: [],
        citations: [],
        refusal: null,
        debug: {}
      })
    });
  });

  await page.goto("/");

  await expect(page.locator(".status-badge")).toContainText("ok");
  await page.getByPlaceholder("Ask about your transactions, spending, or Payjack features...").fill("Show my last 2 transactions");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Here are your last 2 transactions.")).toBeVisible();
});


test("renders a grounded documentation answer with citations", async ({ page }) => {
  await page.route(`${apiBaseUrl}/health`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        environment: "local"
      })
    });
  });

  await page.route(`${apiBaseUrl}/chat`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "req-e2e-doc-1",
        session_id: "session-e2e-doc-1",
        route: "rag",
        answer: "Based on Payjack documentation, fee explanations are available in the help center.",
        tool_traces: [],
        citations: [
          {
            doc_id: "fees_policy",
            title: "Fees Policy",
            snippet: "Payjack fee explanations are available in the help center.",
            score: 0.92,
            metadata: { type: "policy" }
          }
        ],
        refusal: null,
        debug: {
          grounding_mode: "rag"
        }
      })
    });
  });

  await page.goto("/");
  await page.getByPlaceholder("Ask about your transactions, spending, or Payjack features...").fill("What is the Payjack fee policy?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText(/Based on Payjack documentation/)).toBeVisible();
  await expect(page.getByText("Citations")).toBeVisible();
  await expect(page.getByText("Fees Policy")).toBeVisible();
});


test("renders a base fallback answer without citations", async ({ page }) => {
  await page.route(`${apiBaseUrl}/health`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        environment: "local"
      })
    });
  });

  await page.route(`${apiBaseUrl}/chat`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "req-e2e-doc-2",
        session_id: "session-e2e-doc-2",
        route: "rag",
        answer: "I could not verify that in reliable Payjack documentation.",
        tool_traces: [],
        citations: [],
        refusal: null,
        debug: {
          grounding_mode: "base",
          retrieval_reason: "no_candidate_chunks"
        }
      })
    });
  });

  await page.goto("/");
  await page.getByPlaceholder("Ask about your transactions, spending, or Payjack features...").fill("What are the Payjack features?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText(/could not verify/i)).toBeVisible();
  await expect(page.getByText("Citations")).toHaveCount(0);
});


test("shows backend unavailable when the health check fails", async ({ page }) => {
  await page.route(`${apiBaseUrl}/health`, async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "text/plain",
      body: "Backend unavailable"
    });
  });

  await page.goto("/");

  await expect(page.locator(".status-badge")).toContainText("Backend unavailable");
  await expect(page.getByText("Health request failed: 503")).toBeVisible();
});


test("renders a refusal response for disallowed actions", async ({ page }) => {
  await page.route(`${apiBaseUrl}/health`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        environment: "local"
      })
    });
  });

  await page.route(`${apiBaseUrl}/chat`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "req-e2e-2",
        session_id: "session-e2e-2",
        route: "refuse",
        answer: "I can explain account restrictions, but I cannot move money.",
        tool_traces: [],
        citations: [],
        refusal: {
          category: "disallowed_action",
          message: "Payjack cannot execute money movement."
        },
        debug: {}
      })
    });
  });

  await page.goto("/");
  await page.getByPlaceholder("Ask about your transactions, spending, or Payjack features...").fill("Send money to another account");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Refusal")).toBeVisible();
  await expect(page.getByText(/Payjack cannot execute money movement/)).toBeVisible();
});
