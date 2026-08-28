import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack, useRouter, useSegments } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { NotificationProvider } from "@/lib/notification-context";
import { ConnectivityProvider } from "@/lib/connectivity";

function Gate() {
  const { user, loading } = useAuth(); const segments = useSegments(); const router = useRouter();
  useEffect(() => { if (!loading) { const route = String(segments[0]); const publicRoute = route === "login" || route === "reset-password"; if (!user && !publicRoute) router.replace("/login" as never); if (user && route === "login") router.replace("/(tabs)" as never); } }, [user, loading, segments, router]);
  if (loading) return <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#F7F9FC" }}><ActivityIndicator color="#2563EB" /></View>;
  return <Stack screenOptions={{ headerShown: false }}><Stack.Screen name="login" /><Stack.Screen name="reset-password" /><Stack.Screen name="account-security" /><Stack.Screen name="billing" /><Stack.Screen name="mobile-companion" /><Stack.Screen name="(tabs)" /><Stack.Screen name="campaign/[id]" /><Stack.Screen name="workspace" /><Stack.Screen name="platforms" /><Stack.Screen name="knowledge" /><Stack.Screen name="optimization" /><Stack.Screen name="personal-brand" /></Stack>;
}

export default function Root() {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 2, retryDelay: (attempt) => Math.min(600 * (attempt + 1), 2500), refetchOnReconnect: true } } }));
  return <SafeAreaProvider><QueryClientProvider client={client}><ConnectivityProvider><AuthProvider><NotificationProvider><Gate /><StatusBar style="dark" /></NotificationProvider></AuthProvider></ConnectivityProvider></QueryClientProvider></SafeAreaProvider>;
}
