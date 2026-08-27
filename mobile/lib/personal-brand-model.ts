export type RelationshipPlan = { id: string; person: string; value: string; nextStep: string };
export type DraftRevision = { id: string; body: string; savedAt: string };
export type PostDraft = { id: string; title: string; body: string; status: "review" | "approved"; createdAt: string; revisions: DraftRevision[] };
export type PersonalBrandState = { audience: string; promise: string; proof: string; topics: string; goal: string; headline: string; about: string; relationships: RelationshipPlan[]; routineCompleted: string[]; postDrafts: PostDraft[] };
export type ProfileVariant = { id: string; goal: string; headline: string; about: string; description: string };

export const emptyPersonalBrand: PersonalBrandState = { audience: "", promise: "", proof: "", topics: "", goal: "", headline: "", about: "", relationships: [], routineCompleted: [], postDrafts: [] };

const audienceFor = (value: PersonalBrandState) => value.audience.trim() || "the people you want to help";
const promiseFor = (value: PersonalBrandState) => value.promise.trim() || "make a meaningful professional change";
const proofFor = (value: PersonalBrandState) => value.proof.trim() || "hands-on experience and useful lessons";

export function profileChecks(value: PersonalBrandState) {
  return [{ label: "Headline explains your expertise", done: Boolean(value.headline.trim()) }, { label: "About connects mission, motivation, and skills", done: Boolean(value.about.trim()) }, { label: "Positioning identifies a best-fit audience", done: Boolean(value.audience.trim() && value.promise.trim()) }, { label: "Proof points make the promise credible", done: Boolean(value.proof.trim()) }];
}
export function thoughtLeadershipPrompts(value: PersonalBrandState) {
  const topics = value.topics.split(",").map((topic) => topic.trim()).filter(Boolean); const audience = audienceFor(value); const topic = topics[0] || "a customer problem you understand"; return [{ title: `The mistake ${audience} make with ${topic}`, type: "Useful point of view" }, { title: `A practical three-step approach to ${topic}`, type: "Teach a repeatable method" }, { title: `What I changed my mind about in ${topic}`, type: "Personal learning story" }];
}
export function profileVariants(value: PersonalBrandState): ProfileVariant[] {
  const audience = audienceFor(value); const promise = promiseFor(value); const proof = proofFor(value);
  return [
    { id: "career", goal: "Career opportunity", headline: `Helping ${audience} ${promise}`, about: `I am exploring opportunities where I can help ${audience} ${promise}. My perspective is grounded in ${proof}. I share practical lessons and welcome conversations about the work.`, description: "Use when you want recruiters and peers to understand the work you want to do next." },
    { id: "consulting", goal: "Consulting or services", headline: `I help ${audience} ${promise}`, about: `I work with ${audience} who want to ${promise}. My approach is informed by ${proof}. I share clear, useful ideas so people can decide whether my perspective is relevant to their work.`, description: "Use when you want to explain a service without sounding promotional." },
    { id: "founder", goal: "Founder or operator", headline: `Building practical systems that help ${audience} ${promise}`, about: `I am building and learning in public around one goal: helping ${audience} ${promise}. I draw on ${proof} and share the decisions, experiments, and lessons that may be useful to other operators.`, description: "Use when your company-building perspective is the central story." },
    { id: "expert", goal: "Recognized practitioner", headline: `Practitioner in work that helps ${audience} ${promise}`, about: `I study and practice the work behind ${promise} for ${audience}. My perspective comes from ${proof}. I write to make complex decisions clearer, with practical examples rather than broad claims.`, description: "Use when you are building durable professional credibility through useful teaching." },
  ];
}
export const weeklyVisibilityRoutine = [
  { id: "listen", day: "Monday", title: "Listen for the real questions", detail: "Save two questions or observations from your field. Do not post yet.", minutes: "10 min" },
  { id: "contribute", day: "Tuesday", title: "Add one useful comment", detail: "Contribute a specific lesson or resource to a conversation you genuinely understand.", minutes: "10 min" },
  { id: "draft", day: "Wednesday", title: "Draft one useful post", detail: "Turn a lived experience into one observation, one lesson, and one question.", minutes: "20 min" },
  { id: "review", day: "Thursday", title: "Review for accuracy and tone", detail: "Move the draft through your own approval queue before any external publishing.", minutes: "10 min" },
  { id: "followup", day: "Friday", title: "Build one real relationship", detail: "Plan a thoughtful follow-up or resource share. Never automate the message.", minutes: "10 min" },
];
export function personalBrandScore(value: PersonalBrandState) {
  const profile = profileChecks(value).filter((item) => item.done).length;
  const routine = Math.min(value.routineCompleted.length, weeklyVisibilityRoutine.length);
  const drafts = value.postDrafts.length;
  const approved = value.postDrafts.filter((draft) => draft.status === "approved").length;
  const relationships = value.relationships.length;
  const points = profile * 10 + routine * 6 + Math.min(drafts, 3) * 5 + Math.min(approved, 2) * 5 + Math.min(relationships, 3) * 5;
  return { points: Math.min(points, 100), profile, routine, drafts, approved, relationships };
}
export function reviseDraft(draft: PostDraft, body: string): PostDraft {
  if (body.trim() === draft.body.trim()) return draft;
  return { ...draft, body, revisions: [{ id: `${Date.now()}`, body: draft.body, savedAt: new Date().toISOString() }, ...draft.revisions] };
}
export function draftFromPrompt(title: string, type: string, value: PersonalBrandState): PostDraft {
  return { id: `${Date.now()}`, title, body: `Opening observation: ${title}.\n\nWhat I have seen: ${proofFor(value)}.\n\nPractical lesson: ${promiseFor(value)}.\n\nQuestion for peers: What has worked in your context?`, status: "review", createdAt: new Date().toISOString(), revisions: [] };
}
