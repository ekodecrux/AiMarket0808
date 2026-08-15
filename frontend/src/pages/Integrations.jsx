import { useEffect, useState } from "react";
import { useClient } from "@/context/ClientContext";
import { useCurrency } from "@/context/CurrencyContext";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import { PlugsConnected, X, CheckCircle, WarningCircle, Circle, Buildings, Sparkle, Globe } from "@phosphor-icons/react";

const STATUS = {
  Connected: { color: "#34C759", Icon: CheckCircle },
  Partial: { color: "#FFCC00", Icon: WarningCircle },
  Pending: { color: "#52525B", Icon: Circle },
};

const CURRENCIES = ["USD", "EUR", "GBP", "INR", "AED", "AUD", "CAD", "SGD", "JPY", "BRL", "ZAR", "NGN"];
const COUNTRIES = ["United States", "United Kingdom", "India", "United Arab Emirates", "Australia", "Canada", "Singapore", "Germany", "France", "Brazil", "South Africa", "Nigeria", "Other"];

// Standard currency for each location. When the location in the business profile
// changes, the workspace currency follows automatically (unless the owner has
// explicitly picked a different currency and saved it).
const COUNTRY_CURRENCY = {
  "United States": "USD",
  "United Kingdom": "GBP",
  "India": "INR",
  "United Arab Emirates": "AED",
  "Australia": "AUD",
  "Canada": "CAD",
  "Singapore": "SGD",
  "Germany": "EUR",
  "France": "EUR",
  "Brazil": "BRL",
  "South Africa": "ZAR",
  "Nigeria": "NGN",
};

const CURRENCY_SYMBOLS = {
  USD: "$", EUR: "\u20AC", GBP: "\u00A3", INR: "\u20B9", AED: "AED", AUD: "A$",
  CAD: "C$", SGD: "S$", JPY: "\u00A5", BRL: "R$", ZAR: "R", NGN: "\u20A6",
};

