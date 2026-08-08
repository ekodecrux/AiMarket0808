import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { useClient } from "@/context/ClientContext";
import { PageHeader, Loader, Section } from "@/components/common";
import { toast } from "sonner";
import { Plus, Sparkle, Trash, X, MagnifyingGlass, UploadSimple, ArrowsClockwise } from "@phosphor-icons/react";

const CAT_COLOR = {
  "Hot": "text-[#2563EB] border-[#2563EB]/40 bg-[#2563EB]/5",
  "Sales Ready": "text-[#34C759] border-[#34C759]/40 bg-[#34C759]/5",
  "Warm": "text-[#FFCC00] border-[#FFCC00]/40 bg-[#FFCC00]/5",
  "Cold": "text-[#007AFF] border-[#007AFF]/40 bg-[#007AFF]/5",
  "Unscored": "text-zinc-500 border-zinc-300",
};
const STAGES = ["New", "Qualified", "Opportunity", "Won", "Lost"];

export default function Leads() {
  const { activeClientId, activeClient } = useClient();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showScrape, setShowScrape] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [scoring, setScoring] = useState(null);
  const [crmBusy, setCrmBusy] = useState(false);

  const load = () => {
    setLoading(true);
    const q = activeClientId ? `?client_id=${activeClientId}` : "";
    api.get(`/leads${q}`).then((r) => setLeads(r.data)).catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [activeClientId]);

  const syncCrm = async () => {
    setCrmBusy(true);
    let done = false;
    for (const provider of ["hubspot", "zoho"]) {
      try {
        const { data } = await api.post("/crm/sync", { provider, client_id: activeClientId || null });
        toast.success(data.message);
        done = true;
        break;
      } catch (e) {
        const msg = formatApiError(e.response?.data?.detail);
        if (!msg.includes("not configured")) { toast.error(msg); done = true; break; }
      }
    }
    if (!done) toast.error("Connect HubSpot or Zoho in Settings to sync CRM leads");
    setCrmBusy(false);
    load();
  };

  const score = async (id) => {
    setScoring(id);
    try { await api.post(`/leads/${id}/score`); toast.success("Lead scored"); load(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setScoring(null); }
  };
  const setStage = async (id, stage) => { await api.patch(`/leads/${id}/stage`, { stage }); load(); };
  const del = async (id) => { await api.delete(`/leads/${id}`); toast.success("Lead deleted"); load(); };

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline={activeClient ? `Lead Management · ${activeClient.name}` : "Lead Management"}
        title="Pipeline & Qualification"
        description="Capture leads manually, scrape them live from company websites, or import a CRM CSV — then let the AI score them."
        action={
          <div className="flex flex-wrap gap-2">
            <button onClick={syncCrm} disabled={crmBusy} data-testid="sync-crm-btn"
              className="flex items-center gap-2 border border-zinc-300 text-zinc-200 px-3 py-2.5 text-sm uppercase tracking-wider hover:border-[#007AFF] hover:text-[#007AFF] transition-colors duration-200 disabled:opacity-40">
              <ArrowsClockwise size={16} className={crmBusy ? "animate-spin" : ""} /> Sync CRM
            </button>
            <button onClick={() => setShowScrape(true)} data-testid="discover-leads-btn"
              className="flex items-center gap-2 border border-zinc-300 text-zinc-200 px-3 py-2.5 text-sm uppercase tracking-wider hover:border-[#2563EB] hover:text-[#2563EB] transition-colors duration-200">
              <MagnifyingGlass size={16} /> Discover
            </button>
            <button onClick={() => setShowImport(true)} data-testid="import-leads-btn"
              className="flex items-center gap-2 border border-zinc-300 text-zinc-200 px-3 py-2.5 text-sm uppercase tracking-wider hover:border-[#2563EB] hover:text-[#2563EB] transition-colors duration-200">
              <UploadSimple size={16} /> Import CSV
            </button>
            <button onClick={() => setShowForm(true)} data-testid="add-lead-btn"
              className="flex items-center gap-2 bg-[#2563EB] text-white px-4 py-2.5 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] transition-colors duration-200">
              <Plus size={16} /> Add Lead
            </button>
          </div>
        }
      />

      {loading ? <Loader label="Loading leads" /> : (
        <Section title={`Leads · ${leads.length}`}>
          {leads.length === 0 ? (
            <div className="text-center py-16 text-zinc-500 text-sm">No leads yet. Add your first lead to begin scoring.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-xs uppercase tracking-wider text-zinc-500 text-left border-b border-border">
                  <th className="pb-3">Lead</th><th className="pb-3">Company</th><th className="pb-3">Score</th>
                  <th className="pb-3">Category</th><th className="pb-3">Stage</th><th className="pb-3 text-right">Actions</th>
                </tr></thead>
                <tbody>
                  {leads.map((l) => (
                    <tr key={l.id} className="border-b border-zinc-900 hover:bg-zinc-50 transition-colors duration-200" data-testid={`lead-row-${l.id}`}>
                      <td className="py-3"><div>{l.name}</div><div className="text-xs text-zinc-500">{l.email}</div></td>
                      <td className="py-3"><div>{l.company}</div><div className="text-xs text-zinc-500">{l.role}</div></td>
                      <td className="py-3 font-mono">{l.score ?? "—"}</td>
                      <td className="py-3"><span className={`text-xs px-2 py-1 border ${CAT_COLOR[l.category] || CAT_COLOR.Unscored}`}>{l.category}</span></td>
                      <td className="py-3">
                        <select value={l.stage} onChange={(e) => setStage(l.id, e.target.value)} data-testid={`lead-stage-${l.id}`}
                          className="bg-white border border-zinc-200 px-2 py-1 text-xs focus:outline-none focus:border-[#2563EB] transition-colors duration-200">
                          {STAGES.map((s) => <option key={s}>{s}</option>)}
                        </select>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center justify-end gap-2">
                          <button onClick={() => score(l.id)} disabled={scoring === l.id} data-testid={`score-lead-${l.id}`}
                            className="flex items-center gap-1 text-xs border border-zinc-200 px-2 py-1.5 hover:border-[#2563EB] hover:text-[#2563EB] transition-colors duration-200 disabled:opacity-40">
                            <Sparkle size={12} weight="fill" /> {scoring === l.id ? "..." : "Score"}
                          </button>
                          <button onClick={() => del(l.id)} data-testid={`delete-lead-${l.id}`} className="text-zinc-500 hover:text-[#2563EB] transition-colors duration-200"><Trash size={16} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      )}

      {showForm && <LeadForm clientId={activeClientId} onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />}
      {showScrape && <ScrapeModal clientId={activeClientId} onClose={() => setShowScrape(false)} onSaved={() => { setShowScrape(false); load(); }} />}
      {showImport && <ImportModal clientId={activeClientId} onClose={() => setShowImport(false)} onSaved={() => { setShowImport(false); load(); }} />}
    </div>
  );
}

function ScrapeModal({ clientId, onClose, onSaved }) {
  const [domains, setDomains] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (!domains.trim()) return toast.error("Enter at least one domain");
    setBusy(true);
    try {
      const { data } = await api.post("/leads/scrape", { domains, client_id: clientId || null });
      toast.success(`${data.count} lead(s) discovered`);
      onSaved();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white border border-border w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="font-display text-lg">Discover Leads from Websites</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-950 transition-colors duration-200"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Company Domains (one per line, max 10)</label>
            <textarea rows={5} value={domains} onChange={(e) => setDomains(e.target.value)} data-testid="scrape-domains"
              placeholder={"stripe.com\nnotion.so\nvercel.com"}
              className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#2563EB] transition-colors duration-200 resize-none" />
          </div>
          <p className="text-xs text-zinc-500">NEXUS fetches each site's contact/about pages and extracts real emails, phones and social profiles. ~5-15s.</p>
          <button onClick={run} disabled={busy} data-testid="run-scrape-btn"
            className="w-full flex items-center justify-center gap-2 bg-[#2563EB] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors duration-200">
            <MagnifyingGlass size={16} /> {busy ? "Scraping" : "Discover Leads"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ImportModal({ clientId, onClose, onSaved }) {
  const [csv, setCsv] = useState("");
  const [busy, setBusy] = useState(false);
  const onFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = (ev) => setCsv(ev.target.result);
    reader.readAsText(f);
  };
  const run = async () => {
    if (!csv.trim()) return toast.error("Paste CSV or choose a file");
    setBusy(true);
    try {
      const { data } = await api.post("/leads/import", { csv_text: csv, client_id: clientId || null });
      toast.success(`${data.count} lead(s) imported`);
      onSaved();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white border border-border w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="font-display text-lg">Import Leads from CSV</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-950 transition-colors duration-200"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">
          <input type="file" accept=".csv,text/csv" onChange={onFile} data-testid="import-file"
            className="block w-full text-sm text-zinc-500 file:mr-3 file:border file:border-zinc-300 file:bg-transparent file:text-zinc-200 file:px-3 file:py-1.5 file:text-xs file:uppercase" />
          <div className="text-xs text-zinc-500 text-center">or paste below</div>
          <textarea rows={6} value={csv} onChange={(e) => setCsv(e.target.value)} data-testid="import-csv-text"
            placeholder={"name,email,company,title\nJane Doe,jane@acme.com,Acme,VP Marketing"}
            className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-xs font-mono focus:outline-none focus:border-[#2563EB] transition-colors duration-200 resize-none" />
          <p className="text-xs text-zinc-500">Recognizes columns: name, email, company, role/title, industry, size, budget, source, notes. Works with HubSpot/Zoho/Salesforce exports.</p>
          <button onClick={run} disabled={busy} data-testid="run-import-btn"
            className="w-full flex items-center justify-center gap-2 bg-[#2563EB] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors duration-200">
            <UploadSimple size={16} /> {busy ? "Importing" : "Import Leads"}
          </button>
        </div>
      </div>
    </div>
  );
}

function LeadForm({ clientId, onClose, onSaved }) {
  const [form, setForm] = useState({ name: "", email: "", company: "", role: "", industry: "", company_size: "", budget: "", source: "Website", notes: "" });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!form.name || !form.email || !form.company) return toast.error("Name, email and company required");
    setBusy(true);
    try { await api.post("/leads", { ...form, client_id: clientId || null }); toast.success("Lead added"); onSaved(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };
  const F = ([key, label]) => (
    <div key={key}>
      <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{label}</label>
      <input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} data-testid={`lead-${key}`}
        className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200" />
    </div>
  );
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white border border-border w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="font-display text-lg">Add Lead</h3>
          <button onClick={onClose} data-testid="close-lead-form" className="text-zinc-500 hover:text-zinc-950 transition-colors duration-200"><X size={20} /></button>
        </div>
        <div className="p-5 grid grid-cols-2 gap-4">
          {[["name", "Name"], ["email", "Email"], ["company", "Company"], ["role", "Role"], ["industry", "Industry"], ["company_size", "Company Size"], ["budget", "Budget"], ["source", "Source"]].map(F)}
          <div className="col-span-2">
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Notes</label>
            <textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="lead-notes"
              className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200 resize-none" />
          </div>
        </div>
        <div className="px-5 py-4 border-t border-border flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-zinc-200 hover:border-zinc-600 transition-colors duration-200">Cancel</button>
          <button onClick={submit} disabled={busy} data-testid="save-lead-btn" className="px-4 py-2 text-sm bg-[#2563EB] text-white hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors duration-200">{busy ? "Saving" : "Save Lead"}</button>
        </div>
      </div>
    </div>
  );
}
