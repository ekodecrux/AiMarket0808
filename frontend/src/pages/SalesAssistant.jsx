import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import { EnvelopeSimple, WhatsappLogo, ShieldCheck, NotePencil, Copy, PaperPlaneTilt } from "@phosphor-icons/react";

const ACTIONS = [
  { id: "follow_up_email", label: "Follow-up Email", icon: EnvelopeSimple },
  { id: "whatsapp", label: "WhatsApp Message", icon: WhatsappLogo },
  { id: "objection_handling", label: "Objection Handling", icon: ShieldCheck },
  { id: "summary", label: "Summary & Next Action", icon: NotePencil },
];

export default function SalesAssistant() {
  const [leads, setLeads] = useState([]);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(null);
  const [result, setResult] = useState(null);
  const [sending, setSending] = useState(false);
  const [lastAction, setLastAction] = useState(null);

  useEffect(() => { api.get("/leads").then((r) => { setLeads(r.data); if (r.data[0]) setSelected(r.data[0].id); }).catch(() => {}); }, []);

  const run = async (action) => {
    if (!selected) return toast.error("Select a lead");
    setBusy(action); setResult(null);
    try {
      const { data } = await api.post("/sales/assist", { lead_id: selected, action });
      setResult(data.result);
      setLastAction(action);
      toast.success("Generated");
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(null); }
  };

  const sendEmail = async () => {
    if (!result?.message) return;
    setSending(true);
    try {
      await api.post("/sales/send-email", { lead_id: selected, subject: result.title || "A quick note", message: result.message });
      toast.success("Email sent via AIMarketing");
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setSending(false); }
  };

  const lead = leads.find((l) => l.id === selected);

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="AI Sales Assistant"
        title="Convert & Nurture"
        description="The Sales Agent drafts follow-ups, handles objections and recommends the next best action for any lead."
      />

      {leads.length === 0 ? (
        <Section><div className="text-center py-16 text-zinc-500 text-sm">Add leads first in Lead Management to use the Sales Assistant.</div></Section>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-4">
            <Section title="Select Lead">
              <select value={selected} onChange={(e) => setSelected(e.target.value)} data-testid="sales-lead-select"
                className="w-full bg-white border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200">
                {leads.map((l) => <option key={l.id} value={l.id}>{l.name} — {l.company}</option>)}
              </select>
              {lead && (
                <div className="mt-4 pt-4 border-t border-border text-sm space-y-1">
                  <div className="text-zinc-500">{lead.role || "—"}</div>
                  <div className="text-zinc-500 text-xs">{lead.email}</div>
                  <div className="text-xs"><span className="text-zinc-500">Category: </span><span className="text-[#FF3B30]">{lead.category}</span></div>
                </div>
              )}
            </Section>
            <Section title="AI Actions">
              <div className="space-y-2">
                {ACTIONS.map((a) => (
                  <button key={a.id} onClick={() => run(a.id)} disabled={busy} data-testid={`sales-action-${a.id}`}
                    className="w-full flex items-center gap-3 px-3 py-3 border border-zinc-200 text-sm hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors duration-200 disabled:opacity-40">
                    <a.icon size={18} /> {busy === a.id ? "Generating..." : a.label}
                  </button>
                ))}
              </div>
            </Section>
          </div>

          <div className="lg:col-span-2">
            {busy && <Section><Loader label="Sales Agent is drafting" /></Section>}
            {!busy && !result && <Section><div className="text-center py-16 text-zinc-500"><EnvelopeSimple size={40} className="mx-auto mb-4 text-zinc-700" /><div className="text-sm">Pick an AI action to draft a message.</div></div></Section>}
            {result && !result._error && (
              <Fade><Section title={
                <div className="flex items-center justify-between w-full">
                  <span>{result.title}</span>
                  <div className="flex items-center gap-3">
                    {lastAction === "follow_up_email" && (
                      <button onClick={sendEmail} disabled={sending} data-testid="send-email-btn"
                        className="flex items-center gap-1.5 text-xs border border-[#34C759]/40 text-[#34C759] px-3 py-1.5 hover:bg-[#34C759]/10 transition-colors duration-200 disabled:opacity-40">
                        <PaperPlaneTilt size={13} /> {sending ? "Sending" : "Send Email"}
                      </button>
                    )}
                    <button onClick={() => { navigator.clipboard.writeText(result.message); toast.success("Copied"); }} data-testid="copy-sales-btn" className="text-zinc-500 hover:text-white transition-colors duration-200"><Copy size={16} /></button>
                  </div>
                </div>
              }>
                <p className="text-sm text-zinc-700 whitespace-pre-wrap leading-relaxed">{result.message}</p>
              </Section></Fade>
            )}
            {result?._error && <Section title="Raw Output"><pre className="text-xs text-zinc-500 whitespace-pre-wrap">{result._raw}</pre></Section>}
          </div>
        </div>
      )}
    </div>
  );
}