export default function Integrations() {
  const { activeClient, activeClientId } = useClient();
  const [tab, setTab] = useState("profile");
  const [conns, setConns] = useState(null);
  const [editing, setEditing] = useState(null);

  const load = () => {
    setConns(null);
    const q = activeClientId ? `?client_id=${activeClientId}` : "";
    api.get(`/connections${q}`).then((r) => setConns(r.data)).catch(() => setConns([]));
  };
  useEffect(() => { if (tab === "credentials") load(); }, [activeClientId, tab]);

  const categories = conns ? [...new Set(conns.map((c) => c.category))] : [];

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Settings"
        title="Workspace Settings"
        description={`${activeClient ? `Scope: ${activeClient.name}.` : "Scope: Platform (default)."} One place for your business profile, currency and all integration credentials — set once, used everywhere.`}
        action={
          <div className="flex border border-border">
            {[["profile", "Business Profile", Buildings], ["credentials", "Credentials", PlugsConnected]].map(([id, label, Icon]) => (
              <button key={id} onClick={() => setTab(id)} data-testid={`settings-tab-${id}`}
                className={`flex items-center gap-2 px-4 py-2 text-xs uppercase tracking-wider transition-colors duration-200 ${tab === id ? "bg-[#2563EB] text-white" : "text-zinc-500 hover:text-zinc-950"}`}>
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>
        }
      />

      {tab === "profile" ? <BusinessProfile clientId={activeClientId} /> : (
        !conns ? <Loader label="Loading connections" /> : (
          <div className="space-y-8">
            {categories.map((cat) => (
              <div key={cat}>
                <div className="text-xs font-bold uppercase tracking-[0.2em] text-zinc-500 mb-4">{cat}</div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-border border border-border">
                  {conns.filter((c) => c.category === cat).map((c) => {
                    const s = STATUS[c.status] || STATUS.Pending;
                    return (
                      <Fade key={c.provider}>
                        <div className="bg-white p-5 h-full flex flex-col" data-testid={`integration-${c.provider}`}>
                          <div className="flex items-start justify-between">
                            <div className="w-9 h-9 rounded-md border border-zinc-200 bg-zinc-50 flex items-center justify-center"><PlugsConnected size={18} className="text-zinc-500" /></div>
                            <div className="flex items-center gap-1.5" style={{ color: s.color }}>
                              <s.Icon size={14} weight="fill" />
                              <span className="text-[10px] uppercase tracking-wider">{c.status}</span>
                            </div>
                          </div>
                          <div className="font-display text-base mt-3">{c.label}</div>
                          <div className="text-xs text-zinc-500 mt-1 flex-1">{c.help}</div>
                          <button onClick={() => setEditing(c)} data-testid={`configure-${c.provider}`}
                            className="mt-4 w-full py-2 rounded-md text-xs uppercase tracking-wider border border-zinc-200 text-zinc-500 hover:border-[#2563EB] hover:text-[#2563EB] transition-colors duration-200">
                            Configure
                          </button>
                        </div>
                      </Fade>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {editing && <ConfigModal conn={editing} clientId={activeClientId} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}

function BusinessProfile({ clientId }) {
  const { refresh: refreshCurrency, currency: savedCurrency } = useCurrency();
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [extracting, setExtracting] = useState(false);

  useEffect(() => {
    const q = clientId ? `?client_id=${clientId}` : "";
    api.get(`/profile${q}`).then((r) => setForm(r.data)).catch(() => setForm({ currency: "USD", country: "United States" }));
  }, [clientId]);

  // Auto-follow: when the owner changes the location, adopt that country's
  // standard currency (only if the currency still matches the loaded one, i.e.
  // the owner hasn't explicitly picked something else).
  const setLocation = (country) => {
    setForm((f) => {
      const suggested = COUNTRY_CURRENCY[country];
      const keeps = !suggested || f.currency === savedCurrency;
      return { ...f, country, ...(suggested && keeps ? { currency: suggested } : {}) };
    });
  };

  const extract = async () => {
    if (!form.website) return toast.error("Enter a website URL first");
    setExtracting(true);
    try {
      const { data } = await api.post("/profile/extract", { url: form.website });
      setForm((f) => ({
        ...f,
        company_name: data.company_name || f.company_name,
        description: data.description || f.description,
        industry: data.industry || f.industry,
        country: data.suggested_country || f.country,
        currency: data.suggested_currency || f.currency,
      }));
      toast.success("Prefilled from website — review & save");
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setExtracting(false); }
  };

  const save = async () => {
    setBusy(true);
    try {
      await api.put("/profile", { ...form, client_id: clientId || null });
      toast.success("Profile saved");
      refreshCurrency();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };

  if (!form) return <Loader label="Loading profile" />;

  return (
    <Fade>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Section title="Prefill from Website" className="lg:col-span-1 self-start">
          <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Website URL</label>
          <input value={form.website || ""} onChange={(e) => setForm({ ...form, website: e.target.value })} data-testid="profile-website" placeholder="yourcompany.com"
            className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200 mb-3" />
          <button onClick={extract} disabled={extracting} data-testid="extract-profile-btn"
            className="w-full flex items-center justify-center gap-2 border border-zinc-300 py-2.5 text-sm uppercase tracking-wider hover:border-[#2563EB] hover:text-[#2563EB] transition-colors duration-200 disabled:opacity-50">
            <Sparkle size={15} weight="fill" /> {extracting ? "Extracting" : "Auto-Fill Profile"}
          </button>
          <p className="text-xs text-zinc-500 mt-3">We fetch your site and let AI extract your company name, description, industry and suggested currency.</p>
        </Section>

        <Section title="Business Profile" className="lg:col-span-2">
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Company Name" value={form.company_name} onChange={(v) => setForm({ ...form, company_name: v })} testid="profile-company" />
            <Field label="Industry" value={form.industry} onChange={(v) => setForm({ ...form, industry: v })} testid="profile-industry" />
            <div className="sm:col-span-2">
              <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Description</label>
              <textarea rows={3} value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="profile-description"
                className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200 resize-none" />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2 flex items-center gap-1"><Globe size={12} /> Location</label>
              <select value={form.country || "United States"} onChange={(e) => setLocation(e.target.value)} data-testid="profile-country"
                className="w-full bg-white border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200">
                {COUNTRIES.map((c) => <option key={c}>{c}</option>)}
              </select>
              <p className="text-[11px] text-zinc-400 mt-1.5">Currency follows your location &mdash; change this to switch the workspace currency.</p>
            </div>
            <div>
              <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Currency</label>
              <select value={form.currency || "USD"} onChange={(e) => setForm({ ...form, currency: e.target.value })} data-testid="profile-currency"
                className="w-full bg-white border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200">
                {CURRENCIES.map((c) => <option key={c} value={c}>{CURRENCY_SYMBOLS[c] ? `${c} (${CURRENCY_SYMBOLS[c]})` : c}</option>)}
              </select>
            </div>
          </div>
          <button onClick={save} disabled={busy} data-testid="save-profile-btn"
            className="mt-5 flex items-center justify-center gap-2 bg-[#2563EB] text-white px-5 py-2.5 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors duration-200">
            {busy ? "Saving" : "Save Profile"}
          </button>
        </Section>
      </div>
    </Fade>
  );
}

function Field({ label, value, onChange, testid }) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{label}</label>
      <input value={value || ""} onChange={(e) => onChange(e.target.value)} data-testid={testid}
        className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200" />
    </div>
  );
}

function ConfigModal({ conn, clientId, onClose, onSaved }) {
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await api.post("/connections", { provider: conn.provider, client_id: clientId || null, credentials: values });
      toast.success("Credentials saved (encrypted)");
      onSaved();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-zinc-950/25 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-2xl border border-border w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h3 className="font-display text-lg">{conn.label}</h3>
            <div className="text-xs text-zinc-500">{conn.category}</div>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-950 transition-colors duration-200"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">
          {conn.fields.map((f) => {
            const stored = conn.credentials?.[f];
            return (
              <div key={f}>
                <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{f.replace(/_/g, " ")}{stored?.set && <span className="text-[#34C759] ml-2 lowercase tracking-normal">saved {stored.hint}</span>}</label>
                <input type="password" placeholder={stored?.set ? "•••• (leave blank to keep)" : "Enter value"} value={values[f] || ""}
                  onChange={(e) => setValues({ ...values, [f]: e.target.value })} data-testid={`cred-${conn.provider}-${f}`}
                  className="w-full bg-white border border-zinc-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[#2563EB] transition-colors duration-200 font-mono" />
              </div>
            );
          })}
          <div className="text-xs text-zinc-500 bg-zinc-50 border border-zinc-200 px-3 py-2 rounded-md">{conn.help}</div>
        </div>
        <div className="px-5 py-4 border-t border-border flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-zinc-200 rounded-md hover:border-zinc-400 transition-colors duration-200">Cancel</button>
          <button onClick={save} disabled={busy} data-testid="save-connection-btn" className="px-4 py-2 text-sm rounded-md bg-[#2563EB] text-white hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors duration-200">{busy ? "Saving" : "Save Encrypted"}</button>
        </div>
      </div>
    </div>
  );
}
