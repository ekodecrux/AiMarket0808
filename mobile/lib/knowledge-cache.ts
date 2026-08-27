import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";

const PREFIX = "aimarket.nexus.knowledge.v1:";
const MAX_AGE = 1000 * 60 * 60 * 24 * 7;
const keyFor = (question: string) => `${PREFIX}${encodeURIComponent(question.trim().toLowerCase().replace(/\s+/g, " "))}`;
const readWeb = (key: string) => typeof localStorage === "undefined" ? null : localStorage.getItem(key);
const writeWeb = (key: string, value: string) => { if (typeof localStorage !== "undefined") localStorage.setItem(key, value); };

export async function cachedKnowledge<T>(question: string): Promise<T | null> {
  const key = keyFor(question); const raw = Platform.OS === "web" ? readWeb(key) : await AsyncStorage.getItem(key);
  if (!raw) return null;
  try { const value = JSON.parse(raw) as { savedAt: number; answer: T }; return Date.now() - value.savedAt < MAX_AGE ? value.answer : null; } catch { return null; }
}
export async function saveKnowledge<T>(question: string, answer: T) {
  const item = JSON.stringify({ savedAt: Date.now(), answer }); const key = keyFor(question);
  if (Platform.OS === "web") { writeWeb(key, item); return; }
  await AsyncStorage.setItem(key, item);
}
