import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { ScreenContainer } from "@/components/screen-container";
import { Button, Card, c, money, Pill, State } from "@/components/nexus";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

type Block = "hero" | "personal" | "metrics" | "watch" | "actions";

export default function Home() {
  const router = useRouter();
  const { user } = useAuth();
  const overview = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.profile.get });
  const campaigns = useQuery({ queryKey: ["campaigns"], queryFn: api.campaigns.list });
  const kpis = (overview.data as { kpis?: Record<string, number> } | undefined)?.kpis ?? {};
  const currency = profile.data?.currency ?? "USD";
  const refresh = () => void Promise.all([overview.refetch(), profile.refetch(), campaigns.refetch()]);

  if (overview.isLoading || profile.isLoading || campaigns.isLoading) return <ScreenContainer><State title="Opening your command view" loading /></ScreenContainer>;

  return <ScreenContainer><FlatList
    data={["hero", "personal", "metrics", "watch", "actions"] as Block[]}
    keyExtractor={(item) => item}
    contentContainerStyle={s.content}
    refreshControl={<RefreshControl refreshing={overview.isRefetching} onRefresh={refresh} tintColor={c.blue} />}
    ListHeaderComponent={<Header name={user?.name} email={user?.email} company={profile.data?.company_name} onProfile={() => router.push("/workspace" as never)} />}
    renderItem={({ item }) => {
      if (item === "hero") return <Hero revenue={money(kpis.revenue, currency)} leads={String(kpis.hot_leads ?? 0)} />;
      if (item === "personal") return <PersonalBrandMenu onOpen={() => router.push("/personal-brand" as never)} onProfile={() => router.push({ pathname: "/personal-brand", params: { focus: "profile" } } as never)} onHeadline={() => router.push({ pathname: "/personal-brand", params: { focus: "profile", action: "headline" } } as never)} onAbout={() => router.push({ pathname: "/personal-brand", params: { focus: "profile", action: "about" } } as never)} />;
      if (item === "metrics") return <PerformanceMetrics kpis={kpis} currency={currency} />;
      if (item === "watch") return <CampaignWatch campaign={campaigns.data?.[0]} currency={currency} onOpen={(id) => router.push({ pathname: "/campaign/[id]", params: { id } } as never)} onAll={() => router.push("/(tabs)/campaigns" as never)} />;
      return <Actions onCampaign={() => router.push("/(tabs)/campaigns" as never)} onPlan={() => router.push("/(tabs)/plan" as never)} onBrain={() => router.push("/(tabs)/intelligence" as never)} onAutomate={() => router.push("/(tabs)/automate" as never)} onPlatforms={() => router.push("/platforms" as never)} onKnowledge={() => router.push("/knowledge" as never)} onOptimization={() => router.push("/optimization" as never)} onPersonalBrand={() => router.push("/personal-brand" as never)} />;
    }}
  /></ScreenContainer>;
}

function Header({ name, email, company, onProfile }: { name?: string; email?: string; company?: string; onProfile: () => void }) {
  const initial = (name || email || "A")[0]?.toUpperCase();
  return <View style={s.header}><View style={s.headerCopy}><Text style={s.overline}>NEXUS · LIVE OPERATING CONTEXT</Text><Text style={s.greeting}>Welcome back{name ? `, ${name.split(" ")[0]}` : ""}.</Text><Text style={s.company}>{company || "Your connected marketing workspace"}</Text></View><Pressable accessibilityRole="button" accessibilityLabel="Open workspace settings" onPress={onProfile} style={({ pressed }) => [s.avatar, pressed && { opacity: 0.75 }]}><Text style={s.avatarText}>{initial}</Text></Pressable></View>;
}

function Hero({ revenue, leads }: { revenue: string; leads: string }) {
  return <View style={s.hero}><View style={s.heroRing} /><View style={s.heroTop}><View><Text style={s.heroEyebrow}>TODAY’S OPERATING SIGNAL</Text><Text style={s.heroTitle}>Growth is in motion.</Text></View><View style={s.live}><View style={s.liveDot} /><Text style={s.liveText}>LIVE</Text></View></View><Text style={s.heroDetail}>Monitor the levers that matter, then move from insight to execution without breaking your flow.</Text><View style={s.heroMetrics}><HeroMetric icon="payments" label="Revenue" value={revenue} /><HeroMetric icon="groups" label="Qualified leads" value={leads} /></View></View>;
}
function HeroMetric({ icon, label, value }: { icon: React.ComponentProps<typeof MaterialIcons>["name"]; label: string; value: string }) { return <View style={s.heroMetric}><MaterialIcons name={icon} size={15} color="#9FC3FF" /><View><Text style={s.heroMetricValue}>{value}</Text><Text style={s.heroMetricLabel}>{label}</Text></View></View>; }

