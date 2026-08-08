import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import { Plus, ArrowsClockwise, Trash, Crosshair, TrendUp, X, ArrowSquareOut, Sparkle } from "@phosphor-icons/react";

export default function CompetitorRadar() {
  const [tab, setTab] = useState("competitors");
  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Competitor & Trend Intelligence"
        title="Market Radar"
        description="Live intelligence — NEXUS fetches real competitor websites and real industry news, then the AI analyzes them."
        action={
          <div className="flex border border-border">
            {[["competitors", "Competitors", Crosshair], ["trends", "Trend Discovery", TrendUp]].map(([id, label, Icon]) => (
              <button key={id} onClick={() => setTab(id)} data-testid={`radar-tab-${id}`}
                className={`flex items-center gap-2 px-4 py-2 text-xs uppercase tracking-wider transition-colors duration-200 ${tab === id ? "bg-[#FF3B30] text-white" : "text-zinc-500 hover:text-white"}`}>
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>
        }
      />
      {tab === "competitors" ? <Competitors /> : <Trends />}
    </div>
  );
}

function Competitors() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [rescanning, setRescanning] = useState(null);

  const load = () => { setLoading(true); api.get("/competitors").then((r) => setItems(r.data)).catch(() => {}).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const rescan = async (id) => { setRescanning(id); try { await api.post(`/competitors/${id}/rescan`); toast.success("Re-analyzed"); load(); } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); } finally { setRescanning(null); } };
  const del = async (id) => { await api.delete(`/competitors/${id}`); toast.success("Removed"); load(); };

  return (
    <div>
      <div className="flex justify-end mb-6">
        <button onClick={() => setShowForm(true)} data-testid="add-competitor-btn"
          className="flex items-center gap-2 bg-[#FF3B30] text-white px-4 py-2.5 text-sm uppercase tracking-wider hover:bg-[#D63026] transition-colors duration-200">
          <Plus size={16} /> Track Competitor
        </button>
      </div>

      {loading ? <Loader label="Loading competitors" /> : items.length === 0 ? (
        <Section><div className="text-center py-16 text-zinc-500 text-sm">No competitors tracked yet. Add a competitor URL and NEXUS will fetch and analyze their site live.</div></Section>
      ) : (
        <div className="space-y-6">
          {items.map((c) => {
            const a = c.analysis || {};
            return (
              <Fade key={c.id}>
                <div className="border border-border bg-white" data-testid={`competitor-${c.id}`}>
                  <div className="flex items-start justify-between p-5 border-b border-border">
                    <div>
                      <div className="font-display text-xl">{c.name}</div>
                      <a href={c.url.startsWith("http") ? c.url : `https://${c.url}`} target="_blank" rel="noreferrer" className="text-xs text-[#007AFF] hover:underline flex items-center gap-1 mt-1">{c.url} <ArrowSquareOut size={11} /></a>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={() => rescan(c.id)} disabled={rescanning === c.id} data-testid={`rescan-${c.id}`}
                        className="flex items-center gap-1 text-xs border border-zinc-200 px-3 py-1.5 hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors duration-200 disabled:opacity-40">
                        <ArrowsClockwise size={14} className={rescanning === c.id ? "animate-spin" : ""} /> {rescanning === c.id ? "Scanning" : "Rescan"}
                      </button>
                      <button onClick={() => del(c.id)} className="text-zinc-500 hover:text-[#FF3B30] transition-colors duration-200"><Trash size={16} /></button>
                    </div>
                  </div>
                  <div className="p-5 space-y-4">
                    {a.positioning && <Row label="Positioning" value={a.positioning} />}
                    {a.value_proposition && <Row label="Value Prop" value={a.value_proposition} />}
                    {a.target_audience && <Row label="Target Audience" value={a.target_audience} />}
                    {a.pricing_signals && <Row label="Pricing Signals" value={a.pricing_signals} />}
                    <div className="grid sm:grid-cols-2 gap-4 pt-2">
                      {a.strengths?.length > 0 && <Chips title="Strengths" items={a.strengths} color="#34C759" />}
                      {a.weaknesses?.length > 0 && <Chips title="Weaknesses / Gaps" items={a.weaknesses} color="#FFCC00" />}
                      {a.key_messaging?.length > 0 && <Chips title="Key Messaging" items={a.key_messaging} color="#A1A1AA" />}
                      {a.products?.length > 0 && <Chips title="Products" items={a.products} color="#007AFF" />}
                    </div>
                    {a.counter_strategy && (
                      <div className="mt-2 border-l-2 border-[#FF3B30] bg-[#FF3B30]/5 px-4 py-3">
                        <div className="text-xs uppercase tracking-wider text-[#FF3B30] mb-1">How to Win</div>
                        <div className="text-sm text-zinc-700">{a.counter_strategy}</div>
                      </div>
                    )}
                    {a._error && <pre className="text-xs text-zinc-500 whitespace-pre-wrap">{a._raw}</pre>}
                    <div className="text-[11px] font-mono text-zinc-500 pt-2">Last scanned {new Date(c.updated_at).toLocaleString()} · {c.history?.length || 1} snapshot(s)</div>
                  </div>
                </div>
              </Fade>
            );
          })}
        </div>
      )}

      {showForm && <CompForm onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />}
    </div>
  );
}

