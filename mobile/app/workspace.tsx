import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { Alert, FlatList, Pressable, StyleSheet, Switch, Text, View } from "react-native";
import { ScreenContainer } from "@/components/screen-container";
import { Button, Card, c, State, Title } from "@/components/nexus";
import { Field } from "@/components/workflow";
import { api, Profile } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { currencyForLocation, locationCurrency } from "@/lib/market-utils";

type Section = "business" | "location" | "preferences" | "account";

export default function Workspace() {
  const router = useRouter(); const client = useQueryClient(); const { user, logout } = useAuth();
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.profile.get });
  const [form, setForm] = useState<Profile>({ country: "United States", currency: "USD" }); const [saving, setSaving] = useState(false);
  useEffect(() => { if (profile.data) setForm(profile.data); }, [profile.data]);
  const set = (key: keyof Profile, value: string | boolean) => setForm((current) => ({ ...current, [key]: value }));
  const setCountry = (country: string) => setForm((current) => ({ ...current, country, currency: currencyForLocation(country, current.currency) }));
  const save = async () => { setSaving(true); try { await api.profile.save(form); await client.invalidateQueries({ queryKey: ["profile"] }); Alert.alert("Workspace saved", "Your business profile and currency settings are now up to date."); } catch { Alert.alert("Profile not saved", "Please try again."); } finally { setSaving(false); } };
  const signOut = async () => { await logout(); router.replace("/login" as never); };
  if (profile.isLoading) return <ScreenContainer><State title="Loading workspace profile" loading /></ScreenContainer>;
  return <ScreenContainer><FlatList<Section>
    data={["business", "location", "preferences", "account"]}
    keyExtractor={(item) => item}
    contentContainerStyle={s.content}
    ListHeaderComponent={<View style={s.header}><Pressable onPress={() => router.back()}><Text style={s.back}>‹ Home</Text></Pressable><Title eyebrow="WORKSPACE" title="Business profile" detail="Keep your marketing context and currency aligned to your location." /></View>}
    renderItem={({ item }) => item === "business" ? <Card><Text style={s.cardTitle}>Business context</Text><View style={s.gap}><Field label="COMPANY NAME" value={form.company_name ?? ""} onChangeText={(value) => set("company_name", value)} placeholder="Company name" /><Field label="WEBSITE" value={form.website ?? ""} onChangeText={(value) => set("website", value)} placeholder="https://company.com" /><Field label="INDUSTRY" value={form.industry ?? ""} onChangeText={(value) => set("industry", value)} placeholder="B2B SaaS" /><Field label="DESCRIPTION" value={form.description ?? ""} onChangeText={(value) => set("description", value)} placeholder="What does your business do?" multiline /></View></Card> : item === "location" ? <Card><Text style={s.cardTitle}>Location and currency</Text><Text style={s.support}>Choose your operating market. Its mapped currency is used in your performance views.</Text><FlatList horizontal data={Object.keys(locationCurrency)} keyExtractor={(country) => country} contentContainerStyle={s.chips} showsHorizontalScrollIndicator={false} renderItem={({ item: country }) => <Pressable onPress={() => setCountry(country)} style={[s.chip, form.country === country && s.chipActive]}><Text style={[s.chipText, form.country === country && s.chipTextActive]}>{country}</Text></Pressable>} /><View style={s.gap}><Field label="COUNTRY" value={form.country ?? ""} onChangeText={(value) => set("country", value)} placeholder="Country" /><Field label="CURRENCY" value={form.currency ?? ""} onChangeText={(value) => set("currency", value.toUpperCase())} placeholder="USD" /></View></Card> : item === "preferences" ? <Card><View style={s.pref}><View style={s.flex}><Text style={s.cardTitle}>Autopilot proposals</Text><Text style={s.support}>Allow the workspace to prepare daily marketing proposals for review.</Text></View><Switch value={Boolean(form.autopilot)} onValueChange={(value) => set("autopilot", value)} trackColor={{ false: "#C7D2E3", true: "#93B9FF" }} thumbColor={form.autopilot ? c.blue : c.white} /></View><View style={{ marginTop: 13 }}><Field label="DAILY PROPOSALS" value={String(form.daily_proposals ?? 3)} onChangeText={(value) => set("daily_proposals", value)} placeholder="3" /></View></Card> : <Card><Text style={s.cardTitle}>Account</Text><Text style={s.support}>{user?.email ?? "Signed-in workspace"}</Text><View style={s.accountActions}><Button secondary compact label="Account security" icon="security" onPress={() => router.push("/account-security" as never)} /><Button secondary compact label="Billing" icon="credit-card" onPress={() => router.push("/billing" as never)} /><Button secondary compact label="Sign out" icon="logout" onPress={signOut} /></View></Card>}
    ItemSeparatorComponent={() => <View style={{ height: 12 }} />}
    ListFooterComponent={<View style={{ marginTop: 4 }}><Button label="Save workspace changes" icon="save" onPress={save} loading={saving} /></View>}
  /></ScreenContainer>;
}

const s = StyleSheet.create({ content: { padding: 20, paddingBottom: 34 }, header: { gap: 12, marginBottom: 18 }, back: { color: c.blue, fontSize: 14, fontWeight: "900" }, cardTitle: { color: c.ink, fontSize: 16, fontWeight: "900" }, support: { color: c.muted, fontSize: 13, lineHeight: 19, marginTop: 5 }, gap: { gap: 11, marginTop: 13 }, chips: { gap: 7, paddingVertical: 12 }, chip: { backgroundColor: "#EEF2F7", borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8 }, chipActive: { backgroundColor: c.sky, borderWidth: 1, borderColor: "#BFD7FF" }, chipText: { color: c.muted, fontSize: 12, fontWeight: "900" }, chipTextActive: { color: c.blue }, pref: { flexDirection: "row", alignItems: "center", gap: 12 }, flex: { flex: 1 }, accountActions: { gap: 9, marginTop: 13 } });