function PersonalBrandMenu({ onOpen, onProfile, onHeadline, onAbout }: { onOpen: () => void; onProfile: () => void; onHeadline: () => void; onAbout: () => void }) {
  return <View style={s.personalBlock}><View style={s.personalHeader}><View><Text style={s.personalEyebrow}>PERSONAL BRANDING</Text><Text style={s.personalTitle}>Grow your LinkedIn presence.</Text></View><Pressable onPress={onOpen} style={({ pressed }) => [s.personalOpen, pressed && { opacity: 0.7 }]}><Text style={s.personalOpenText}>Open studio</Text><MaterialIcons name="arrow-forward" size={15} color={c.blue} /></Pressable></View><Text style={s.personalDetail}>Turn your expertise into a clearer profile and useful professional content—always reviewed by you before it goes live.</Text><View style={s.personalActions}><QuickProfileAction icon="badge" label="Profile readiness" onPress={onProfile} /><QuickProfileAction icon="title" label="Improve headline" onPress={onHeadline} /><QuickProfileAction icon="subject" label="Write About section" onPress={onAbout} /></View></View>;
}
function QuickProfileAction({ icon, label, onPress }: { icon: React.ComponentProps<typeof MaterialIcons>["name"]; label: string; onPress: () => void }) { return <Pressable onPress={onPress} style={({ pressed }) => [s.personalAction, pressed && { opacity: 0.72, transform: [{ scale: 0.98 }] }]}><MaterialIcons name={icon} size={18} color={c.blue} /><Text style={s.personalActionText}>{label}</Text><MaterialIcons name="chevron-right" size={17} color="#90A4BD" /></Pressable>; }

function PerformanceMetrics({ kpis, currency }: { kpis: Record<string, number>; currency: string }) {
  const items = [{ label: "Campaign spend", value: money(kpis.total_spend, currency), hint: `${kpis.campaigns ?? 0} active streams`, icon: "campaign" as const, color: "#2563EB" }, { label: "ROI", value: `${kpis.roi ?? 0}%`, hint: "Revenue efficiency", icon: "trending-up" as const, color: "#16A34A" }, { label: "Total leads", value: String(kpis.total_leads ?? 0), hint: "Across acquisition", icon: "groups" as const, color: "#8B5CF6" }];
  return <View style={s.block}><Section title="Performance pulse" tag="LIVE DATA" /><FlatList horizontal data={items} keyExtractor={(metric) => metric.label} showsHorizontalScrollIndicator={false} contentContainerStyle={s.metricList} renderItem={({ item: metric }) => <View style={s.metricCard}><View style={[s.metricIcon, { backgroundColor: `${metric.color}16` }]}><MaterialIcons name={metric.icon} size={18} color={metric.color} /></View><Text style={s.metricLabel}>{metric.label}</Text><Text style={s.metricValue}>{metric.value}</Text><Text style={s.metricHint}>{metric.hint}</Text></View>} /></View>;
}

function CampaignWatch({ campaign, currency, onOpen, onAll }: { campaign?: { _id: string; name: string; channel: string; objective: string; status: string; roas?: number; revenue?: number; conversions?: number }; currency: string; onOpen: (id: string) => void; onAll: () => void }) {
  return <View style={s.block}><Section title="Campaign radar" link="See all" onLink={onAll} />{campaign ? <Card><View style={s.cardTop}><View style={s.channelMark}><MaterialIcons name="campaign" color={c.blue} size={18} /></View><View style={{ flex: 1 }}><Text style={s.cardTitle}>{campaign.name}</Text><Text style={s.cardDetail}>{campaign.channel} · {campaign.objective}</Text></View><Pill label={campaign.status} tone={campaign.status === "Active" ? "green" : "amber"} /></View><View style={s.divider} /><View style={s.stats}><MiniStat label="ROAS" value={`${Number(campaign.roas ?? 0).toFixed(2)}x`} /><MiniStat label="REVENUE" value={money(campaign.revenue, currency)} /><MiniStat label="CONVERSIONS" value={String(campaign.conversions ?? 0)} /></View><Button compact label="Open campaign control" icon="arrow-forward" onPress={() => onOpen(campaign._id)} /></Card> : <State title="No active campaign signal" detail="Create your first campaign to begin monitoring the work." />}</View>;
}
function MiniStat({ label, value }: { label: string; value: string }) { return <View><Text style={s.statValue}>{value}</Text><Text style={s.statLabel}>{label}</Text></View>; }

