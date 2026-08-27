import * as Network from "expo-network";
import { createContext, PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { QueryClient, useQueryClient } from "@tanstack/react-query";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { c } from "@/components/nexus";

type ConnectivityValue = { online: boolean; checking: boolean; refresh: () => Promise<void> };
const ConnectivityContext = createContext<ConnectivityValue | null>(null);
function isOnline(state: Network.NetworkState) { return state.isInternetReachable ?? state.isConnected ?? false; }
export function ConnectivityProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient(); const [online, setOnline] = useState(true); const [checking, setChecking] = useState(false);
  useEffect(() => { void Network.getNetworkStateAsync().then((state) => setOnline(isOnline(state))).catch(() => setOnline(true)); const listener = Network.addNetworkStateListener((state) => { const reachable = isOnline(state); setOnline(reachable); if (reachable) void queryClient.refetchQueries({ type: "active" }); }); return () => listener.remove(); }, [queryClient]);
  const refresh = useCallback(async () => { setChecking(true); try { const state = await Network.getNetworkStateAsync(); const reachable = isOnline(state); setOnline(reachable); if (reachable) await queryClient.refetchQueries({ type: "active" }); } finally { setChecking(false); } }, [queryClient]);
  const value = useMemo(() => ({ online, checking, refresh }), [online, checking, refresh]); return <ConnectivityContext.Provider value={value}>{children}</ConnectivityContext.Provider>;
}
export function useConnectivity() { const value = useContext(ConnectivityContext); if (!value) throw new Error("useConnectivity must be used inside ConnectivityProvider."); return value; }
export function OfflineBanner() { const { online, checking, refresh } = useConnectivity(); if (online) return null; return <View style={s.banner}><View style={{ flex: 1 }}><Text style={s.title}>Working offline</Text><Text style={s.detail}>Showing your most recently saved workspace data.</Text></View><Pressable accessibilityRole="button" onPress={() => void refresh()} style={({ pressed }) => [s.button, pressed && { opacity: 0.72 }]}><Text style={s.buttonText}>{checking ? "Checking…" : "Retry"}</Text></Pressable></View>; }
const s = StyleSheet.create({ banner: { backgroundColor: "#FFF4E5", borderBottomWidth: 1, borderColor: "#F8D7A5", paddingHorizontal: 16, paddingVertical: 9, flexDirection: "row", alignItems: "center", gap: 10 }, title: { color: "#A14F00", fontSize: 12, fontWeight: "900" }, detail: { color: "#A14F00", fontSize: 11, marginTop: 2 }, button: { backgroundColor: c.white, borderWidth: 1, borderColor: "#F0B75E", paddingHorizontal: 10, minHeight: 31, borderRadius: 9, justifyContent: "center" }, buttonText: { color: "#A14F00", fontWeight: "900", fontSize: 12 } });
