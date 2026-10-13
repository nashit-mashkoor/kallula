import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiGet, apiUrl } from "../../apps/web/src/api/client";

describe("apiUrl", () => {
  it("returns same-origin paths by default", () => {
    expect(apiUrl("/api/v1/session")).toBe("/api/v1/session");
  });
});

describe("ApiError", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("carries the problem status and code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "PROJECT_EXECUTION_BUSY",
            detail: "Another Run of this Project is not finished.",
          }),
          {
            status: 409,
            headers: { "Content-Type": "application/problem+json" },
          },
        ),
      ),
    );

    const failure = apiGet("/api/v1/projects/p/runs");
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await failure.catch((error: ApiError) => {
      expect(error.status).toBe(409);
      expect(error.code).toBe("PROJECT_EXECUTION_BUSY");
    });
  });

  it("tolerates non-problem error bodies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("boom", { status: 500 })),
    );

    const failure = apiGet("/api/v1/projects/p/runs");
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await failure.catch((error: ApiError) => {
      expect(error.status).toBe(500);
      expect(error.code).toBeNull();
    });
  });
});
