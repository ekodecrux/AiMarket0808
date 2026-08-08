import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import { Sparkle, Target, Calendar, ChartPie, Users, ListChecks } from "@phosphor-icons/react";

const FIELDS = [
  ["industry", "Industry", "e.g. B2B SaaS, Fintech"],
  ["product", "Product / Service", "e.g. AI analytics platform"],
  ["competitors", "Competitors", "e.g. Tableau, PowerBI"],
  ["budget", "Budget", "e.g. $50,000 / quarter"],
  ["geography", "Geography", "e.g. North America, EU"],
  ["goals", "Goals", "e.g. 200 qualified leads, reduce CAC 20%"],
];

export default function Strategy() {
  const [form, setForm] = useState({ industry: "", product: "", competitors: "", budget: "", geography: "", goals: "" });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  const loadHistory = () => api.get("/strategy").then((r) => setHistory(r.data)).catch(() => {});
  useEffect(() => { loadHistory(); }, []);

  const generate = async () => {
    if (!form.industry || !form.product) return toast.error("Industry and product are required");
    setBusy(true);
    setResult(null);
    try {
      const { data } = await api.post("/strategy/generate", form);
      setResult(data.result);
      toast.success("Strategy generated");
      loadHistory();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="AI Strategy Generator"
        title="Autonomous Marketing Plan"
        description="Feed the engine your business context. It returns a complete GTM roadmap, personas, channel mix, budget split and KPIs."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Input */}
        <div className="lg:col-span-1 space-y-4">
          <Section title="Business Context">
            <div className="space-y-4">
              {FIELDS.map(([key, label, ph]) => (
                <div key={key}>
                  <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{label}</label>
                  {key === "goals" ? (
                    <textarea
                      rows={3}
                      value={form[key]}
                      placeholder={ph}
                      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                      data-testid={`strategy-${key}`}
                      className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200 resize-none"
                    />
                  ) : (
                    <input
                      value={form[key]}
                      placeholder={ph}
                      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                      data-testid={`strategy-${key}`}
                      className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200"
                    />
                  )}
                </div>
              ))}
              <button
                onClick={generate}
                disabled={busy}
                data-testid="generate-strategy-btn"
                className="w-full flex items-center justify-center gap-2 bg-[#FF3B30] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200"
              >
                <Sparkle size={16} weight="fill" /> {busy ? "Generating" : "Generate Strategy"}
              </button>
            </div>
          </Section>

          {history.length > 0 && (
            <Section title={`History · ${history.length}`}>
              <div className="space-y-2">
                {history.map((h) => (
                  <button
                    key={h.id}
                    onClick={() => setResult(h.result)}
                    className="w-full text-left px-3 py-2 border border-zinc-200 hover:border-zinc-600 text-sm transition-colors duration-200"
                    data-testid={`strategy-history-${h.id}`}
                  >
                    <div className="truncate">{h.input?.product || "Strategy"}</div>
                    <div className="text-xs text-zinc-500">{h.input?.industry}</div>
                  </button>
                ))}
              </div>
            </Section>
          )}
        </div>

        {/* Output */}
        <div className="lg:col-span-2">
          {busy && <Section><Loader label="CMO Agent is building your roadmap" /></Section>}
          {!busy && !result && (
            <Section>
              <div className="text-center py-16 text-zinc-500">
                <Target size={40} className="mx-auto mb-4 text-zinc-700" />
                <div className="text-sm">Your AI-generated marketing roadmap will appear here.</div>
              </div>
            </Section>
          )}
          {result && <StrategyResult result={result} />}
        </div>
      </div>
    </div>
  );
}

function StrategyResult({ result }) {
  if (result._error) {
    return <Section title="Raw Output"><pre className="text-xs text-zinc-500 whitespace-pre-wrap">{result._raw}</pre></Section>;
  }
  return (
    <Fade>
      <div className="space-y-6">
        <Section title="Executive Summary">
          <p className="text-sm text-zinc-700 leading-relaxed">{result.executive_summary}</p>
          {result.gtm_strategy && <p className="text-sm text-zinc-500 leading-relaxed mt-3">{result.gtm_strategy}</p>}
          {result.target_audience && (
            <div className="mt-4 pt-4 border-t border-border">
              <div className="text-xs uppercase tracking-wider text-zinc-500 mb-1">Target Audience</div>
              <p className="text-sm text-zinc-700">{result.target_audience}</p>
            </div>
          )}
        </Section>

        {result.personas?.length > 0 && (
          <Section title={<span className="flex items-center gap-2"><Users size={14} /> Customer Personas</span>}>
            <div className="grid sm:grid-cols-2 gap-4">
              {result.personas.map((p, i) => (
                <div key={i} className="border border-zinc-200 p-4">
                  <div className="font-display text-lg">{p.name}</div>
                  <div className="text-xs text-[#FF3B30] uppercase tracking-wider mb-2">{p.role}</div>
                  <div className="text-xs text-zinc-500"><span className="text-zinc-500">Pain: </span>{p.pain_points}</div>
                  <div className="text-xs text-zinc-500 mt-1"><span className="text-zinc-500">Channels: </span>{p.channels}</div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {result.channel_mix?.length > 0 && (
          <Section title={<span className="flex items-center gap-2"><ChartPie size={14} /> Channel Mix</span>}>
            <div className="space-y-3">
              {result.channel_mix.map((c, i) => (
                <div key={i}>
                  <div className="flex justify-between text-sm mb-1">
                    <span>{c.channel}</span>
                    <span className="font-mono text-[#FF3B30]">{c.allocation_pct}%</span>
                  </div>
                  <div className="h-1.5 bg-zinc-100"><div className="h-full bg-[#FF3B30]" style={{ width: `${c.allocation_pct}%` }} /></div>
                  <div className="text-xs text-zinc-500 mt-1">{c.rationale}</div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {result.budget_allocation?.length > 0 && (
          <Section title="Budget Allocation">
            <table className="w-full text-sm">
              <thead><tr className="text-xs uppercase tracking-wider text-zinc-500 text-left border-b border-border">
                <th className="pb-2">Category</th><th className="pb-2 text-right">%</th><th className="pb-2 text-right">Amount</th>
              </tr></thead>
              <tbody>
                {result.budget_allocation.map((b, i) => (
                  <tr key={i} className="border-b border-zinc-900">
                    <td className="py-2">{b.category}</td>
                    <td className="py-2 text-right font-mono">{b.pct}%</td>
                    <td className="py-2 text-right font-mono text-zinc-500">{b.amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
        )}

        {result.campaign_calendar?.length > 0 && (
          <Section title={<span className="flex items-center gap-2"><Calendar size={14} /> Campaign Calendar</span>}>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {result.campaign_calendar.map((q, i) => (
                <div key={i} className="border border-zinc-200 p-3">
                  <div className="font-mono text-[#FF3B30] text-sm">{q.quarter}</div>
                  <div className="text-sm mt-1">{q.theme}</div>
                  <div className="text-xs text-zinc-500 mt-1">{q.key_campaigns}</div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {result.kpis?.length > 0 && (
          <Section title={<span className="flex items-center gap-2"><ListChecks size={14} /> KPI Targets</span>}>
            <div className="grid sm:grid-cols-2 gap-3">
              {result.kpis.map((kp, i) => (
                <div key={i} className="flex justify-between border border-zinc-200 px-3 py-2 text-sm">
                  <span className="text-zinc-500">{kp.metric}</span>
                  <span className="font-mono text-white">{kp.target}</span>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>
    </Fade>
  );
}
