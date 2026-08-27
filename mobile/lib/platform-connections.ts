import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";
import type { ConnectionRequest } from "@/lib/platform-connection-model";

export { oauthProviderForPlatform, roleLabel, type ConnectionRequest, type ConnectionRole } from "@/lib/platform-connection-model";

const KEY = "aimarket.nexus.platform-connections.v1";
const web = () => typeof localStorage === "undefined" ? null : localStorage;
export async function loadConnectionRequests(): Promise<ConnectionRequest[]> {
  const raw = Platform.OS === "web" ? web()?.getItem(KEY) : await AsyncStorage.getItem(KEY);
  if (!raw) return [];
  try { return JSON.parse(raw) as ConnectionRequest[]; } catch { return []; }
}
export async function saveConnectionRequests(records: ConnectionRequest[]) {
  const value = JSON.stringify(records); if (Platform.OS === "web") { web()?.setItem(KEY, value); return; } await AsyncStorage.setItem(KEY, value);
}
