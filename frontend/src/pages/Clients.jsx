import { useState, useEffect } from "react";
import { useClient } from "@/context/ClientContext";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import { Plus, Trash, X, Buildings, Users, Megaphone, PlugsConnected, Pencil, Key } from "@phosphor-icons/react";

export default function Clients() {
  const { clients, refresh, activeClientId, setActive } = useClient();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [portalClient, setPortalClient] = useState(null);
  const [loading, setLoading] = useState(false);

  const del = async (id) => {
    await api.delete(`/clients/${id}`);
    if (activeClientId === id) setActive("");
    toast.success("Client removed");
    refresh();
  };

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Agency · Customer Accounts"
        title="Client Workspaces"
        description="Create a workspace per customer. Select a client (top bar) to run leads, campaigns and connections on their behalf."
        action={
          <button onClick={() => setShowForm(true)} data-testid="add-client-btn"
            className="flex items-center gap-2 bg-[#FF3B30] text-white px-4 py-2.5 text-sm uppercase tracking-wider hover:bg-[#D63026] transition-colors duration-200">
            <Plus size={16} /> New Client
          </button>
        }
      />

      {loading ? <Loader /> : clients.length === 0 ? (
        <Section><div className="text-center py-16 text-zinc-600 text-sm">No clients yet. Create your first customer account to manage their marketing.</div></Section>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {clients.map((c) => (
            <Fade key={c.id}>
              <div className={`border bg-[#0A0A0A] ${activeClientId === c.id ? "border-[#FF3B30]" : "border-border"}`} data-testid={`client-${c.id}`}>
                <div className="p-5 border-b border-border">
                  <div className="flex items-start justify-between">
                    <div className="w-10 h-10 border border-zinc-800 flex items-center justify-center"><Buildings size={20} className="text-[#FF3B30]" /></div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => setEditing(c)} className="text-zinc-600 hover:text-white transition-colors duration-200 p-1"><Pencil size={15} /></button>
                      <button onClick={() => del(c.id)} data-testid={`delete-client-${c.id}`} className="text-zinc-600 hover:text-[#FF3B30] transition-colors duration-200 p-1"><Trash size={15} /></button>
                    </div>
                  </div>
                  <div className="font-display text-lg mt-3">{c.name}</div>
                  <div className="text-xs text-zinc-500">{c.industry || "—"} · {c.website || "no site"}</div>
                </div>
                <div className="grid grid-cols-3 border-b border-border">
                  {[[Users, c.leads, "Leads"], [Megaphone, c.campaigns, "Campaigns"], [PlugsConnected, c.connections, "Connected"]].map(([Icon, v, l], i) => (
                    <div key={i} className="p-3 border-r border-border last:border-r-0 text-center">
                      <Icon size={14} className="mx-auto text-zinc-500" />
                      <div className="font-mono text-sm mt-1">{v ?? 0}</div>
                      <div className="text-[9px] uppercase tracking-wider text-zinc-600">{l}</div>
                    </div>
                  ))}
                </div>
                <div className="p-4 space-y-2">
                  <button onClick={() => setActive(activeClientId === c.id ? "" : c.id)} data-testid={`select-client-${c.id}`}
                    className={`w-full py-2 text-xs uppercase tracking-wider transition-colors duration-200 ${activeClientId === c.id ? "bg-[#FF3B30] text-white" : "border border-zinc-700 text-zinc-300 hover:border-[#FF3B30] hover:text-[#FF3B30]"}`}>
                    {activeClientId === c.id ? "Active — Deselect" : "Work on this Client"}
                  </button>
                  <button onClick={() => setPortalClient(c)} data-testid={`portal-login-${c.id}`}
                    className="w-full flex items-center justify-center gap-2 py-2 text-xs uppercase tracking-wider border border-zinc-800 text-zinc-400 hover:border-[#007AFF] hover:text-[#007AFF] transition-colors duration-200">
                    <Key size={13} /> Portal Login {c.portal_users ? `(${c.portal_users})` : ""}
                  </button>
                </div>
              </div>
            </Fade>
          ))}
        </div>
      )}

      {showForm && <ClientForm onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); refresh(); }} />}
      {editing && <ClientForm client={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); refresh(); }} />}
      {portalClient && <PortalModal client={portalClient} onClose={() => setPortalClient(null)} onSaved={() => { setPortalClient(null); refresh(); }} />}
    </div>
  );
}

function PortalModal({ client, onClose, onSaved }) {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get(`/clients/${client.id}/portal-users`).then((r) => setUsers(r.data)).catch(() => {}); }, [client.id]);
  const submit = async () => {
    if (!form.email || !form.password) return toast.error("Email and password required");
    setBusy(true);
    try {
      await api.post(`/clients/${client.id}/portal-user`, form);
      toast.success("Portal login created — share with your client");
      onSaved();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[#0A0A0A] border border-border w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h3 className="font-display text-lg">Client Portal Login</h3>
            <div className="text-xs text-zinc-600">{client.name} — client sees only their leads, campaigns & analytics</div>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors duration-200"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">
          {users.length > 0 && (
            <div className="border border-zinc-800 p-3">
              <div className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Existing logins</div>
              {users.map((u) => <div key={u.id} className="text-sm text-zinc-300 font-mono">{u.email}</div>)}
            </div>
          )}
          <div>
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Client Email</label>
            <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="portal-email"
              className="w-full bg-transparent border border-zinc-800 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Temporary Password</label>
            <input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="portal-password"
              className="w-full bg-transparent border border-zinc-800 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200" />
          </div>
          <button onClick={submit} disabled={busy} data-testid="create-portal-user-btn"
            className="w-full flex items-center justify-center gap-2 bg-[#FF3B30] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">
            <Key size={16} /> {busy ? "Creating" : "Create Portal Login"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ClientForm({ client, onClose, onSaved }) {
  const [form, setForm] = useState(client || { name: "", industry: "", website: "", contact_email: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!form.name) return toast.error("Name required");
    setBusy(true);
    try {
      const payload = { name: form.name, industry: form.industry, website: form.website, contact_email: form.contact_email, notes: form.notes };
      if (client) await api.patch(`/clients/${client.id}`, payload);
      else await api.post("/clients", payload);
      toast.success(client ? "Updated" : "Client created");
      onSaved();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };
  const F = ([key, label]) => (
    <div key={key} className={key === "notes" ? "col-span-2" : ""}>
      <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{label}</label>
      <input value={form[key] || ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })} data-testid={`client-${key}`}
        className="w-full bg-transparent border border-zinc-800 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200" />
    </div>
  );
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[#0A0A0A] border border-border w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="font-display text-lg">{client ? "Edit Client" : "New Client"}</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors duration-200"><X size={20} /></button>
        </div>
        <div className="p-5 grid grid-cols-2 gap-4">
          {[["name", "Client Name"], ["industry", "Industry"], ["website", "Website"], ["contact_email", "Contact Email"], ["notes", "Notes"]].map(F)}
        </div>
        <div className="px-5 py-4 border-t border-border flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-zinc-800 hover:border-zinc-600 transition-colors duration-200">Cancel</button>
          <button onClick={submit} disabled={busy} data-testid="save-client-btn" className="px-4 py-2 text-sm bg-[#FF3B30] text-white hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">{busy ? "Saving" : "Save"}</button>
        </div>
      </div>
    </div>
  );
}
