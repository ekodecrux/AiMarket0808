import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section, StatCard } from "@/components/common";
import { toast } from "sonner";
import {
  Lightbulb, Flask, Power, ShieldCheck, List, FileText,
  CircleNotch, Check, TrendUp, X as XIcon, Warning,
} from "@phosphor-icons/react";

export default function Learning() {
  const [tab, setTab] = useState("learning");
  const [records, setRecords] = useState([]);
  const [exps, setExps] = useState([]);
  const [policy, setPolicy] = useState({ autonomy_level: "suggest", kill_switch: false });
  const [events, setEvents] = useState([]);
  const [load, setLoad] = useState(true);
  const [busy, setBusy] = useState(false);
  const [newExp, setNewExp] = useState({ name: "", hypothesis: "", primary_metric: "conversions", min_sample: 100, variants: ["", ""] });

  const loadAll = async () => {
    try {
      const [recRes, expRes, polRes, evRes] = await Promise.all([
        api.get("/learning"),
        api.get("/experiments"),
        api.get("/policy"),
        api.get("/events?limit=30"),
      ]);
      setRecords(recRes.data);
      setExps(expRes.data);
      setPolicy(polRes.data);
      setEvents(evRes.data);
      setLoad(false);
    } catch {
      setLoad(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const generateLearning = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/learning/generate");
      toast.success("Weekly learning report generated");
      loadAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const decide = async (exp, verdict) => {
    setBusy(true);
    try {
      await api.post(`/experiments/${exp.id}/decide`, { decision: verdict });
      toast.success(verdict === "winner" ? "Winner declared — learning recorded" : "Experiment concluded");
      loadAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const startExperiment = async () => {
    const variants = newExp.variants.filter(Boolean).map((n) => ({ name: n }));
    if (newExp.name.length < 3) return toast.error("Name the experiment");
    if (newExp.hypothesis.length < 10) return toast.error("State a fuller hypothesis");
    if (variants.length < 2) return toast.error("Add at least two variants");
    setBusy(true);
    try {
      await api.post("/experiments", {
        name: newExp.name,
        hypothesis: newExp.hypothesis,
        variables: ["creative"],
        primary_metric: newExp.primary_metric,
        min_sample: parseInt(newExp.min_sample) || 100,
        variants,
      });
      toast.success("Experiment created — track impressions and conversions in Campaigns");
      setNewExp({ name: "", hypothesis: "", primary_metric: "conversions", min_sample: 100, variants: ["", ""] });
      loadAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const setLevel = async (level) => {
    setBusy(true);
    try {
      await api.post("/policy", { ...policy, autonomy_level: level });
      toast.success(`Autonomy set to ${level.replace(/_/g, " ")}`);
      loadAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const toggleKill = async () => {
    setBusy(true);
    try {
      const next = !policy.kill_switch;
      await api.post("/policy/kill-switch", { active: next });
      toast(next ? "Kill switch activated — all autonomous actions paused" : "Autonomy restored");
      loadAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const levels = [
    ["suggest", "Suggest", "Engine advises; you act"],
    ["approve", "Approve", "Engine drafts; human approves each action"],
    ["controlled_autopilot", "Controlled Autopilot", "Runs within spend & channel limits"],
    ["full_autopilot", "Full Autopilot", "Engine executes freely (policy-gated)"],
  ];

  const fmt = (iso) => {
    try {
      return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch {
      return iso;
    }
  };

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Module O + M + Q — Learning & Governance"
        title="Learning & Governance"
        description="Weekly learning records that feed the next plan, hypothesis-driven experiments with statistical decision rules, and autonomy policy with an emergency kill switch."
      />

      <div className="flex flex-wrap gap-2 mb-6">
        {[
          ["learning", "Learning Records", Lightbulb],
          ["experiments", "Experiments", Flask],
          ["governance", "Autonomy Policy", ShieldCheck],
          ["events", "Telemetry & Audit", List],
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

      {tab === "learning" && (
        <Fade>
          <div className="flex items-center justify-between border border-border bg-white px-5 py-4 mb-4">
            <div className="text-sm text-zinc-600 max-w-2xl">
              The engine summarizes the week — winners, losers, revenue outcomes — and proposes the next experiments. Every record is stored and feeds future mission plans.
            </div>
            <button
              onClick={generateLearning}
              disabled={busy}
              className="bg-[#2563EB] text-white text-xs uppercase tracking-[0.15em] px-5 py-2.5 hover:bg-[#1D4ED8] disabled:opacity-50 flex items-center gap-2 shrink-0"
            >
              {busy ? <CircleNotch size={14} className="animate-spin" /> : <TrendUp size={14} />}
              Generate Report
            </button>
          </div>
          {load ? <Loader label="Loading learning records" /> : records.length === 0 ? (
            <Section><p className="text-sm text-zinc-500">No learning records yet. Run experiments and record revenue, then generate a report.</p></Section>
          ) : (
            <div className="space-y-4">
              {records.map((r) => (
                <div key={r.id} className="border border-border bg-white">
                  <div className="px-5 py-3 border-b border-border flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Lightbulb size={16} className="text-[#FFCC00]" />
                      <span className="text-xs uppercase tracking-[0.15em] text-zinc-500 font-mono">
                        {r.period || "weekly"} record · {fmt(r.created_at || r.generated_at)}
                      </span>
                    </div>
                    <span className={`text-[10px] uppercase tracking-wider font-mono px-2 py-1 border ${r.confidence === "high" ? "border-emerald-300 text-emerald-600" : r.confidence === "low" ? "border-amber-300 text-amber-600" : "border-zinc-300 text-zinc-600"}`}>
                      {r.confidence || "medium"} confidence
                    </span>
                  </div>
                  <div className="p-5 space-y-4">
                    <p className="text-sm text-zinc-700">{r.summary}</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {(r.winners || []).length > 0 && (
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-emerald-600 mb-1.5 flex items-center gap-1"><Check size={12} /> Winners</div>
                          <ul className="space-y-1">{r.winners.map((w, i) => <li key={i} className="text-xs text-zinc-700 flex gap-2"><Check size={12} className="text-emerald-500 shrink-0 mt-0.5" />{w}</li>)}</ul>
                        </div>
                      )}
                      {(r.losers || []).length > 0 && (
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-red-500 mb-1.5 flex items-center gap-1"><XIcon size={12} /> Losers</div>
                          <ul className="space-y-1">{r.losers.map((w, i) => <li key={i} className="text-xs text-zinc-700 flex gap-2"><XIcon size={12} className="text-red-400 shrink-0 mt-0.5" />{w}</li>)}</ul>
                        </div>
                      )}
                      {(r.reasons || []).length > 0 && (
                        <div className="md:col-span-2">
                          <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1.5">Reasons</div>
                          <ul className="space-y-1">{r.reasons.map((w, i) => <li key={i} className="text-xs text-zinc-600">{w}</li>)}</ul>
                        </div>
                      )}
                      {(r.next_experiments || []).length > 0 && (
                        <div className="md:col-span-2">
                          <div className="text-[10px] uppercase tracking-wider text-[#2563EB] mb-1.5">Proposed next experiments</div>
                          <ul className="space-y-1">{r.next_experiments.map((w, i) => <li key={i} className="text-xs text-zinc-700 flex gap-2"><Flask size={12} className="text-[#2563EB] shrink-0 mt-0.5" />{w}</li>)}</ul>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Fade>
      )}

      {tab === "experiments" && (
        <Fade>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="space-y-4">
              <Section title="Design Experiment">
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Name</label>
                    <input
                      value={newExp.name}
                      onChange={(e) => setNewExp({ ...newExp, name: e.target.value })}
                      placeholder="Ad headline test"
                      className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Hypothesis</label>
                    <textarea
                      rows={3}
                      value={newExp.hypothesis}
                      onChange={(e) => setNewExp({ ...newExp, hypothesis: e.target.value })}
                      placeholder="Question-style headlines will outperform statements on CTR"
                      className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB] resize-none"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Metric</label>
                      <select
                        value={newExp.primary_metric}
                        onChange={(e) => setNewExp({ ...newExp, primary_metric: e.target.value })}
                        className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                      >
                        <option value="conversions">Conversions</option>
                        <option value="clicks">Clicks</option>
                        <option value="impressions">Impressions</option>
                        <option value="revenue">Revenue</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Min Sample</label>
                      <input
                        type="number"
                        value={newExp.min_sample}
                        onChange={(e) => setNewExp({ ...newExp, min_sample: e.target.value })}
                        className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                      />
                    </div>
                  </div>
                  {newExp.variants.map((v, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="text-[10px] uppercase tracking-wider font-mono text-zinc-500 w-14 shrink-0">#{i + 1}</span>
                      <input
                        value={v}
                        onChange={(e) => {
                          const variants = [...newExp.variants];
                          variants[i] = e.target.value;
                          setNewExp({ ...newExp, variants });
                        }}
                        placeholder={`Variant ${i + 1} name`}
                        className="flex-1 border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                      />
                    </div>
                  ))}
                  <button
                    onClick={() => setNewExp({ ...newExp, variants: [...newExp.variants, ""] })}
                    className="text-[10px] uppercase tracking-wider text-[#2563EB] flex items-center gap-1"
                  >
                    <Plus size={12} /> Add variant
                  </button>
                  <button
                    onClick={startExperiment}
                    disabled={busy}
                    className="w-full bg-[#2563EB] text-white text-xs uppercase tracking-[0.15em] py-3 hover:bg-[#1D4ED8] disabled:opacity-50"
                  >
                    Start Experiment
                  </button>
                </div>
              </Section>
            </div>

            <div className="lg:col-span-2 space-y-4">
              {load ? <Loader label="Loading experiments" /> : exps.length === 0 ? (
                <Section><p className="text-sm text-zinc-500">No experiments yet. Design one on the left. The engine decides winners only when the minimum sample is reached, protecting you from false conclusions.</p></Section>
              ) : (
                exps.map((exp) => {
                  const total = (exp.variants || []).reduce((a, v) => a + (v.conversions || 0), 0);
                  return (
                    <div key={exp.id} className="border border-border bg-white">
                      <div className="px-5 py-3 border-b border-border flex items-center justify-between">
                        <div>
                          <div className="text-sm font-medium">{exp.name}</div>
                          <div className="text-[10px] uppercase tracking-wider font-mono text-zinc-500 mt-0.5">{fmt(exp.created_at)} · min sample {exp.min_sample}</div>
                        </div>
                        <span className={`text-[10px] uppercase tracking-wider font-mono px-2.5 py-1 border ${
                          exp.status === "winner" ? "border-emerald-500 text-emerald-600"
                          : exp.status === "loser" ? "border-red-300 text-red-500"
                          : exp.status === "needs_more_data" ? "border-amber-300 text-amber-600"
                          : "border-zinc-300 text-zinc-500"}`}>
                          {exp.status || "design"}
                        </span>
                      </div>
                      <div className="p-5 space-y-4">
                        <p className="text-xs text-zinc-600 italic">{exp.hypothesis}</p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {(exp.variants || []).map((v) => (
                            <div key={v.id || v.name} className={`border px-4 py-3 ${v.status === "winner" ? "border-emerald-500 bg-emerald-50/50" : "border-border"}`}>
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium">{v.name}</span>
                                {v.status && <span className="text-[10px] uppercase tracking-wider font-mono text-emerald-600">{v.status}</span>}
                              </div>
                              <div className="flex items-center gap-4 text-[11px] font-mono text-zinc-600">
                                <span>imp {v.impressions ?? 0}</span>
                                <span>clk {v.clicks ?? 0}</span>
                                <span className="text-[#2563EB]">conv {v.conversions ?? 0}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="flex items-center justify-between border-t border-border pt-3">
                          <span className="text-[11px] text-zinc-500 font-mono">total {exp.primary_metric}: {total}</span>
                          {exp.status === "design" && (
                            <div className="flex gap-2">
                              <button
                                onClick={() => decide(exp, "winner")}
                                disabled={busy}
                                className="border border-emerald-500 text-emerald-600 text-[10px] uppercase tracking-wider px-3 py-1.5 hover:bg-emerald-50 disabled:opacity-50"
                              >
                                Declare Winner
                              </button>
                              <button
                                onClick={() => decide(exp, "needs_more_data")}
                                disabled={busy}
                                className="border border-zinc-300 text-zinc-600 text-[10px] uppercase tracking-wider px-3 py-1.5 hover:bg-zinc-50 disabled:opacity-50"
                              >
                                Needs More Data
                              </button>
                              <button
                                onClick={() => decide(exp, "inconclusive")}
                                disabled={busy}
                                className="border border-zinc-300 text-zinc-500 text-[10px] uppercase tracking-wider px-3 py-1.5 hover:bg-zinc-50 disabled:opacity-50"
                              >
                                Inconclusive
                              </button>
                            </div>
                          )}
                        </div>
                        {exp.verdict_reasons?.length > 0 && (
                          <div className="text-[11px] text-zinc-500 border-t border-border pt-3 space-y-1">
                            {exp.verdict_reasons.map((r, i) => <div key={i}>· {r}</div>)}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </Fade>
      )}

      {tab === "governance" && (
        <Fade>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <Section title="Autonomy Level">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                  {levels.map(([key, label, desc]) => (
                    <button
                      key={key}
                      onClick={() => setLevel(key)}
                      disabled={busy}
                      className={`border px-4 py-3 text-left transition-all disabled:opacity-50 ${policy.autonomy_level === key ? "border-[#2563EB] bg-[#EFF6FF]" : "border-border hover:bg-zinc-50"}`}
                    >
                      <div className="text-sm font-medium">{label}</div>
                      <div className="text-[11px] text-zinc-500 mt-0.5">{desc}</div>
                      {policy.autonomy_level === key && (
                        <div className="text-[10px] uppercase tracking-wider font-mono text-[#2563EB] mt-2 flex items-center gap-1"><Check size={12} /> Active</div>
                      )}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-zinc-500">
                  Every autonomous action is policy-checked: spend caps, budget-change limits, allowed channels and approval thresholds. Changing policy is recorded in the immutable audit log.
                </p>
              </Section>

              <Section title="Emergency Kill Switch">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Power size={22} className={policy.kill_switch ? "text-red-500" : "text-zinc-400"} />
                    <div>
                      <div className="text-sm font-medium">{policy.kill_switch ? "Kill switch ACTIVE — all autonomous actions paused" : "Autonomy operational"}</div>
                      <div className="text-[11px] text-zinc-500 mt-0.5">One click stops every agent action immediately. Human workflows are never affected.</div>
                    </div>
                  </div>
                  <button
                    onClick={toggleKill}
                    disabled={busy}
                    className={`text-xs uppercase tracking-[0.15em] px-5 py-2.5 border disabled:opacity-50 ${policy.kill_switch ? "border-emerald-500 text-emerald-600 hover:bg-emerald-50" : "border-red-400 text-red-500 hover:bg-red-50"}`}
                  >
                    {policy.kill_switch ? "Restore Autonomy" : "Activate Kill Switch"}
                  </button>
                </div>
              </Section>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-0 border border-border bg-white">
                <div className="p-4 border-r border-b border-border">
                  <div className="text-[10px] uppercase tracking-[0.15em] text-zinc-500 mb-2">Current Level</div>
                  <div className="font-mono text-sm text-zinc-950">{policy.autonomy_level?.replace(/_/g, " ")}</div>
                </div>
                <div className="p-4 border-b border-border">
                  <div className="text-[10px] uppercase tracking-[0.15em] text-zinc-500 mb-2">Kill Switch</div>
                  <div className={`font-mono text-sm ${policy.kill_switch ? "text-red-500" : "text-emerald-600"}`}>{policy.kill_switch ? "ON" : "OFF"}</div>
                </div>
                <div className="p-4 border-r border-border">
                  <div className="text-[10px] uppercase tracking-[0.15em] text-zinc-500 mb-2">Daily Spend Cap</div>
                  <div className="font-mono text-sm">${policy.max_daily_spend ?? "—"}</div>
                </div>
                <div className="p-4">
                  <div className="text-[10px] uppercase tracking-[0.15em] text-zinc-500 mb-2">Budget Δ Cap</div>
                  <div className="font-mono text-sm">±{policy.max_budget_change_pct ?? 25}%</div>
                </div>
              </div>
              <Section title="Policy Rules">
                <ul className="space-y-2 text-xs text-zinc-600">
                  <li className="flex gap-2"><ShieldCheck size={14} className="text-[#2563EB] shrink-0" /> Approval required above set amount thresholds</li>
                  <li className="flex gap-2"><ShieldCheck size={14} className="text-[#2563EB] shrink-0" /> Channel and country allow-lists enforced</li>
                  <li className="flex gap-2"><ShieldCheck size={14} className="text-[#2563EB] shrink-0" /> All autonomous actions logged with correlation IDs</li>
                  <li className="flex gap-2"><Warning size={14} className="text-amber-500 shrink-0" /> Kill switch overrides every level instantly</li>
                </ul>
              </Section>
            </div>
          </div>
        </Fade>
      )}

      {tab === "events" && (
        <Fade>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Section title="Marketing Events (append-only)">
              {load ? <Loader label="Loading events" /> : events.length === 0 ? (
                <p className="text-sm text-zinc-500">No events yet. Events are recorded automatically as the engine operates.</p>
              ) : (
                <div className="space-y-1 max-h-[520px] overflow-y-auto">
                  {events.map((ev) => (
                    <div key={ev.id} className="flex items-start gap-3 border-b border-border/60 py-2">
                      <span className="font-mono text-[10px] uppercase tracking-wider text-[#2563EB] w-40 shrink-0 pt-0.5">{ev.event_type}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] text-zinc-700 truncate">{JSON.stringify(ev.payload || {})}</div>
                        <div className="text-[10px] font-mono text-zinc-400 mt-0.5">
                          {ev.actor_type} · {ev.entity_type || ""} {ev.entity_id ? `#${String(ev.entity_id).slice(0, 8)}` : ""} · {fmt(ev.created_at)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Section>
            <Section title="Audit Log (immutable)">
              {load ? <Loader label="Loading audit log" /> : (
                <AuditFeed />
              )}
            </Section>
          </div>
        </Fade>
      )}
    </div>
  );
}

function AuditFeed() {
  const [entries, setEntries] = useState([]);
  const [load, setLoad] = useState(true);
  useEffect(() => {
    api.get("/audit").then((r) => { setEntries(r.data); setLoad(false); }).catch(() => setLoad(false));
  }, []);
  const fmt = (iso) => {
    try {
      return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch {
      return iso;
    }
  };
  if (load) return <Loader label="Loading audit log" />;
  if (entries.length === 0)
    return <p className="text-sm text-zinc-500">No audit entries yet. Governance actions are recorded here permanently.</p>;
  return (
    <div className="space-y-1 max-h-[520px] overflow-y-auto">
      {entries.map((e) => (
        <div key={e.id} className="flex items-start gap-3 border-b border-border/60 py-2">
          <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500 w-36 shrink-0 pt-0.5">{e.action}</span>
          <div className="flex-1 min-w-0">
            <div className="text-[11px] text-zinc-700 truncate">{JSON.stringify(e.detail || {})}</div>
            <div className="text-[10px] font-mono text-zinc-400 mt-0.5">{e.actor_type} · {fmt(e.created_at)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
