import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";
import { emptyPersonalBrand } from "@/lib/personal-brand-model";
export { draftFromPrompt, emptyPersonalBrand, personalBrandScore, profileChecks, profileVariants, reviseDraft, thoughtLeadershipPrompts, weeklyVisibilityRoutine } from "@/lib/personal-brand-model";
export type { PersonalBrandState, PostDraft } from "@/lib/personal-brand-model";

export type PersonalBrand = typeof emptyPersonalBrand;
const key = "aimarket.nexus.personal-brand.v1";
const readWeb = () => typeof localStorage === "undefined" ? null : localStorage.getItem(key);
export async function loadPersonalBrand(): Promise<PersonalBrand> { const raw = Platform.OS === "web" ? readWeb() : await AsyncStorage.getItem(key); if (!raw) return emptyPersonalBrand; try { const stored = JSON.parse(raw) as Partial<PersonalBrand>; return { ...emptyPersonalBrand, ...stored, postDrafts: (stored.postDrafts ?? []).map((draft) => ({ ...draft, revisions: draft.revisions ?? [] })) }; } catch { return emptyPersonalBrand; } }
export async function savePersonalBrand(value: PersonalBrand) { const raw = JSON.stringify(value); if (Platform.OS === "web") { if (typeof localStorage !== "undefined") localStorage.setItem(key, raw); return; } await AsyncStorage.setItem(key, raw); }
