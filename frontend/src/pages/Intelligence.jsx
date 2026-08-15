import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section, StatCard } from "@/components/common";
import { toast } from "sonner";
import {
  Sparkle, Users, ArrowRight, Plus, ActivityIcon as Activity, Gauge, Recycle,
  Target, CircleNotch,
} from "@phosphor-icons/react";

export default function Intelligence() {
  const [tab, setTab] = useState("scoring");
  const [leads, setLeads] = useState([]);
  const [load, setLoad] = useState(true);
  const [busy, setBusy] = useState(false);
  const [revenue, setRevenue] = useState({ amount: "", stage: "won", lead_id: "" });
  const [rep, setRep] = useState(null);
  const [repLoad, setRepLoad] = useState(false);

  const loadLeads = () =>
    api.get("/leads").then((r) => { setLeads(r.data.slice(0, 30)); setLoad(false); }).catch(() => setLoad(false));

  const loadReport = async () => {
    setRepLoad(true);
    try {
      const { data } = await api.get("/attribution/report");
      setRep(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setRepLoad(false);
    }
  };

  useEffect(() => { loadLeads(); loadReport(); }, []);

  const score = async (lead) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/leads/${lead.id}/score-ai`);
      toast.success(`Scored: ${data.score} — ${data.category}`);
      loadLeads();
      loadReport();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const recordRevenue = async () => {
    const amount = parseFloat(revenue.amount);
    if (!revenue.lead_id) return toast.error("Choose a lead first");
    if (!amount || amount <= 0) return toast.error("Enter a valid amount");
    setBusy(true);
    try {
      await api.post("/revenue", { lead_id: revenue.lead_id, amount, stage: revenue.stage });
      toast.success("Revenue recorded and fed back to the engine");
      setRevenue({ amount: "", stage: "won", lead_id: revenue.lead_id });
      loadReport();
      loadLeads();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const catColor = (c) =>
    c === "Hot" || c === "Sales Ready" ? "text-emerald-600 bg-emerald-50 border-emerald-200"
    : c === "Warm" ? "text-amber-600 bg-amber-50 border-amber-200"
    : "text-zinc-600 bg-zinc-50 border-zinc-200";

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Module I + L — Revenue Intelligence"
        title="Intelligence"
        description="Composite, explainable lead scoring that learns from intent signals, plus first-touch attribution and revenue feedback — the closed loop that teaches the engine what actually converts."
      />

      <div className="flex gap-2 mb-6">
        {[
          ["scoring", "Lead Intelligence", Users],
          ["attribution", "Attribution & Revenue", Activity],
        ].map(([id, label, Icon]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 border px-4 py-2.5 text-xs uppercase tracking-[0.15em] ${tab === id ? "border-[#2563EB] text-[#2563EB] bg-[#EFF6FF]" : "border-border text-zinc-500 hover:bg-zinc-50"}`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {tab === "scoring" && (
        <Fade>
          {load ? <Loader label="Loading leads" /> : leads.length === 0 ? (
            <Section><p className="text-sm text-zinc-500">No leads yet. Add leads in Lead Management, then score them here.</p></Section>
          ) : (
            <div className="space-y-3">
              {leads.map((lead) => {
                const scores = lead.scores || {};
                return (
                  <div key={lead.id} className="border border-border bg-white">
                    <div className="flex flex-wrap items-center gap-4 px-4 py-3 border-b border-border">
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{lead.name} <span className="text-zinc-500 font-normal">— {lead.company}</span></div>
                        <div className="text-[10px] uppercase tracking-wider font-mono text-zinc-500 mt-0.5">{lead.role || "no role"} · {lead.source || "unknown source"}</div>
                      </div>
                      <div className="flex items-center gap-2 ml-auto shrink-0">
                        {lead.category && (
                          <span className={`text-[10px] uppercase tracking-wider font-mono px-2 py-1 border ${catColor(lead.category)}`}>
                            {lead.category}
                          </span>
                        )}
                        {lead.score !== null && lead.score !== undefined ? (
                          <span className="font-mono text-sm text-zinc-900">{lead.score}</span>
                        ) : (
                          <span className="font-mono text-xs text-zinc-400">unscored</span>
                        )}
                        <button
                          onClick={() => score(lead)}
                          disabled={busy}
                          className="flex items-center gap-1.5 border border-[#2563EB] text-[#2563EB] text-[10px] uppercase tracking-wider px-2.5 py-1.5 hover:bg-[#2563EB] hover:text-white disabled:opacity-50"
                        >
                          {busy ? <CircleNotch size={12} className="animate-spin" /> : <Sparkle size={13} />}
                          Score & Explain
                        </button>
                      </div>
                    </div>
                    {lead.scores && (
                      <div className="px-4 py-3 bg-zinc-50/60">
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
                          {[
                            ["ICP Fit", scores.fit, "match to your profile"],
                            ["Behavior", scores.behavior, "intent signals"],
                            ["Recency", scores.recency, "days since activity"],
                            ["Composite", lead.score, "weighted score"],
                          ].map(([label, val, hint]) => (
                            <div key={label} className="border border-border bg-white px-3 py-2">
                              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">{label}</div>
                              <div className="flex items-baseline gap-2">
                                <span className={`font-mono text-lg ${label === "Composite" ? "text-[#2563EB]" : "text-zinc-900"}`}>{val ?? "—"}</span>
                                <span className="text-[10px] text-zinc-400">{hint}</span>
                              </div>
                              <div className="h-1 bg-zinc-100 mt-2">
                                <div className="h-full bg-[#2563EB]" style={{ width: `${val ?? 0}%` }} />
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="flex items-start gap-2 text-[11px] text-zinc-600">
                          <Gauge size={13} className="text-[#2563EB] shrink-0 mt-0.5" />
                          <span>{lead.reasoning || (scores.components || []).join("; ")}</span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
              <div className="border border-border bg-white px-4 py-3 text-[11px] text-zinc-500">
                Scoring formula: 45% ICP fit (role seniority, industry, budget signal, company quality) · 35% behavior (intent signals) · 20% recency. Log intent signals below to sharpen behavior scores.
              </div>
            </div>
          )}
        </Fade>
      )}

      {tab === "attribution" && (
        <Fade>
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-0 border border-border bg-white">
              <StatCard
                label="Revenue Won"
                value={`$${rep?.metrics?.total_revenue_won?.toFixed(0) ?? 0}`}
                accent
              />
              <StatCard label="ROAS" value={rep?.metrics?.roas ?? 0} sub="revenue / spend" />
              <StatCard label="CPL" value={`$${rep?.metrics?.cpl ?? 0}`} sub="spend / touches" />
              <StatCard label="Touches Tracked" value={rep?.metrics?.touch_count ?? 0} sub="first / multi / last" />
            </div>

            <Section title="Record Revenue">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
                <div className="md:col-span-2">
                  <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Lead</label>
                  <select
                    value={revenue.lead_id}
                    onChange={(e) => setRevenue({ ...revenue, lead_id: e.target.value })}
                    className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                  >
                    <option value="">Select a lead…</option>
                    {leads.map((l) => (
                      <option key={l.id} value={l.id}>{l.name} — {l.company}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Amount (USD)</label>
                  <input
                    type="number"
                    value={revenue.amount}
                    onChange={(e) => setRevenue({ ...revenue, amount: e.target.value })}
                    placeholder="99"
                    className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
                <button
                  onClick={recordRevenue}
                  disabled={busy}
                  className="bg-[#2563EB] text-white text-xs uppercase tracking-[0.15em] py-2.5 hover:bg-[#1D4ED8] disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {busy ? <CircleNotch size={15} className="animate-spin" /> : <Plus size={15} />}
                  Record & Learn
                </button>
              </div>
              <p className="text-[11px] text-zinc-500 mt-3">
                Recorded revenue becomes a learning record — the engine uses wins and losses to propose better experiments.
              </p>
            </Section>

            <Section title="First-Touch Channel Attribution">
              {repLoad ? <Loader label="Loading attribution" /> : !rep?.metrics?.channel_attribution?.length ? (
                <p className="text-sm text-zinc-500">No attribution touches yet. Log touches in Lead Management or record revenue to build the picture.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left uppercase tracking-wider text-zinc-500 border-b border-border">
                        <th className="py-2 pr-4">Channel</th>
                        <th className="py-2 pr-4">Touches</th>
                        <th className="py-2 pr-4">First Touch</th>
                        <th className="py-2 pr-4">Last Touch</th>
                        <th className="py-2">First-Touch Revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rep.metrics.channel_attribution.map((ch) => (
                        <tr key={ch.channel} className="border-b border-border/50">
                          <td className="py-2 pr-4 font-medium">{ch.channel}</td>
                          <td className="py-2 pr-4 font-mono">{ch.touches}</td>
                          <td className="py-2 pr-4 font-mono">{ch.first_touch}</td>
                          <td className="py-2 pr-4 font-mono">{ch.last_touch}</td>
                          <td className="py-2 font-mono text-[#2563EB]">${ch.first_touch_revenue}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Section>

            <Section title="How the Closed Loop Feeds Strategy">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-zinc-600">
                <div className="flex gap-2">
                  <Users size={16} className="text-[#2563EB] shrink-0" />
                  <p><b className="text-zinc-900">Score.</b> Every lead gets an explainable composite score: fit, behavior and recency — no black box, reason codes shown.</p>
                </div>
                <div className="flex gap-2">
                  <Activity size={16} className="text-[#2563EB] shrink-0" />
                  <p><b className="text-zinc-900">Attribute.</b> Touches and revenue are tied to channels, so spend follows what actually produces pipeline.</p>
                </div>
                <div className="flex gap-2">
                  <Recycle size={16} className="text-[#2563EB] shrink-0" />
                  <p><b className="text-zinc-900">Learn.</b> Wins and losses are recorded as learning records and shape the next week's experiments and plan.</p>
                </div>
              </div>
            </Section>
          </div>
        </Fade>
      )}
    </div>
  );
}
