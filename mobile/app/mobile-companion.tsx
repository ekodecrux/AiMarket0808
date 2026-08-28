import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { useRouter } from "expo-router";
import { Alert, FlatList, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { ScreenContainer } from "@/components/screen-container";
import { Button, Card, c, Title } from "@/components/nexus";
import { useConnectivity } from "@/lib/connectivity";
import { useNotifications } from "@/lib/notification-context";

type Section = "alerts" | "availability" | "calendar" | "connections";

export default function MobileCompanion() {
  const router = useRouter();
  const { online, checking, refresh } = useConnectivity();
  const { enabled, registering, remoteReady, enable, disable } = useNotifications();
  const native = Platform.OS !== "web";
  const enableAlerts = async () => {
    const granted = await enable();
    Alert.alert(granted ? "Alerts enabled" : "Permission not granted", granted ? "Approval and mission alerts are enabled for this device." : "You can enable notifications later in your device settings.");
  };

  return <ScreenContainer><FlatList<Section>
    data={["alerts", "availability", "calendar", "connections"]}
    keyExtractor={(item) => item}
    contentContainerStyle={s.content}
    ListHeaderComponent={<View style={s.header}><Pressable accessibilityRole="button" accessibilityLabel="Go back" onPress={() => router.back()} style={({ pressed }) => [s.back, pressed && { opacity: 0.7 }]}><MaterialIcons name="arrow-back" color={c.blue} size={18} /><Text style={s.backText}>Workspace</Text></Pressable><Title eyebrow="DEVICE SETTINGS" title="AiMarket on this device" detail="The same marketing workspace as the website, with device-aware controls where they add value." /></View>}
    renderItem={({ item }) => {
      if (item === "alerts") return <Card><Capability icon="notifications-active" title="Approval and mission alerts" detail={enabled ? (remoteReady ? "Permissions are on and this device is registered for approval alerts." : "Permissions are on. Local alerts work now; remote approval delivery is pending device-build configuration.") : "Enable device notifications for approval and mission status alerts."} tone={enabled ? "good" : "neutral"} /><Button secondary compact label={enabled ? "Disable alerts" : "Enable alerts"} icon={enabled ? "notifications-off" : "notifications-active"} onPress={() => void (enabled ? disable() : enableAlerts())} loading={registering} /></Card>;
      if (item === "availability") return <Card><Capability icon={online ? "cloud-done" : "cloud-off"} title="Offline-aware workspace" detail={online ? "Connected. Pull-to-refresh and Retry keep live workspace views current." : "Offline. Recent supported workspace data stays visible and active queries retry when the connection returns."} tone={online ? "good" : "warning"} /><Button secondary compact label={checking ? "Checking connection" : "Check connection"} icon="refresh" onPress={() => void refresh()} loading={checking} /></Card>;
      if (item === "calendar") return <Card><Capability icon="event" title="Weekly visibility reminders" detail="Create your own recurring LinkedIn visibility reminders in your device calendar. AiMarket never posts, messages, or connects on your behalf." tone="neutral" /><Button secondary compact label="Open Personal Brand routine" icon="arrow-forward" onPress={() => router.push({ pathname: "/personal-brand", params: { focus: "routine" } } as never)} /></Card>;
      return <Card><Capability icon="open-in-new" title="Official account handoffs" detail="Platform connections open only provider authorization pages after the platform owner configures OAuth. AiMarket does not request provider passwords, cookies, or 2FA codes." tone="neutral" /><View style={s.connectionDetail}><Text style={s.detailLabel}>CURRENT CLIENT</Text><Text style={s.detailValue}>{native ? `${Platform.OS === "ios" ? "iOS" : "Android"} native client · secure local session storage` : "Web preview · install a signed app or open a native development build to use device services"}</Text></View><Button label="Open Platform Hub" icon="hub" onPress={() => router.push("/platforms" as never)} /></Card>;
    }}
    ItemSeparatorComponent={() => <View style={{ height: 12 }} />}
  /></ScreenContainer>;
}

function Capability({ icon, title, detail, tone }: { icon: React.ComponentProps<typeof MaterialIcons>["name"]; title: string; detail: string; tone: "good" | "warning" | "neutral" }) {
  const color = tone === "good" ? "#15803D" : tone === "warning" ? "#B45309" : c.blue;
  const background = tone === "good" ? "#F0FDF4" : tone === "warning" ? "#FFF7ED" : "#EFF6FF";
  return <View style={s.capability}><View style={[s.icon, { backgroundColor: background }]}><MaterialIcons name={icon} color={color} size={20} /></View><View style={s.capabilityCopy}><Text style={s.capabilityTitle}>{title}</Text><Text style={s.capabilityDetail}>{detail}</Text></View></View>;
}

const s = StyleSheet.create({ content: { padding: 20, paddingBottom: 34 }, header: { gap: 12, marginBottom: 18 }, back: { flexDirection: "row", alignItems: "center", gap: 5, alignSelf: "flex-start", paddingVertical: 2 }, backText: { color: c.blue, fontSize: 14, fontWeight: "900" }, capability: { flexDirection: "row", gap: 11, marginBottom: 14 }, icon: { height: 40, width: 40, borderRadius: 12, alignItems: "center", justifyContent: "center" }, capabilityCopy: { flex: 1 }, capabilityTitle: { color: c.ink, fontSize: 15, fontWeight: "900" }, capabilityDetail: { color: c.muted, fontSize: 12, lineHeight: 18, marginTop: 4 }, connectionDetail: { borderTopWidth: 1, borderTopColor: c.border, paddingTop: 11, marginBottom: 13 }, detailLabel: { color: "#94A3B8", fontSize: 9, fontWeight: "900", letterSpacing: 0.8 }, detailValue: { color: c.ink, fontSize: 12, lineHeight: 18, marginTop: 4, fontWeight: "700" } });
