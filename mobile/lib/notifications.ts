import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

const TOKEN_KEY = "aimarket.nexus.expo-push-token";
const ENABLED_KEY = "aimarket.nexus.approval-alerts";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

async function setItem(key: string, value: string) {
  if (Platform.OS === "web") { if (typeof localStorage !== "undefined") localStorage.setItem(key, value); return; }
  await SecureStore.setItemAsync(key, value);
}
async function getItem(key: string) {
  if (Platform.OS === "web") return typeof localStorage === "undefined" ? null : localStorage.getItem(key);
  return SecureStore.getItemAsync(key);
}

export async function approvalAlertsEnabled() { return (await getItem(ENABLED_KEY)) === "true"; }
export async function cachedPushToken() { return getItem(TOKEN_KEY); }

export async function enableApprovalAlerts() {
  if (Platform.OS === "web") {
    await setItem(ENABLED_KEY, "true");
    return { enabled: true, token: null as string | null, remoteAvailable: false };
  }
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("approvals", {
      name: "Agent approvals",
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 220, 130, 220],
      lightColor: "#2563EB",
    });
  }
  const existing = await Notifications.getPermissionsAsync();
  const permission = existing.status === "granted" ? existing : await Notifications.requestPermissionsAsync();
  if (permission.status !== "granted") return { enabled: false, token: null as string | null, remoteAvailable: false };
  await setItem(ENABLED_KEY, "true");
  const projectId = Constants.easConfig?.projectId ?? Constants.expoConfig?.extra?.eas?.projectId;
  if (!projectId) return { enabled: true, token: null as string | null, remoteAvailable: false };
  try {
    const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
    await setItem(TOKEN_KEY, token);
    return { enabled: true, token, remoteAvailable: true };
  } catch { return { enabled: true, token: null as string | null, remoteAvailable: false }; }
}

export async function disableApprovalAlerts() {
  await setItem(ENABLED_KEY, "false");
  if (Platform.OS !== "web") await Notifications.setBadgeCountAsync(0);
}

export async function presentMissionAlert(title: string, body: string, url = "/(tabs)/automate") {
  if (!(await approvalAlertsEnabled()) || Platform.OS === "web") return;
  await Notifications.scheduleNotificationAsync({
    content: { title, body, data: { url }, sound: "default", badge: 1 },
    trigger: null,
  });
}
