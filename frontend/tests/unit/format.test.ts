import { expect, it } from "vitest";
import { weightedRisk } from "../../src/features/card/weights";
import { toCsv } from "../../src/lib/format/csv";
import { formatAgo, formatDate } from "../../src/lib/format/date";
import { formatNumber } from "../../src/lib/format/number";
import { fill } from "../../src/lib/format/template";

it("formats numbers as hr-HR", () => {
  expect(formatNumber(3871833)).toBe("3.871.833");
  expect(formatNumber(0.5, 1)).toBe("0,5");
});

it("fills templates and leaves unknown names", () => {
  expect(fill("{a} i {b}", { a: 1 })).toBe("1 i {b}");
});

it("formats recent times relatively", () => {
  const now = Date.parse("2026-11-01T12:00:00Z");
  expect(formatAgo("2026-11-01T11:55:00Z", now)).toBe("prije 5 minuta");
  expect(formatAgo("2026-11-01T10:00:00Z", now)).toBe("prije 2 sata");
  expect(formatAgo("2026-10-20T10:00:00Z", now)).toBe("20. 10. 2026. u 12:00");
});

it("formats a calendar date", () => {
  expect(formatDate("2026-11-01")).toBe("1. 11. 2026.");
});

it("quotes CSV cells that need it", () => {
  expect(
    toCsv(
      ["a", "b"],
      [
        ["x;y", null],
        ['q"', 1],
      ],
    ),
  ).toBe('a;b\r\n"x;y";\r\n"q""";1');
});

it("recalculates risk with user weights and skips missing hazards", () => {
  const risks = { flood: 1, heat: 0, fire: null, air: 0 };
  const equal = { flood: 25, heat: 25, fire: 25, air: 25 };
  expect(weightedRisk(risks, equal)).toBeCloseTo(1 / 3);
  expect(weightedRisk(risks, { flood: 0, heat: 50, fire: 50, air: 0 })).toBe(0);
  expect(
    weightedRisk({ flood: null, heat: null, fire: null, air: null }, equal),
  ).toBeNull();
});
