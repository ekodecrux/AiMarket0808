import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { useClient } from "@/context/ClientContext";
import { useCurrency } from "@/context/CurrencyContext";
import { PageHeader, Loader, Section } from "@/components/common";
import { toast } from "sonner";
import { Plus, Play, Pause, Trash, X, PencilSimple } from "@phosphor-icons/react";

const CHANNELS = ["Google Ads", "Meta Ads", "LinkedIn Ads", "YouTube Ads", "Email", "SEO", "Retargeting", "Influencer"];

export default function Campaigns() {
  const { activeClientId, activeClient } = useClient();
  const { format } = useCurrency();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = () => {
    setLoading(true);
    const q = activeClientId ? `?client_id=${activeClientId}` : "";
    api.get(`/campaigns${q}`).then((r) => setItems(r.data)).catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [activeClientId]);

  const toggle = async (id) => { await api.patch(`/campaigns/${id}/toggle`); load(); };
  const del = async (id) => { await api.delete(`/campaigns/${id}`); toast.success("Deleted"); load(); };

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline={activeClient ? `Campaign Manager · ${activeClient.name}` : "Campaign Manager"}
        title="Campaigns & Performance"
        description="Track real spend and results per channel. Enter actuals and the engine computes CTR, CPA, ROAS and ROI live."
        action={
          <button onClick={() => setShowForm(true)} data-testid="add-campaign-btn"
            className="flex items-center gap-2 bg-[#FF3B30] text-white px-4 py-2.5 text-sm uppercase tracking-wider hover:bg-[#D63026] transition-colors duration-200">
            <Plus size={16} /> New Campaign
          </button>
        }
      />

      {loading ? <Loader label="Loading campaigns" /> : items.length === 0 ? (
        <Section><div className="text-center py-16 text-zinc-500 text-sm">No campaigns yet. Create one to start tracking performance.</div></Section>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {items.map((c) => (
            <div key={c.id} className="border border-border bg-white" data-testid={`campaign-${c.id}`}>
              <div className="flex items-start justify-between p-5 border-b border-border">
                <div>
                  <div className="font-display text-lg">{c.name}</div>
                  <div className="text-xs text-zinc-500 mt-0.5">{c.channel} · {c.objective}</div>
                </div>
                <span className={`text-xs px-2 py-1 border ${c.status === "Active" ? "text-[#34C759] border-[#34C759]/40" : "text-zinc-500 border-zinc-300"}`}>{c.status}</span>
              </div>
              <div className="grid grid-cols-4 border-b border-border">
                {[["Spend", format(c.budget || 0)], ["Revenue", format(c.revenue || 0)], ["ROAS", `${c.roas}x`], ["ROI", `${c.roi}%`]].map(([l, v]) => (
                  <div key={l} className="p-3 border-r border-border last:border-r-0">
                    <div className="text-[10px] uppercase tracking-wider text-zinc-500">{l}</div>
                    <div className="font-mono text-sm mt-1">{v}</div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-4 border-b border-border">
                {[["Impr.", (c.impressions || 0).toLocaleString()], ["Clicks", (c.clicks || 0).toLocaleString()], ["CTR", `${c.ctr}%`], ["Conv.", c.conversions || 0]].map(([l, v]) => (
                  <div key={l} className="p-3 border-r border-border last:border-r-0">
                    <div className="text-[10px] uppercase tracking-wider text-zinc-500">{l}</div>
                    <div className="font-mono text-sm mt-1">{v}</div>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2 p-4">
                <button onClick={() => setEditing(c)} data-testid={`edit-metrics-${c.id}`} className="flex items-center gap-1 text-xs border border-zinc-200 px-3 py-1.5 hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors duration-200"><PencilSimple size={14} /> Update Metrics</button>
                <button onClick={() => toggle(c.id)} data-testid={`toggle-campaign-${c.id}`} className="flex items-center gap-1 text-xs border border-zinc-200 px-3 py-1.5 hover:border-zinc-600 transition-colors duration-200">{c.status === "Active" ? <><Pause size={14} /> Pause</> : <><Play size={14} /> Resume</>}</button>
                <button onClick={() => del(c.id)} data-testid={`delete-campaign-${c.id}`} className="ml-auto text-zinc-500 hover:text-[#FF3B30] transition-colors duration-200"><Trash size={16} /></button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && <CampaignForm clientId={activeClientId} onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />}
      {editing && <MetricsForm campaign={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}

function CampaignForm({ clientId, onClose, onSaved }) {
  const [form, setForm] = useState({ name: "", channel: "Google Ads", objective: "Lead Generation", budget: "", impressions: "", clicks: "", conversions: "", revenue: "" });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!form.name || !form.budget) return toast.error("Name and budget required");
    setBusy(true);
    try {
      await api.post("/campaigns", {
        name: form.name, channel: form.channel, objective: form.objective,
        budget: parseFloat(form.budget) || 0, impressions: parseInt(form.impressions) || 0,
        clicks: parseInt(form.clicks) || 0, conversions: parseInt(form.conversions) || 0, revenue: parseFloat(form.revenue) || 0,
        client_id: clientId || null,
      });
      toast.success("Campaign created"); onSaved();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };
  return (
    <Modal title="New Campaign" onClose={onClose}>
      <div className="grid grid-cols-2 gap-4">
        <TextIn label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testid="campaign-name" span />
        <div>
          <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Channel</label>
          <select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })} data-testid="campaign-channel"
            className="w-full bg-white border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200">
            {CHANNELS.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <TextIn label="Objective" value={form.objective} onChange={(v) => setForm({ ...form, objective: v })} testid="campaign-objective" />
        <TextIn label="Budget ($)" value={form.budget} onChange={(v) => setForm({ ...form, budget: v })} testid="campaign-budget" type="number" />
        <TextIn label="Revenue ($)" value={form.revenue} onChange={(v) => setForm({ ...form, revenue: v })} testid="campaign-revenue" type="number" />
        <TextIn label="Impressions" value={form.impressions} onChange={(v) => setForm({ ...form, impressions: v })} testid="campaign-impressions" type="number" />
        <TextIn label="Clicks" value={form.clicks} onChange={(v) => setForm({ ...form, clicks: v })} testid="campaign-clicks" type="number" />
        <TextIn label="Conversions" value={form.conversions} onChange={(v) => setForm({ ...form, conversions: v })} testid="campaign-conversions" type="number" />
      </div>
      <FormFooter busy={busy} onClose={onClose} onSubmit={submit} testid="save-campaign-btn" />
    </Modal>
  );
}

function MetricsForm({ campaign, onClose, onSaved }) {
  const [form, setForm] = useState({ impressions: campaign.impressions || 0, clicks: campaign.clicks || 0, conversions: campaign.conversions || 0, revenue: campaign.revenue || 0 });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await api.patch(`/campaigns/${campaign.id}/metrics`, {
        impressions: parseInt(form.impressions) || 0, clicks: parseInt(form.clicks) || 0,
        conversions: parseInt(form.conversions) || 0, revenue: parseFloat(form.revenue) || 0,
      });
      toast.success("Metrics updated"); onSaved();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };
  return (
    <Modal title={`Update · ${campaign.name}`} onClose={onClose}>
      <div className="grid grid-cols-2 gap-4">
        <TextIn label="Impressions" value={form.impressions} onChange={(v) => setForm({ ...form, impressions: v })} testid="m-impressions" type="number" />
        <TextIn label="Clicks" value={form.clicks} onChange={(v) => setForm({ ...form, clicks: v })} testid="m-clicks" type="number" />
        <TextIn label="Conversions" value={form.conversions} onChange={(v) => setForm({ ...form, conversions: v })} testid="m-conversions" type="number" />
        <TextIn label="Revenue ($)" value={form.revenue} onChange={(v) => setForm({ ...form, revenue: v })} testid="m-revenue" type="number" />
      </div>
      <FormFooter busy={busy} onClose={onClose} onSubmit={submit} testid="save-metrics-btn" />
    </Modal>
  );
}

const Modal = ({ title, children, onClose }) => (
  <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
    <div className="bg-white border border-border w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <h3 className="font-display text-lg">{title}</h3>
        <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors duration-200"><X size={20} /></button>
      </div>
      <div className="p-5">{children}</div>
    </div>
  </div>
);

const TextIn = ({ label, value, onChange, testid, type = "text", span }) => (
  <div className={span ? "col-span-2" : ""}>
    <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{label}</label>
    <input type={type} value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid}
      className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200" />
  </div>
);

const FormFooter = ({ busy, onClose, onSubmit, testid }) => (
  <div className="flex justify-end gap-3 mt-6">
    <button onClick={onClose} className="px-4 py-2 text-sm border border-zinc-200 hover:border-zinc-600 transition-colors duration-200">Cancel</button>
    <button onClick={onSubmit} disabled={busy} data-testid={testid} className="px-4 py-2 text-sm bg-[#FF3B30] text-white hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">{busy ? "Saving" : "Save"}</button>
  </div>
);
