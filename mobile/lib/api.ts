import axios, { AxiosError } from "axios";
import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import { cachedResponse, cacheResponse } from "@/lib/offline-cache";
import { cachedKnowledge, saveKnowledge } from "@/lib/knowledge-cache";

const tokenKey = "aimarket.nexus.token";
export const API_BASE_URL = "https://aimarket.expertaitutor.com/api";
const client = axios.create({ baseURL: API_BASE_URL, timeout: 30000, withCredentials: true });

export type User = { _id?: string; id?: string; name?: string; email: string; role?: string; tenant_id?: string; client_id?: string; must_change_password?: boolean };
export type Campaign = { _id: string; name: string; channel: string; objective: string; budget: number; status: string; impressions?: number; clicks?: number; conversions?: number; revenue?: number; roas?: number; ctr?: number };
export type Lead = { _id: string; name: string; email: string; company: string; role?: string; source?: string; stage?: string; ai_score?: number; score?: number };
export type Profile = { company_name?: string; description?: string; industry?: string; website?: string; country?: string; currency?: string; autopilot?: boolean; daily_proposals?: number };
export type PaymentGateway = { provider: "razorpay" | "stripe" | "paytm"; label: string; checkout_ready: boolean; webhook_ready: boolean; plans_configured: boolean; mode: "ready" | "configuration_pending" };
export type PaymentRecord = { id: string; provider: string; plan_name?: string; plan_code?: string; amount_minor?: number; currency?: string; status: string; created_at?: string };
export type PaymentPlan = { code: string; name: string; amount_minor: number; currency: string };
export type PaymentCheckout = { payment_id: string; provider: string; status: string; checkout_url?: string | null };
export type AuthProviderReadiness = { google: { available: boolean; flow: string; required_configuration: string[]; web_client_id: string }; phone_otp: { available: boolean; flow: string; requires_sms_consent: boolean; required_configuration: string[] } };

