import { describe, expect, it } from "vitest";
import { draftFromPrompt, emptyPersonalBrand, personalBrandScore, profileChecks, profileVariants, reviseDraft, thoughtLeadershipPrompts, weeklyVisibilityRoutine } from "../lib/personal-brand-model";

describe("Personal Brand workspace helpers", () => {
  it("reports concrete LinkedIn-first readiness only after the relevant profile inputs are present", () => {
    expect(profileChecks(emptyPersonalBrand).filter((item) => item.done)).toHaveLength(0);
    const complete = { ...emptyPersonalBrand, audience: "B2B founders", promise: "clarity", proof: "operator experience", headline: "B2B growth operator", about: "I help founders make better marketing decisions." };
    expect(profileChecks(complete).filter((item) => item.done)).toHaveLength(4);
  });

  it("creates reusable, experience-led thought-leadership prompts without automated publishing", () => {
    const prompts = thoughtLeadershipPrompts({ ...emptyPersonalBrand, audience: "SaaS founders", topics: "CRM adoption, B2B growth" });
    expect(prompts).toHaveLength(3);
    expect(prompts[0].title).toContain("SaaS founders");
    expect(prompts[0].title).toContain("CRM adoption");
    expect(prompts.every((prompt) => prompt.title.length > 10)).toBe(true);
  });

  it("creates goal-specific profile variants from approved positioning rather than generic claims", () => {
    const variants = profileVariants({ ...emptyPersonalBrand, audience: "B2B founders", promise: "build a focused growth system", proof: "leading product launches" });
    expect(variants).toHaveLength(4);
    expect(variants[0].headline).toContain("B2B founders");
    expect(variants.some((variant) => variant.goal === "Consulting or services")).toBe(true);
  });

  it("keeps visibility and publishing actions user-managed", () => {
    expect(weeklyVisibilityRoutine).toHaveLength(5);
    expect(weeklyVisibilityRoutine.map((item) => item.day)).toEqual(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]);
    const draft = draftFromPrompt("A practical lesson", "Useful point of view", { ...emptyPersonalBrand, proof: "real CRM implementation work", promise: "help teams decide clearly" });
    expect(draft.status).toBe("review");
    expect(draft.body).toContain("real CRM implementation work");
  });

  it("keeps an editable post revision locally before replacing the active draft text", () => {
    const draft = draftFromPrompt("A practical lesson", "Useful point of view", emptyPersonalBrand);
    const revised = reviseDraft(draft, "A revised, more specific practical lesson.");
    expect(revised.body).toContain("revised");
    expect(revised.revisions).toHaveLength(1);
    expect(revised.revisions[0].body).toBe(draft.body);
  });

  it("calculates a transparent activity score rather than predicting social reach", () => {
    const draft = { ...draftFromPrompt("A lesson", "Point of view", emptyPersonalBrand), status: "approved" as const };
    const score = personalBrandScore({ ...emptyPersonalBrand, audience: "SaaS founders", promise: "build clarity", proof: "operating experience", headline: "Growth operator", about: "Useful profile", routineCompleted: ["listen", "draft"], postDrafts: [draft], relationships: [{ id: "r1", person: "Peer", value: "Share resource", nextStep: "Write note" }] });
    expect(score.profile).toBe(4);
    expect(score.routine).toBe(2);
    expect(score.approved).toBe(1);
    expect(score.points).toBeGreaterThan(0);
    expect(score.points).toBeLessThanOrEqual(100);
  });
});
