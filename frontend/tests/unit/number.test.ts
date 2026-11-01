import { describe, expect, it } from "vitest";

import { formatNumber } from "../../src/lib/format/number";

describe("formatNumber", () => {
  it("uses Croatian separators", () => {
    expect(formatNumber(3871833)).toBe("3.871.833");
    expect(formatNumber(2.5, 1)).toBe("2,5");
  });
});
