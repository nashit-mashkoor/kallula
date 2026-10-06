import { describe, expect, it } from "vitest";

import { apiUrl } from "./client";

describe("apiUrl", () => {
  it("joins the base url and path", () => {
    expect(apiUrl("/api/v1/session")).toMatch(/\/api\/v1\/session$/);
  });
});
