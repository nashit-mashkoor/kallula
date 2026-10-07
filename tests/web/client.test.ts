import { describe, expect, it } from "vitest";

import { apiUrl } from "../../apps/web/src/api/client";

describe("apiUrl", () => {
  it("returns same-origin paths by default", () => {
    expect(apiUrl("/api/v1/session")).toBe("/api/v1/session");
  });
});