export const tokenStore = {
  async get() { return Platform.OS === "web" ? (typeof sessionStorage === "undefined" ? null : sessionStorage.getItem(tokenKey)) : SecureStore.getItemAsync(tokenKey); },
  async set(value: string) { if (Platform.OS === "web") { sessionStorage.setItem(tokenKey, value); return; } await SecureStore.setItemAsync(tokenKey, value); },
  async clear() { if (Platform.OS === "web") { sessionStorage.removeItem(tokenKey); return; } await SecureStore.deleteItemAsync(tokenKey); },
};
client.interceptors.request.use(async (config) => { const token = await tokenStore.get(); if (token) config.headers.Authorization = `Bearer ${token}`; return config; });
const sleep = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const get = async <T,>(url: string) => {
  let lastError: unknown;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try { const data = (await client.get<T>(url)).data; void cacheResponse(url, data); return data; }
    catch (error) { lastError = error; const axiosError = error as AxiosError; if (axiosError.response || attempt === 2) break; await sleep(400 * (attempt + 1)); }
  }
  const cached = await cachedResponse<T>(url);
  if (cached) return cached.data;
  throw lastError;
};
const post = async <T,>(url: string, data?: unknown) => (await client.post<T>(url, data)).data;
const put = async <T,>(url: string, data?: unknown) => (await client.put<T>(url, data)).data;
const patch = async <T,>(url: string, data?: unknown) => (await client.patch<T>(url, data)).data;
export const apiError = (error: unknown, fallback = "Request failed.") => { const e = error as AxiosError<{ detail?: string; message?: string }>; return e.response?.data?.detail ?? e.response?.data?.message ?? fallback; };
export const api = {
  auth: {
    login: (email: string, password: string) => post<{ user: User; token: string }>("/auth/login", { email, password }),
    register: (data: { name: string; email: string; password?: string; phone?: string; use_generated_password: boolean }) => post<{ user: User; token: string; temporary_password_emailed: boolean }>("/auth/register", data),
    requestPasswordReset: (email: string, delivery: "link" | "temporary" = "link") => post<{ message: string }>("/auth/password/reset/request", { email, delivery }),
    confirmPasswordReset: (token: string, password: string) => post<{ message: string }>("/auth/password/reset/confirm", { token, password }),
    changePassword: (current_password: string, new_password: string) => post<{ message: string }>("/auth/password/change", { current_password, new_password }),
    providers: () => get<AuthProviderReadiness>("/auth/providers"),
    exchangeGoogleCode: (code: string) => post<{ user: User; token: string }>("/auth/google/exchange", { code }),
    requestPhoneOtp: (phone: string, intent: "login" | "signup", name: string, consent: boolean) => post<{ message: string; sent_to: string }>("/auth/otp/phone/request", { phone, intent, name, consent }),
    verifyPhoneOtp: (phone: string, code: string, intent: "login" | "signup") => post<{ user: User; token: string }>("/auth/otp/phone/verify", { phone, code, intent }),
    me: () => get<User>("/auth/me"), logout: () => post("/auth/logout"),
  },
  overview: () => get<Record<string, unknown>>("/analytics/overview"),
  profile: { get: () => get<Profile>("/profile"), save: (data: Profile) => put<Profile>("/profile", data) },
  campaigns: { list: () => get<Campaign[]>("/campaigns"), create: (data: Pick<Campaign, "name" | "channel" | "objective" | "budget">) => post<Campaign>("/campaigns", data), metrics: (id: string, data: Record<string, number>) => patch<Campaign>(`/campaigns/${id}/metrics`, data), toggle: (id: string) => patch<Campaign>(`/campaigns/${id}/toggle`) },
  strategy: { list: () => get<Record<string, unknown>[]>("/strategy"), generate: (data: Record<string, string>) => post<Record<string, unknown>>("/strategy/generate", data) },
  content: { list: () => get<Record<string, unknown>[]>("/content"), generate: (data: Record<string, string>) => post<Record<string, unknown>>("/content/generate", data) },
  seo: { audit: (url: string) => post<Record<string, unknown>>("/seo/audit", { url }), keywords: (seeds: string[], industry: string) => post<Record<string, unknown>>("/seo/keywords", { seeds, industry }), brief: (keywords: string[], industry: string) => post<Record<string, unknown>>("/seo/briefs", { keywords, industry }) },
  leads: { list: () => get<Lead[]>("/leads"), score: (id: string) => post<Lead>(`/leads/${id}/score-ai`) },
  revenue: { list: () => get<Record<string, unknown>[]>("/revenue"), report: () => get<Record<string, unknown>>("/attribution/report") },
  competitors: { list: () => get<Record<string, unknown>[]>("/competitors"), create: (name: string, url: string) => post<Record<string, unknown>>("/competitors", { name, url }) },
  brain: { sources: () => get<Record<string, unknown>[]>("/brain/sources"), query: async (query: string) => { const cached = await cachedKnowledge<Record<string, unknown>>(query); if (cached) return { ...cached, _nexus_reused: true }; const answer = await post<Record<string, unknown>>("/brain/query", { query, top_k: 5, with_answer: true }); void saveKnowledge(query, answer); return { ...answer, _nexus_reused: false }; } },
  agents: { schedules: () => get<Record<string, unknown>[]>("/agents/schedules"), run: (id: string) => post(`/agents/schedules/${id}/run`), toggle: (id: string, enabled: boolean) => post(`/agents/schedules/${id}/toggle`, { enabled }) },
  missions: { list: () => get<Record<string, unknown>[]>("/missions"), create: (data: Record<string, unknown>) => post("/missions", data) },
  learning: { list: () => get<Record<string, unknown>[]>("/learning"), generate: () => post("/learning/generate") },
  policy: { get: () => get<Record<string, unknown>>("/policy"), set: (data: Record<string, unknown>) => post("/policy", data), kill: (active: boolean) => post("/policy/kill-switch", { active }) },
  notifications: { register: (expo_push_token: string) => post("/notifications/devices", { expo_push_token, platform: Platform.OS }) },
  connections: { oauthStart: (provider: string, data: { client_id?: string; connection_role: "customer" | "owner_managed"; authorization_confirmed: boolean }) => post<{ authorization_url: string }>(`/connections/oauth/${provider}/start`, data) },
  budget: { requestApproval: (data: { provider: string; current_daily_budget: number; proposed_daily_budget: number; rationale: string; evidence?: Record<string, unknown>; client_id?: string }) => post<Record<string, unknown>>("/budget/approval-requests", data), listApprovals: () => get<Record<string, unknown>[]>("/budget/approval-requests"), decideApproval: (id: string, decision: "approve" | "reject", note = "") => post<Record<string, unknown>>(`/budget/approval-requests/${id}/decision`, { decision, note }) },
  payments: { gateways: () => get<PaymentGateway[]>("/payments/gateways"), plans: () => get<PaymentPlan[]>("/payments/plans"), history: () => get<PaymentRecord[]>("/payments"), checkout: (provider: PaymentGateway["provider"], plan_code: string, client_id?: string) => post<PaymentCheckout>("/payments/checkout", { provider, plan_code, client_id }) },
};
