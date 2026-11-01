import { expect, it } from "vitest";
import { formatDateTime } from "../../src/lib/format/date";

it("formats in hr-HR style and the Zagreb time zone", () => {
  expect(formatDateTime("2026-11-01T13:20:00Z")).toBe("1. 11. 2026. u 14:20");
});