function Actions({ onCampaign, onPlan, onBrain, onAutomate, onPlatforms, onKnowledge, onOptimization, onPersonalBrand }: { onCampaign: () => void; onPlan: () => void; onBrain: () => void; onAutomate: () => void; onPlatforms: () => void; onKnowledge: () => void; onOptimization: () => void; onPersonalBrand: () => void }) {
  return <View style={s.block}><Section title="Command actions" tag="ONE TAP" /><View style={s.actionGrid}><Action icon="add-chart" label="Launch campaign" note="Paid media" onPress={onCampaign} /><Action icon="person" label="Personal brand" note="LinkedIn-first studio" onPress={onPersonalBrand} /><Action icon="hub" label="Connect platforms" note="Social + advertising" onPress={onPlatforms} /><Action icon="auto-awesome" label="Build a plan" note="Frameworks + content" onPress={onPlan} /><Action icon="memory" label="Operating memory" note="Reuse evidence first" onPress={onKnowledge} /><Action icon="savings" label="Budget control" note="Evidence-led spend" onPress={onOptimization} /><Action icon="psychology" label="Ask Business Brain" note="Grounded answers" onPress={onBrain} /><Action icon="smart-toy" label="Run an agent" note="Automation control" onPress={onAutomate} /></View></View>;
}
function Section({ title, tag, link, onLink }: { title: string; tag?: string; link?: string; onLink?: () => void }) { return <View style={s.sectionRow}><Text style={s.section}>{title}</Text>{link ? <Pressable onPress={onLink}><Text style={s.link}>{link}</Text></Pressable> : <Text style={s.miniLabel}>{tag}</Text>}</View>; }
function Action({ icon, label, note, onPress }: { icon: React.ComponentProps<typeof MaterialIcons>["name"]; label: string; note: string; onPress: () => void }) { return <Pressable onPress={onPress} style={({ pressed }) => [s.action, pressed && { opacity: 0.75, transform: [{ scale: 0.98 }] }]}><View style={s.actionIcon}><MaterialIcons name={icon} color={c.blue} size={20} /></View><View style={{ flex: 1 }}><Text style={s.actionText}>{label}</Text><Text style={s.actionNote}>{note}</Text></View><MaterialIcons name="arrow-forward" color="#9AACBF" size={17} /></Pressable>; }

