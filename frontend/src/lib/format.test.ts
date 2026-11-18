import { describe, expect, it } from "vitest";
import { fmtDuration, fmtNum, fmtPct, fmtRelative } from "./format";

describe("format helpers", () => {
  it("never invents a value for missing data", () => {
    expect(fmtNum(null)).toBe("—");
    expect(fmtPct(undefined)).toBe("—");
    expect(fmtDuration(null)).toBe("non mesurée");
    expect(fmtRelative(null)).toBe("jamais");
  });

  it("formats French numbers and percentages", () => {
    expect(fmtNum(52.4)).toBe("52,4");
    expect(fmtPct(0.234)).toBe("23,4 %");
  });

  it("scales durations to a readable unit", () => {
    expect(fmtDuration(120)).toBe("120 ms");
    expect(fmtDuration(81_800)).toBe("1 min 22 s");
    expect(fmtDuration(2 * 3600_000 + 5 * 60_000)).toBe("2 h 5 min");
    expect(fmtDuration(295_943_000)).toBe("3 j 10 h");
  });

  it("produces relative times", () => {
    const now = Date.parse("2026-11-16T12:00:00Z");
    expect(fmtRelative("2026-11-16T11:00:00Z", now)).toBe("il y a 1 heure");
    expect(fmtRelative("2026-11-14T12:00:00Z", now)).toBe("avant-hier");
  });
});
