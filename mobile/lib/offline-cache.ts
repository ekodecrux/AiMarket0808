import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";

const prefix = "aimarket.nexus.cache.v1:";
function key(url: string) { return `${prefix}${url}`; }
function webStore() { return typeof localStorage === "undefined" ? null : localStorage; }

export async function cacheResponse<T>(url: string, data: T) {
  const record = JSON.stringify({ data, storedAt: Date.now() });
  if (Platform.OS === "web") { webStore()?.setItem(key(url), record); return; }
  await AsyncStorage.setItem(key(url), record);
}
export async function cachedResponse<T>(url: string): Promise<{ data: T; storedAt: number } | null> {
  const raw = Platform.OS === "web" ? webStore()?.getItem(key(url)) : await AsyncStorage.getItem(key(url));
  if (!raw) return null;
  try { return JSON.parse(raw) as { data: T; storedAt: number }; } catch { return null; }
}
