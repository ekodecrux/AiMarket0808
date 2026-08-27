import { PropsWithChildren } from "react";
import { SafeAreaView } from "react-native-safe-area-context";
import { StyleSheet } from "react-native";
import { OfflineBanner } from "@/lib/connectivity";

export function ScreenContainer({ children }: PropsWithChildren<{ className?: string }>) {
  return <SafeAreaView edges={["top", "left", "right"]} style={styles.screen}><OfflineBanner />{children}</SafeAreaView>;
}
const styles = StyleSheet.create({ screen: { flex: 1, backgroundColor: "#F7F9FC" } });
