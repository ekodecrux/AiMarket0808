import { describe, expect, it } from "vitest";
import { currencyForLocation, entityId, safeNumber } from "../lib/market-utils";

describe("mobile marketing workflow helpers", () => {
  it("maps supported business locations to the expected operating currency", () => {
    expect(currencyForLocation("India")).toBe("INR");
    expect(currencyForLocation("United Kingdom")).toBe("GBP");
    expect(currencyForLocation("Germany")).toBe("EUR");
  });

  it("preserves a supplied currency for unlisted locations and normalizes API values", () => {
    expect(currencyForLocation("Kenya", "KES")).toBe("KES");
    expect(entityId({ _id: "campaign-1" })).toBe("campaign-1");
    expect(entityId({ id: 42 })).toBe("42");
    expect(safeNumber("84.75")).toBe(84.75);
    expect(safeNumber("-1")).toBe(0);
    expect(safeNumber("invalid")).toBe(0);
  });
});
