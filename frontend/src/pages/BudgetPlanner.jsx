import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { useClient } from "@/context/ClientContext";
import { useCurrency } from "@/context/CurrencyContext";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import { Sparkle, TreeStructure, Megaphone, ChartPieSlice } from "@phosphor-icons/react";
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";

const PERIODS = ["Monthly", "Quarterly", "Annual"];
const tip = { contentStyle: { background: "#0A0A0A", border: "1px solid #27272A", borderRadius: 0, fontSize: 12, fontFamily: "JetBrains Mono" }, labelStyle: { color: "#A1A1AA" } };

export default function BudgetPlanner() {
  const { activeClientId } = useClient();
  const { format, currency } = useCurrency();
  const [form, setForm] = useState({ total_budget: "", period: "Monthly", primary_goal: "Generate qualified leads", notes: "" });
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState(null);
  const [history, setHistory] = useState([]);

  const loadHistory = () => {
    const q = activeClientId ? `?client_id=${activeClientId}` : "";
    api.get(`/budget/plans${q}`).then((r) => setHistory(r.data)).catch(() => {});
  };
  useEffect(() => { loadHistory(); }, [activeClientId]);

  const generate = async () => {
    if (!form.total_budget) return toast.error("Enter a total budget");
    setBusy(true); setPlan(null);
    try {
      const { data } = await api.post("/budget/plan", { ...form, total_budget: parseFloat(form.total_budget), client_id: activeClientId || null });
      setPlan(data.result);
      toast.success("SEO-led budget plan ready");
      loadHistory();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Budget Optimizer · SEO-Led"
        title="Budget Planner"
        description="An SEO-first allocation engine — organic search & content form the foundation, backed by paid marketing to accelerate lead flow. Amounts shown in your workspace currency."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <Section title="Plan Inputs">
            <div className="space-y-4">
              <div>
                <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Total Budget ({currency})</label>
                <input type="number" value={form.total_budget} onChange={(e) => setForm({ ...form, total_budget: e.target.value })} data-testid="budget-total"
                  className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200" />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Period</label>
                <select value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} data-testid="budget-period"
                  className="w-full bg-white border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200">
                  {PERIODS.map((p) => <option key={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Primary Goal</label>
                <input value={form.primary_goal} onChange={(e) => setForm({ ...form, primary_goal: e.target.value })} data-testid="budget-goal"
                  className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200" />
              </div>
              <button onClick={generate} disabled={busy} data-testid="generate-budget-btn"
                className="w-full flex items-center justify-center gap-2 bg-[#2563EB] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors duration-200">
                <Sparkle size={16} weight="fill" /> {busy ? "Optimizing" : "Generate Plan"}
              </button>
            </div>
          </Section>
        </div>

        <div className="lg:col-span-2">
          {busy && <Section><Loader label="Budget Agent is optimizing allocation" /></Section>}
          {!busy && !plan && <Section><div className="text-center py-16 text-zinc-500"><ChartPieSlice size={40} className="mx-auto mb-4 text-zinc-700" /><div className="text-sm">Your SEO-led budget allocation will appear here.</div></div></Section>}
          {plan && !plan._error && <PlanView plan={plan} format={format} />}
        </div>
      </div>
    </div>
  );
}

function PlanView({ plan, format }) {
  const allocations = plan.allocations || [];
  const split = [
    { name: "Organic / SEO", value: plan.seo_share_pct || allocations.filter(a => a.type === "Organic").reduce((s, a) => s + (a.pct || 0), 0), fill: "#34C759" },
    { name: "Paid", value: plan.paid_share_pct || allocations.filter(a => a.type !== "Organic").reduce((s, a) => s + (a.pct || 0), 0), fill: "#2563EB" },
  ];
  return (
    <Fade><div className="space-y-6">
      <Section title="Strategy">
        <p className="text-sm text-zinc-700 leading-relaxed">{plan.strategy_summary}</p>
        {plan.philosophy && <div className="mt-3 border-l-2 border-[#34C759] bg-[#34C759]/5 px-4 py-3 text-sm text-zinc-700"><TreeStructure size={14} className="inline mr-2 text-[#34C759]" />{plan.philosophy}</div>}
      </Section>

      <div className="grid grid-cols-3 border-t border-l border-border">
        <div className="p-5 border-r border-b border-border"><div className="text-xs uppercase tracking-wider text-zinc-500 mb-2">SEO / Organic</div><div className="font-mono text-3xl text-[#34C759]">{split[0].value}%</div></div>
        <div className="p-5 border-r border-b border-border"><div className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Paid Support</div><div className="font-mono text-3xl text-[#2563EB]">{split[1].value}%</div></div>
        <div className="p-5 border-r border-b border-border"><div className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Est. Leads</div><div className="font-mono text-3xl">{plan.expected_total_leads ?? "—"}</div><div className="text-xs text-zinc-500 mt-1">CAC {plan.blended_cac ? format(plan.blended_cac) : "—"}</div></div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Section title="Split" className="lg:col-span-1">
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={split} dataKey="value" innerRadius={45} outerRadius={70} paddingAngle={2}>
                  {split.map((s, i) => <Cell key={i} fill={s.fill} />)}
                </Pie>
                <Tooltip {...tip} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-4 text-xs">
            {split.map((s) => <div key={s.name} className="flex items-center gap-1.5"><span className="w-2 h-2" style={{ background: s.fill }} />{s.name}</div>)}
          </div>
        </Section>

        <Section title="Allocation" className="lg:col-span-2">
          <div className="space-y-3">
            {allocations.map((a, i) => (
              <div key={i}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 ${a.type === "Organic" ? "bg-[#34C759]" : "bg-[#2563EB]"}`} />
                    {a.channel} <span className="text-[10px] uppercase text-zinc-500">{a.type}</span>
                  </span>
                  <span className="font-mono">{format(a.amount)} · {a.pct}%</span>
                </div>
                <div className="h-1.5 bg-zinc-100"><div className="h-full" style={{ width: `${a.pct}%`, background: a.type === "Organic" ? "#34C759" : "#2563EB" }} /></div>
                {a.rationale && <div className="text-xs text-zinc-500 mt-1">{a.rationale} {a.expected_leads ? `· ~${a.expected_leads} leads` : ""}</div>}
              </div>
            ))}
          </div>
        </Section>
      </div>

      {plan.ramp?.length > 0 && (
        <Section title="SEO vs Paid Ramp">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={plan.ramp}>
                <CartesianGrid stroke="#18181B" vertical={false} />
                <XAxis dataKey="month" stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip {...tip} cursor={{ fill: "#141414" }} />
                <Bar dataKey="seo_pct" stackId="a" fill="#34C759" name="SEO %" />
                <Bar dataKey="paid_pct" stackId="a" fill="#2563EB" name="Paid %" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
      )}
    </div></Fade>
  );
}
