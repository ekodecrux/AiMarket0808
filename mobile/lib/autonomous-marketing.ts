export type Framework = { id: string; title: string; plain: string; outcome: string; stages: string[]; guardrail: string };
export const frameworks: Framework[] = [
  { id: "positioning", title: "Positioning clarity", plain: "Make it obvious who the offer is for and why they should choose it.", outcome: "A focused message for every channel.", stages: ["Best-fit customer", "Problem", "Promise", "Proof"], guardrail: "Use approved claims and real customer evidence." },
  { id: "stp", title: "Audience focus", plain: "Choose one customer group before trying to speak to everyone.", outcome: "A target segment and a clear priority.", stages: ["Segment", "Choose", "Describe", "Validate"], guardrail: "Do not infer sensitive customer traits." },
  { id: "race", title: "RACE growth loop", plain: "Reach people, invite action, convert interest, and retain customers.", outcome: "A channel-by-channel operating plan.", stages: ["Reach", "Act", "Convert", "Engage"], guardrail: "Use measurable events at each stage." },
  { id: "funnel", title: "AARRR funnel", plain: "Track acquisition, activation, retention, referral, and revenue.", outcome: "A simple view of where growth is leaking.", stages: ["Acquire", "Activate", "Retain", "Refer", "Revenue"], guardrail: "Prioritize the weakest verified stage, not vanity metrics." },
  { id: "content", title: "Content engine", plain: "Turn one customer problem into useful posts, search content, and follow-up assets.", outcome: "A repeatable content calendar.", stages: ["Question", "Pillar", "Channel", "Measure"], guardrail: "Reuse approved source knowledge before generating copy." },
  { id: "experiment", title: "30-day experiment", plain: "Run a small, controlled growth test before scaling spend.", outcome: "A documented decision to scale, refine, or stop.", stages: ["Hypothesis", "Budget cap", "Measure", "Decide"], guardrail: "Keep spend caps and approval thresholds in policy." },
  { id: "budget", title: "Budget discipline", plain: "Protect cash by testing small, measuring incrementality, and moving only proven spend.", outcome: "A governed budget recommendation, not a promise.", stages: ["Baseline", "Test", "Confidence", "Approve"], guardrail: "No automatic budget move without confidence and human approval." },
];

export type PlatformCard = { id: string; title: string; channel: string; purpose: string; scopes: string[]; color: string; icon: string };
export const platforms: PlatformCard[] = [
  { id: "google-ads", title: "Google Ads", channel: "Paid search", purpose: "Read campaign performance and prepare keyword, bid, and budget recommendations.", scopes: ["View campaigns", "Read performance", "Draft changes"], color: "#4285F4", icon: "ads-click" },
  { id: "meta-ads", title: "Meta Ads", channel: "Paid social", purpose: "Bring Meta campaign signals into your operating view and draft optimizations.", scopes: ["View accounts", "Read insights", "Draft changes"], color: "#1877F2", icon: "campaign" },
  { id: "linkedin", title: "LinkedIn", channel: "Professional social", purpose: "Organize B2B content, audience activity, and approved publishing workflows.", scopes: ["Manage pages", "Read analytics", "Draft posts"], color: "#0A66C2", icon: "groups" },
  { id: "instagram", title: "Instagram", channel: "Social content", purpose: "Plan approved content, monitor reach, and keep brand activity in one workspace.", scopes: ["Manage account", "Read insights", "Draft posts"], color: "#C13584", icon: "photo-camera" },
  { id: "facebook", title: "Facebook", channel: "Community", purpose: "Coordinate page activity, paid social evidence, and response planning.", scopes: ["Manage page", "Read insights", "Draft posts"], color: "#1877F2", icon: "thumb-up" },
  { id: "youtube", title: "YouTube", channel: "Video", purpose: "Track video reach and reuse customer questions for future content.", scopes: ["Read channel", "Read analytics", "Draft metadata"], color: "#FF0000", icon: "play-circle-filled" },
];

export const knowledgePrinciples = [
  "Search approved sources and saved learning before generating a new answer.",
  "Reuse verified frameworks, brand claims, and channel decisions when the situation matches.",
  "Call an AI model only when evidence conflicts, a new synthesis is needed, or content must be created.",
  "Show evidence, confidence, budget cap, and required approval before an action can affect spend.",
];
