export type ConnectionRole = "customer" | "owner_managed";
export type ConnectionRequest = { id: string; platformId: string; role: ConnectionRole; clientName: string; authorized: boolean; requestedAt: string; status: "prepared" | "oauth_required" };
export function roleLabel(role: ConnectionRole) { return role === "owner_managed" ? "Owner-managed client" : "Customer self-service"; }
const oauthProviderIds: Record<string, "google_ads" | "meta_ads" | "linkedin"> = { "google-ads": "google_ads", "meta-ads": "meta_ads", linkedin: "linkedin" };
export function oauthProviderForPlatform(platformId: string) { return oauthProviderIds[platformId] ?? null; }
