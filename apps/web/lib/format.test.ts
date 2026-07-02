import { describe, expect, it } from "vitest";

import { formatCount } from "./format";

describe("formatCount", () => {
  it("formats dashboard counts without decimals", () => {
    expect(formatCount(1200)).toBe("1,200");
  });
});