function CompForm({ onClose, onSaved }) {
  const [form, setForm] = useState({ name: "", url: "" });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!form.name || !form.url) return toast.error("Name and URL required");
    setBusy(true);
    try { await api.post("/competitors", form); toast.success("Competitor analyzed"); onSaved(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white border border-border w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="font-display text-lg">Track Competitor</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors duration-200"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Competitor Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="competitor-name"
              className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Website URL</label>
            <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} data-testid="competitor-url" placeholder="competitor.com"
              className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200" />
          </div>
          <p className="text-xs text-zinc-500">NEXUS fetches the live site and analyzes it with AI. Takes ~10-25s.</p>
          <button onClick={submit} disabled={busy} data-testid="save-competitor-btn"
            className="w-full flex items-center justify-center gap-2 bg-[#FF3B30] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">
            <Sparkle size={16} weight="fill" /> {busy ? "Analyzing" : "Analyze"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Trends() {
  const [industry, setIndustry] = useState("");
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState(null);

  const run = async () => {
    if (!industry) return toast.error("Enter an industry");
    setBusy(true); setData(null);
    try { const { data } = await api.post("/trends/discover", { industry }); setData(data); toast.success("Trends discovered"); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Section title="Discover Trends" className="lg:col-span-1 self-start">
        <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Industry / Topic</label>
        <input value={industry} onChange={(e) => setIndustry(e.target.value)} data-testid="trend-industry" placeholder="e.g. Fintech, B2B SaaS"
          className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200 mb-4" />
        <button onClick={run} disabled={busy} data-testid="discover-trends-btn"
          className="w-full flex items-center justify-center gap-2 bg-[#FF3B30] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">
          <TrendUp size={16} /> {busy ? "Scanning news" : "Discover"}
        </button>
        <p className="text-xs text-zinc-500 mt-3">Pulls real Google News headlines and analyzes them with AI.</p>
      </Section>

      <div className="lg:col-span-2">
        {busy && <Section><Loader label="Fetching live news & analyzing" /></Section>}
        {!busy && !data && <Section><div className="text-center py-16 text-zinc-500"><TrendUp size={40} className="mx-auto mb-4 text-zinc-700" /><div className="text-sm">Enter an industry to discover live trends.</div></div></Section>}
        {data && !data._error && (
          <Fade><div className="space-y-4">
            <Section title="Trend Summary">
              <p className="text-sm text-zinc-700 leading-relaxed">{data.summary}</p>
              {data.sentiment && <div className="mt-3 text-sm"><span className="text-zinc-500 uppercase text-xs tracking-wider">Sentiment · </span>{data.sentiment}</div>}
            </Section>
            {data.trending_topics?.length > 0 && (
              <Section title="Trending Topics">
                <div className="space-y-3">{data.trending_topics.map((t, i) => (
                  <div key={i} className="border border-zinc-200 p-3">
                    <div className="text-sm text-white">{t.topic}</div>
                    <div className="text-xs text-zinc-500 mt-1">{t.why_it_matters}</div>
                  </div>
                ))}</div>
              </Section>
            )}
            <div className="grid sm:grid-cols-2 gap-4">
              {data.keywords?.length > 0 && <Section title="Keywords"><div className="flex flex-wrap gap-2">{data.keywords.map((k, i) => <span key={i} className="text-xs font-mono text-zinc-700 border border-zinc-200 px-2 py-1">{k}</span>)}</div></Section>}
              {data.hashtags?.length > 0 && <Section title="Hashtags"><div className="flex flex-wrap gap-2">{data.hashtags.map((h, i) => <span key={i} className="text-xs font-mono text-[#007AFF] border border-[#007AFF]/30 px-2 py-1">{h}</span>)}</div></Section>}
            </div>
            {data.content_opportunities?.length > 0 && (
              <Section title="Content Opportunities"><ul className="space-y-2">{data.content_opportunities.map((o, i) => <li key={i} className="text-sm text-zinc-700 flex gap-2"><span className="text-[#FF3B30]">→</span> {o}</li>)}</ul></Section>
            )}
            {data.sources?.length > 0 && (
              <Section title="Live Sources">
                <div className="space-y-2">{data.sources.map((s, i) => (
                  <a key={i} href={s.link} target="_blank" rel="noreferrer" className="block text-xs text-zinc-500 hover:text-white transition-colors duration-200 truncate" data-testid={`trend-source-${i}`}>
                    · {s.title} <span className="text-zinc-500">{s.source && `— ${s.source}`}</span>
                  </a>
                ))}</div>
              </Section>
            )}
          </div></Fade>
        )}
      </div>
    </div>
  );
}

const Row = ({ label, value }) => (
  <div>
    <div className="text-xs uppercase tracking-wider text-zinc-500 mb-1">{label}</div>
    <div className="text-sm text-zinc-700">{value}</div>
  </div>
);

const Chips = ({ title, items, color }) => (
  <div>
    <div className="text-xs uppercase tracking-wider text-zinc-500 mb-2">{title}</div>
    <div className="flex flex-wrap gap-2">
      {items.map((it, i) => <span key={i} className="text-xs px-2 py-1 border" style={{ color, borderColor: `${color}40` }}>{it}</span>)}
    </div>
  </div>
);
