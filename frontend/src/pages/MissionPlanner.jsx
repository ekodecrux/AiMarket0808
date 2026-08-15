import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section, StatCard } from "@/components/common";
import { toast } from "sonner";
import {
  CrosshairSimple, Target, Users, ChartPie, Megaphone, ListChecks, Gauge,
  Rocket, CaretRight, Check, X as XIcon, SealCheck, Sparkle,
} from "@phosphor-icons/react";

export default function MissionPlanner() {
  const [missions, setMissions] = useState([]);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  const [load, setLoad] = useState(true);
  const [planGen, setPlanGen] = useState(false);
  const [form, setForm] = useState({
    objective: "", target_market: "", offer: "", budget: "",
    geography: "", timeline: "90 days", constraints: "",
  });

  const loadList = () =>
    api.get("/missions").then((r) => {
      setMissions(r.data);
      if (r.data.length && !active) setActive(r.data[0]);
      setLoad(false);
    }).catch(() => setLoad(false));

  useEffect(() => { loadList(); }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const create = async () => {
    if (form.objective.trim().length < 10)
      return toast.error("Describe your goal more fully — include target market and offer.");
    setPlanGen(true);
    try {
      const payload = { ...form };
      if (form.budget) payload.budget = parseFloat(form.budget);
      const { data } = await api.post("/missions", payload);
      toast.success("Mission plan generated — review below");
      setActive(data);
      loadList();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setPlanGen(false);
    }
  };

  const approve = async (m, actionIndex = null) => {
    setBusy(true);
    try {
      const url = actionIndex !== null
        ? `/missions/${m.id}/actions/${actionIndex}/approve`
        : `/missions/${m.id}/approve`;
      const { data } = await api.post(url, {});
      toast.success(actionIndex !== null ? "Action approved" : "Mission approved — execution enabled");
      setActive(data);
      loadList();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const reject = async (m) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/missions/${m.id}/reject`, {});
      toast("Mission plan rejected", { icon: "🔄" });
      setActive(data);
      loadList();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const plan = active?.plan || {};
  const steps = plan.execution_plan || [];
  const channels = plan.channel_mix || [];

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Module B — Marketing Mission Planner"
        title="Mission Planner"
        description="State a business goal in plain language. The engine returns a complete, machine-readable mission plan: ICP, channel mix, content cadence, lead capture, KPIs and budget forecast. Every plan requires human approval before execution."
        action={
          <div className="hidden sm:flex items-center gap-2 text-[10px] uppercase tracking-wider font-mono text-zinc-500 border border-border px-3 py-1.5">
            <SealCheck size={13} className="text-[#2563EB]" /> Human-in-the-loop approval
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left — input */}
        <div className="space-y-4">
          <Section title="Define the Mission">
            <div className="space-y-4">
              <div>
                <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">
                  Business Goal <span className="text-red-500">*</span>
                </label>
                <textarea
                  rows={4}
                  value={form.objective}
                  onChange={set("objective")}
                  placeholder="e.g. Generate 100 qualified leads for our monthly AI tutoring subscription among parents in the US within 90 days, budget $3,000."
                  className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB] resize-none"
                />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Target Market</label>
                <input
                  value={form.target_market}
                  onChange={set("target_market")}
                  placeholder="e.g. Parents of K-12 students"
                  className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Offer</label>
                <input
                  value={form.offer}
                  onChange={set("offer")}
                  placeholder="e.g. $99/month 1-on-1 tutoring subscription"
                  className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Budget (USD)</label>
                  <input
                    type="number"
                    value={form.budget}
                    onChange={set("budget")}
                    placeholder="3000"
                    className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
                <div>
                  <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Geography</label>
                  <input
                    value={form.geography}
                    onChange={set("geography")}
                    placeholder="e.g. United States"
                    className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
              </div>
              <button
                onClick={create}
                disabled={planGen || busy}
                className="w-full bg-[#2563EB] text-white text-xs uppercase tracking-[0.15em] py-3 hover:bg-[#1D4ED8] disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {planGen ? (
                  <><CircleNotch size={15} className="animate-spin" /> Planning Mission…</>
                ) : (
                  <><Rocket size={15} /> Generate Mission Plan</>
                )}
              </button>
            </div>
          </Section>

          <Section title="Mission History">
            {missions.length === 0 ? (
              <div className="text-xs text-zinc-500 font-mono">No missions yet.</div>
            ) : (
              <div className="space-y-1">
                {missions.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => setActive(m)}
                    className={`w-full text-left px-3 py-2.5 border transition-all ${active?.id === m.id ? "border-[#2563EB] bg-[#EFF6FF]" : "border-border hover:bg-zinc-50"}`}
                  >
                    <div className="text-xs font-medium text-zinc-900 truncate">{m.objective}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`inline-block w-1.5 h-1.5 ${m.status === "Approved" ? "bg-emerald-500" : m.status === "Rejected" ? "bg-red-500" : "bg-amber-400"}`} />
                      <span className="text-[10px] uppercase tracking-wider font-mono text-zinc-500">{m.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </Section>
        </div>

        {/* Center — plan */}
        <div className="lg:col-span-2 space-y-4">
          {load && <Loader label="Loading missions" />}
          {!load && !active && (
            <Section title="Welcome">
              <p className="text-sm text-zinc-500">Define a mission on the left. The engine will design the full plan against your Business Brain context.</p>
            </Section>
          )}
          {!load && active && (
            <Fade>
              <div className="flex items-center justify-between border-b-2 border-zinc-950 pb-3 mb-4">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 font-mono">Mission {active.id?.slice(0, 8)}</div>
                  <div className="text-lg font-light mt-1">{active.objective}</div>
                </div>
                <span className={`text-[10px] uppercase tracking-wider font-mono px-2.5 py-1 border ${active.status === "Approved" ? "border-emerald-500 text-emerald-600" : active.status === "Rejected" ? "border-red-500 text-red-500" : "border-amber-400 text-amber-600"}`}>
                  {active.status}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                {plan.icp && (
                  <Section title="Ideal Customer Profile" className="h-full">
                    <div className="space-y-3 text-sm">
                      <div>
                        <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">{plan.icp.title || "Profile"}</div>
                        <p className="text-zinc-700">{plan.icp.company_profile}</p>
                      </div>
                      <div className="flex items-start gap-2">
                        <Users size={15} className="text-[#2563EB] mt-0.5 shrink-0" />
                        <span className="text-zinc-700">Decision maker: <b>{plan.icp.decision_maker}</b></span>
                      </div>
                      {(plan.icp.pain_points || []).map((p, i) => (
                        <div key={i} className="flex items-start gap-2">
                          <XIcon size={14} className="text-red-400 mt-0.5 shrink-0" />
                          <span className="text-zinc-600 text-xs">{p}</span>
                        </div>
                      ))}
                      {(plan.icp.buying_triggers || []).map((p, i) => (
                        <div key={i} className="flex items-start gap-2">
                          <Check size={14} className="text-emerald-500 mt-0.5 shrink-0" />
                          <span className="text-zinc-600 text-xs">{p}</span>
                        </div>
                      ))}
                    </div>
                  </Section>
                )}
                {channels.length > 0 && (
                  <Section title="Channel Mix" className="h-full">
                    <div className="space-y-3">
                      {channels.map((c, i) => (
                        <div key={i}>
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="font-medium">{c.channel}</span>
                            <span className="font-mono">{c.allocation_pct}%</span>
                          </div>
                          <div className="h-1.5 bg-zinc-100">
                            <div className="h-full bg-[#2563EB]" style={{ width: `${c.allocation_pct}%` }} />
                          </div>
                          <div className="text-[11px] text-zinc-500 mt-1">{c.rationale}</div>
                        </div>
                      ))}
                    </div>
                  </Section>
                )}
              </div>

              {plan.forecast && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-0 border border-border bg-white mb-4">
                  <StatCard
                    label="Forecasted Leads"
                    value={`${plan.forecast.expected_leads_range?.[0] ?? "?"}–${plan.forecast.expected_leads_range?.[1] ?? "?"}`}
                    sub={`Confidence: ${plan.forecast.confidence}`}
                  />
                  <StatCard
                    label="Qualified Pipeline"
                    value={`${plan.forecast.expected_qualified_range?.[0] ?? "?"}–${plan.forecast.expected_qualified_range?.[1] ?? "?"}`}
                  />
                  <StatCard
                    label="Content Cadence"
                    value={(plan.content_plan || []).length}
                    sub="pieces planned"
                  />
                  <StatCard
                    label="KPI Targets"
                    value={(plan.measurement_plan || []).length}
                    sub="metrics tracked"
                  />
                </div>
              )}

              {(plan.offer_strategy || plan.lead_plan || plan.conversion_plan) && (
                <Section title="Funnel Logic">
                  <div className="space-y-4 text-sm">
                    {plan.offer_strategy && (
                      <div className="flex gap-3">
                        <Target size={17} className="text-[#2563EB] shrink-0 mt-0.5" />
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Offer Strategy</div>
                          <p className="text-zinc-700">{plan.offer_strategy}</p>
                        </div>
                      </div>
                    )}
                    {plan.lead_plan && (
                      <div className="flex gap-3">
                        <Users size={17} className="text-[#2563EB] shrink-0 mt-0.5" />
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Lead Capture & Qualification</div>
                          <p className="text-zinc-700">{plan.lead_plan}</p>
                        </div>
                      </div>
                    )}
                    {plan.conversion_plan && (
                      <div className="flex gap-3">
                        <CaretRight size={17} className="text-[#2563EB] shrink-0 mt-0.5" />
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Conversion Path</div>
                          <p className="text-zinc-700">{plan.conversion_plan}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </Section>
              )}

              {steps.length > 0 && (
                <Section
                  title="Execution Plan"
                  className={active.status !== "Approved" ? "" : "border-emerald-500"}
                >
                  <div className="space-y-2">
                    {steps.map((s, i) => (
                      <div key={i} className={`flex items-start gap-3 border px-4 py-3 ${s.approved ? "border-emerald-500 bg-emerald-50/50" : active.status === "Approved" ? "border-border bg-white" : "border-border bg-amber-50/40"}`}>
                        <div className="font-mono text-xs text-zinc-500 w-8 pt-0.5 shrink-0">#{i + 1}</div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-zinc-900">{s.action}</div>
                          <div className="flex flex-wrap items-center gap-2 mt-1 text-[10px] uppercase tracking-wider font-mono text-zinc-500">
                            <span className="flex items-center gap-1"><Megaphone size={11} /> {s.channel || "multi"}</span>
                            <span>Day {s.day_range || "?"}</span>
                            <span className={s.owner === "agent" ? "text-[#2563EB]" : "text-zinc-500"}>
                              {s.owner === "agent" ? "AUTONOMOUS" : "HUMAN"}
                            </span>
                            {s.approved && <span className="text-emerald-600 flex items-center gap-1"><Check size={11} /> APPROVED</span>}
                          </div>
                        </div>
                        {active.status === "Draft" && !s.approved && (
                          <button
                            onClick={() => approve(active, i)}
                            disabled={busy}
                            className="shrink-0 text-[10px] uppercase tracking-wider border border-[#2563EB] text-[#2563EB] px-2.5 py-1.5 hover:bg-[#2563EB] hover:text-white disabled:opacity-50"
                          >
                            Approve
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {(plan.content_plan || []).length > 0 && (
                  <Section title="Content Plan">
                    <ul className="space-y-2">
                      {(plan.content_plan || []).slice(0, 8).map((c, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <ListChecks size={15} className="text-[#2563EB] shrink-0 mt-0.5" />
                          <span><span className="text-[10px] uppercase tracking-wider font-mono text-zinc-500">{c.type}</span> — {c.title}</span>
                        </li>
                      ))}
                    </ul>
                  </Section>
                )}
                {(plan.measurement_plan || []).length > 0 && (
                  <Section title="Measurement Plan">
                    <ul className="space-y-2">
                      {(plan.measurement_plan || []).map((m, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <Gauge size={15} className="text-[#2563EB] shrink-0 mt-0.5" />
                          <span><b>{m.metric}</b> → {m.target} <span className="text-zinc-500">({m.period})</span></span>
                        </li>
                      ))}
                    </ul>
                  </Section>
                )}
                {(plan.risks || []).length > 0 && (
                  <Section title="Risks" className="md:col-span-2">
                    <ul className="space-y-1.5">
                      {plan.risks.map((r, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-zinc-600">
                          <CrosshairSimple size={15} className="text-amber-500 shrink-0 mt-0.5" /> {r}
                        </li>
                      ))}
                    </ul>
                  </Section>
                )}
              </div>

              {active.status === "Draft" && (
                <div className="flex gap-3 mt-4 border-t border-border pt-4">
                  <button
                    onClick={() => approve(active)}
                    disabled={busy}
                    className="bg-emerald-600 text-white text-xs uppercase tracking-[0.15em] px-6 py-3 hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2"
                  >
                    <Check size={15} /> Approve Mission
                  </button>
                  <button
                    onClick={() => reject(active)}
                    disabled={busy}
                    className="border border-zinc-300 text-zinc-600 text-xs uppercase tracking-[0.15em] px-6 py-3 hover:bg-zinc-50 disabled:opacity-50"
                  >
                    Reject & Regenerate
                  </button>
                </div>
              )}
              {active.status === "Approved" && (
                <div className="flex items-center gap-2 mt-4 border border-emerald-500 bg-emerald-50 px-4 py-3 text-xs text-emerald-700">
                  <Sparkle size={15} /> Mission approved. The autonomous engine will execute approved steps within policy limits and record every action.
                </div>
              )}
            </Fade>
          )}
        </div>
      </div>
    </div>
  );
}
