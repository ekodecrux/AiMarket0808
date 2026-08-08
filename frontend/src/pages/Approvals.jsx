import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { useClient } from "@/context/ClientContext";
import { useCurrency } from "@/context/CurrencyContext";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import { Sparkle, CheckCircle, XCircle, Robot, Lightning } from "@phosphor-icons/react";

export default function Approvals() {
  const { activeClientId } = useClient();
  const { format } = useCurrency();
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(false);
  const [autopilot, setAutopilot] = useState(false);
  const [cfg, setCfg] = useState({ daily_proposals: 3, cap: 10, is_admin: false });

  const load = () => {
    const q = activeClientId ? `&client_id=${activeClientId}` : "";
    api.get(`/proposals?status=Pending${q}`).then((r) => setItems(r.data)).catch(() => setItems([]));
    const pq = activeClientId ? `?client_id=${activeClientId}` : "";
    api.get(`/flow/status${pq}`).then((r) => setAutopilot(r.data.autopilot)).catch(() => {});
    api.get(`/autopilot/config${pq}`).then((r) => setCfg(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, [activeClientId]);

  const setCadence = async (n) => {
    const next = Math.max(1, Math.min(n, cfg.cap));
    setCfg((c) => ({ ...c, daily_proposals: next }));
    try {
      const { data } = await api.post("/autopilot/config", { daily_proposals: next, client_id: activeClientId || null });
      setCfg(data);
      toast.success(`Autopilot will propose ${data.daily_proposals} campaign${data.daily_proposals > 1 ? "s" : ""} per day`);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); load(); }
  };

  const setCap = async (n) => {
    const next = Math.max(1, Math.min(n, 50));
    setCfg((c) => ({ ...c, cap: next }));
    try {
      const { data } = await api.post("/autopilot/config", { cap: next });
      setCfg(data);
      toast.success(`Global daily cap set to ${data.cap}`);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); load(); }
  };

  const generate = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/proposals/generate", { client_id: activeClientId || null });
      toast.success(data.message);
      load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };

  const toggleAutopilot = async () => {
    const next = !autopilot;
    setAutopilot(next);
    try {
      const q = activeClientId ? `?client_id=${activeClientId}` : "";
      const cur = await api.get(`/profile${q}`);
      await api.put("/profile", { ...cur.data, autopilot: next, client_id: activeClientId || null });
      toast.success(next ? "Daily autopilot ON — proposals appear here for approval" : "Autopilot paused");
    } catch (e) { setAutopilot(!next); toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const approve = async (id) => { try { const { data } = await api.post(`/proposals/${id}/approve`, {}); toast.success(data.message); load(); } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); } };
  const reject = async (id) => { await api.post(`/proposals/${id}/reject`); toast.success("Rejected"); load(); };

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Autopilot · Human-in-the-Loop"
        title="Campaign Approvals"
        description="The AI proposes campaigns daily. Nothing goes live without your approval — approve to launch, reject to discard."
        action={
          <button onClick={generate} disabled={busy} data-testid="generate-proposals-btn"
            className="flex items-center gap-2 bg-[#FF3B30] text-white px-4 py-2.5 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">
            <Sparkle size={16} weight="fill" /> {busy ? "Generating" : "Generate Now"}
          </button>
        }
      />

      <Fade>
        <div className="border border-border bg-[#0A0A0A] mb-8">
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 border border-zinc-800 flex items-center justify-center"><Robot size={18} className="text-[#FF3B30]" /></div>
              <div>
                <div className="text-sm">Daily Autopilot</div>
                <div className="text-xs text-zinc-500">Auto-generate fresh campaign proposals every day for your review.</div>
              </div>
            </div>
            <button onClick={toggleAutopilot} data-testid="autopilot-toggle"
              className={`relative w-14 h-7 border transition-colors duration-200 ${autopilot ? "bg-[#FF3B30] border-[#FF3B30]" : "bg-transparent border-zinc-700"}`}>
              <span className={`absolute top-0.5 w-5 h-5 bg-white transition-all duration-200 ${autopilot ? "left-8" : "left-0.5"}`} />
            </button>
          </div>

          <div className="border-t border-border p-4 flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-sm">Proposals per day</div>
              <div className="text-xs text-zinc-500">How many campaign ideas the autopilot proposes each day (max {cfg.cap}).</div>
            </div>
            <Stepper value={cfg.daily_proposals} min={1} max={cfg.cap} onChange={setCadence} testid="cadence" />
          </div>

          {cfg.is_admin && (
            <div className="border-t border-border p-4 flex flex-wrap items-center justify-between gap-4 bg-[#080808]">
              <div>
                <div className="text-sm flex items-center gap-2"><Lightning size={13} weight="fill" className="text-[#FFCC00]" /> Platform Daily Cap</div>
                <div className="text-xs text-zinc-500">Global maximum any owner can set for daily proposals.</div>
              </div>
              <Stepper value={cfg.cap} min={1} max={50} onChange={setCap} testid="cap" />
            </div>
          )}
        </div>
      </Fade>

      {!items ? <Loader label="Loading proposals" /> : items.length === 0 ? (
        <Section><div className="text-center py-16 text-zinc-600 text-sm">No pending proposals. Turn on Autopilot or click "Generate Now" to get AI campaign ideas.</div></Section>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {items.map((it) => {
            const p = it.data || {};
            return (
              <Fade key={it.id}>
                <div className="border border-border bg-[#0A0A0A] flex flex-col" data-testid={`proposal-${it.id}`}>
                  <div className="p-5 border-b border-border">
                    <div className="flex items-center justify-between">
                      <span className="text-xs px-2 py-1 border border-[#FFCC00]/40 text-[#FFCC00] uppercase tracking-wider flex items-center gap-1"><Lightning size={11} weight="fill" /> {it.source}</span>
                      <span className="text-xs font-mono text-zinc-500">{p.channel}</span>
                    </div>
                    <div className="font-display text-lg mt-3">{p.name}</div>
                    <div className="text-xs text-zinc-500 mt-1">{p.objective}</div>
                  </div>
                  <div className="p-5 space-y-3 flex-1">
                    <div className="grid grid-cols-2 gap-3">
                      <div><div className="text-[10px] uppercase tracking-wider text-zinc-500">Budget</div><div className="font-mono text-sm">{format(p.suggested_budget || 0)}</div></div>
                      <div><div className="text-[10px] uppercase tracking-wider text-zinc-500">Est. Leads</div><div className="font-mono text-sm">{p.expected_leads ?? "—"}</div></div>
                    </div>
                    {p.target_audience && <div><div className="text-[10px] uppercase tracking-wider text-zinc-500">Audience</div><div className="text-sm text-zinc-300">{p.target_audience}</div></div>}
                    {p.ad_copy && <div className="border-l-2 border-zinc-700 pl-3 text-sm text-zinc-400 italic">"{p.ad_copy}"</div>}
                    {p.rationale && <div className="text-xs text-zinc-600">{p.rationale}</div>}
                  </div>
                  <div className="flex border-t border-border">
                    <button onClick={() => approve(it.id)} data-testid={`approve-${it.id}`}
                      className="flex-1 flex items-center justify-center gap-2 py-3 text-sm uppercase tracking-wider text-[#34C759] hover:bg-[#34C759]/10 transition-colors duration-200 border-r border-border">
                      <CheckCircle size={16} weight="fill" /> Approve & Launch
                    </button>
                    <button onClick={() => reject(it.id)} data-testid={`reject-${it.id}`}
                      className="flex-1 flex items-center justify-center gap-2 py-3 text-sm uppercase tracking-wider text-zinc-400 hover:bg-[#FF3B30]/10 hover:text-[#FF3B30] transition-colors duration-200">
                      <XCircle size={16} /> Reject
                    </button>
                  </div>
                </div>
              </Fade>
            );
          })}
        </div>
      )}
    </div>
  );
}

const Stepper = ({ value, min, max, onChange, testid }) => (
  <div className="flex items-center border border-zinc-800" data-testid={`${testid}-stepper`}>
    <button onClick={() => onChange(value - 1)} disabled={value <= min} data-testid={`${testid}-dec`}
      className="w-10 h-10 flex items-center justify-center text-lg text-zinc-400 hover:text-white hover:bg-[#141414] disabled:opacity-30 transition-colors duration-200">−</button>
    <div className="w-14 text-center font-mono text-lg" data-testid={`${testid}-value`}>{value}</div>
    <button onClick={() => onChange(value + 1)} disabled={value >= max} data-testid={`${testid}-inc`}
      className="w-10 h-10 flex items-center justify-center text-lg text-zinc-400 hover:text-white hover:bg-[#141414] disabled:opacity-30 transition-colors duration-200">+</button>
  </div>
);