const s = StyleSheet.create({
  content: { padding: 16, paddingBottom: 24, gap: 14 },
  header: { minHeight: 70, justifyContent: "center", alignItems: "center", paddingTop: 1 },
  headerCopy: { alignItems: "center", paddingHorizontal: 46 },
  overline: { color: c.blue, fontSize: 9, fontWeight: "900", letterSpacing: 1.05 },
  greeting: { color: c.ink, fontSize: 25, lineHeight: 31, fontWeight: "900", marginTop: 5, letterSpacing: -0.5, textAlign: "center" },
  company: { color: c.muted, fontSize: 12, marginTop: 3, textAlign: "center" },
  avatar: { position: "absolute", right: 0, top: 8, width: 40, height: 40, borderRadius: 13, backgroundColor: c.navy, borderWidth: 1, borderColor: "#284466", alignItems: "center", justifyContent: "center" },
  avatarText: { color: c.white, fontWeight: "900", fontSize: 16 },
  hero: { minHeight: 168, backgroundColor: c.navy, borderRadius: 19, padding: 15, overflow: "hidden", borderWidth: 1, borderColor: "#1E395B" },
  heroRing: { position: "absolute", width: 260, height: 260, borderRadius: 260, borderWidth: 1, borderColor: "#2867BE", opacity: 0.5, right: -120, bottom: -150 },
  heroTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  heroEyebrow: { color: "#9EC3FF", fontSize: 9, fontWeight: "900", letterSpacing: 1 },
  heroTitle: { color: c.white, fontSize: 23, lineHeight: 29, fontWeight: "900", marginTop: 6 },
  live: { flexDirection: "row", alignItems: "center", gap: 5, paddingHorizontal: 8, paddingVertical: 5, borderRadius: 999, backgroundColor: "#123052" },
  liveDot: { width: 6, height: 6, borderRadius: 6, backgroundColor: "#4ADE80" },
  liveText: { color: "#B7D3FF", fontSize: 9, fontWeight: "900", letterSpacing: 0.5 },
  heroDetail: { color: "#B5C4DB", fontSize: 12, lineHeight: 18, marginTop: 10, maxWidth: 290 },
  heroMetrics: { flexDirection: "row", gap: 10, marginTop: 11 },
  heroMetric: { flexDirection: "row", alignItems: "center", gap: 7, backgroundColor: "#10253F", borderWidth: 1, borderColor: "#1F416B", paddingHorizontal: 10, paddingVertical: 8, borderRadius: 11 },
  heroMetricValue: { color: c.white, fontSize: 14, fontWeight: "900" },
  heroMetricLabel: { color: "#9EB0CA", fontSize: 9, marginTop: 2 },
  personalBlock: { backgroundColor: "#F3F7FF", borderWidth: 1, borderColor: "#D4E3FC", borderRadius: 18, padding: 14 },
  personalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 8 },
  personalEyebrow: { color: c.blue, fontSize: 9, fontWeight: "900", letterSpacing: 1 },
  personalTitle: { color: c.ink, fontSize: 17, fontWeight: "900", marginTop: 4 },
  personalOpen: { flexDirection: "row", alignItems: "center", gap: 3, paddingVertical: 3 },
  personalOpenText: { color: c.blue, fontSize: 11, fontWeight: "900" },
  personalDetail: { color: c.muted, fontSize: 12, lineHeight: 18, marginTop: 8 },
  personalActions: { gap: 7, marginTop: 12 },
  personalAction: { minHeight: 42, backgroundColor: c.white, borderWidth: 1, borderColor: "#D9E5F7", borderRadius: 11, paddingHorizontal: 10, flexDirection: "row", alignItems: "center", gap: 8 },
  personalActionText: { color: c.ink, fontSize: 12, fontWeight: "800", flex: 1 },
  block: { gap: 1 },
  sectionRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  section: { color: c.ink, fontSize: 16, fontWeight: "900" },
  miniLabel: { color: "#94A3B8", fontSize: 9, fontWeight: "900", letterSpacing: 0.8 },
  link: { color: c.blue, fontSize: 12, fontWeight: "900" },
  metricList: { gap: 9, paddingRight: 17 },
  metricCard: { width: 142, backgroundColor: c.white, padding: 12, borderRadius: 15, borderWidth: 1, borderColor: c.border },
  metricIcon: { width: 34, height: 34, borderRadius: 11, justifyContent: "center", alignItems: "center" },
  metricLabel: { color: c.muted, fontSize: 11, fontWeight: "800", marginTop: 10 },
  metricValue: { color: c.ink, fontSize: 20, fontWeight: "900", marginTop: 3 },
  metricHint: { color: "#94A3B8", fontSize: 10, marginTop: 3 },
  cardTop: { flexDirection: "row", alignItems: "flex-start", gap: 9 },
  channelMark: { width: 34, height: 34, justifyContent: "center", alignItems: "center", backgroundColor: c.sky, borderRadius: 11 },
  cardTitle: { color: c.ink, fontSize: 15, fontWeight: "900" },
  cardDetail: { color: c.muted, fontSize: 11, marginTop: 4 },
  divider: { height: 1, backgroundColor: c.border, marginVertical: 15 },
  stats: { flexDirection: "row", justifyContent: "space-between", marginBottom: 16 },
  statValue: { color: c.ink, fontSize: 13, fontWeight: "900" },
  statLabel: { color: "#94A3B8", fontSize: 8, fontWeight: "900", marginTop: 3 },
  actionGrid: { gap: 8 },
  action: { minHeight: 62, backgroundColor: c.white, borderRadius: 14, borderWidth: 1, borderColor: c.border, padding: 11, flexDirection: "row", alignItems: "center", gap: 10 },
  actionIcon: { width: 36, height: 36, borderRadius: 12, backgroundColor: c.sky, alignItems: "center", justifyContent: "center" },
  actionText: { color: c.ink, fontSize: 13, fontWeight: "900" },
  actionNote: { color: c.muted, fontSize: 10, marginTop: 3 },
});
