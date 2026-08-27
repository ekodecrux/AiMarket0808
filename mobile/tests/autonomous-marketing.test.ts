import { describe, expect, it } from "vitest";
import { frameworks, knowledgePrinciples, platforms } from "../lib/autonomous-marketing";
import { oauthProviderForPlatform, roleLabel } from "../lib/platform-connection-model";
import type { ConnectionRequest } from "../lib/platform-connection-model";

describe("knowledge-first autonomous marketing model", () => {
  it("exposes practical framework choices with an outcome and a governance guardrail", () => {
    expect(frameworks.length).toBeGreaterThanOrEqual(7);
    frameworks.forEach((framework) => {
      expect(framework.stages.length).toBeGreaterThanOrEqual(4);
      expect(framework.outcome.length).toBeGreaterThan(8);
      expect(framework.guardrail.length).toBeGreaterThan(12);
    });
  });

  it("keeps knowledge reuse and provider consent as explicit first-class constraints", () => {
    expect(knowledgePrinciples.some((principle) => principle.includes("before generating"))).toBe(true);
    expect(platforms.map((platform) => platform.id)).toEqual(expect.arrayContaining(["google-ads", "meta-ads", "linkedin"]));
    expect(platforms.every((platform) => platform.scopes.length >= 3)).toBe(true);
  });

  it("distinguishes a customer’s own consent from an owner-managed client authorization", () => {
    const customer: ConnectionRequest = { id: "google-self", platformId: "google-ads", role: "customer", clientName: "My workspace", authorized: true, requestedAt: "2026-08-25T00:00:00.000Z", status: "oauth_required" };
    const managed: ConnectionRequest = { id: "meta-client", platformId: "meta-ads", role: "owner_managed", clientName: "Acme CRM", authorized: true, requestedAt: "2026-08-25T00:00:00.000Z", status: "oauth_required" };
    expect(roleLabel(customer.role)).toBe("Customer self-service");
    expect(roleLabel(managed.role)).toBe("Owner-managed client");
    expect(managed.authorized).toBe(true);
  });

  it("maps only configured display platforms to provider-safe OAuth route identifiers", () => {
    expect(oauthProviderForPlatform("google-ads")).toBe("google_ads");
    expect(oauthProviderForPlatform("meta-ads")).toBe("meta_ads");
    expect(oauthProviderForPlatform("linkedin")).toBe("linkedin");
    expect(oauthProviderForPlatform("instagram")).toBeNull();
  });
});
