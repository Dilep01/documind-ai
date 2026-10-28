import { afterEach, describe, expect, it, vi } from "vitest";
import { api, setCsrf, money } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
  setCsrf("");
});
describe("authenticated API boundary", () => {
  it("preserves cents when displaying large decimal amounts", () => {
    expect(money("9999999999999999.99")).toBe("₹9,99,99,99,99,99,99,999.99");
    expect(money("2950.00")).toBe("₹2,950.00");
    expect(money(null)).toBe("—");
  });
  it("includes the session CSRF token and keeps credentials on the same origin", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"version":2}', {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    setCsrf("session-specific-token");
    expect(
      await api("/invoices/example", { method: "PATCH", body: "{}" }),
    ).toEqual({ version: 2 });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/invoices/example");
    expect(options.credentials).toBe("same-origin");
    expect(options.headers.get("X-Documind-CSRF")).toBe(
      "session-specific-token",
    );
  });
  it("shows a stale-version server error instead of treating it as a successful save", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('{"detail":"A newer revision exists."}', {
          status: 409,
        }),
      ),
    );
    await expect(
      api("/invoices/example", { method: "PATCH", body: "{}" }),
    ).rejects.toThrow("A newer revision exists.");
  });
  it("keeps multipart boundaries under browser control", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response('{"document_id":"demo"}', { status: 202 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const form = new FormData();
    form.append("file", new Blob(["sample"]), "sample.pdf");
    await api("/documents", { method: "POST", body: form });
    expect(fetchMock.mock.calls[0][1].headers.has("Content-Type")).toBe(false);
  });
});
