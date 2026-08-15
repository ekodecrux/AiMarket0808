import { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import {
  Robot, Clock, Play, Pause, PlayCircle, Trash, Plus, Gear,
  CheckCircle, XCircle, CircleNotch, ListChecks, Spinner,
} from "@phosphor-icons/react";

const KIND_COLORS = {
  learning_report: "#16A34A",
  mission_review: "#2563EB",
  lead_score_refresh: "#9333EA",
  brain_reindex: "#0D9488",
  lead_enrichment: "#9333EA",
  experiment_review: "#D97706",
  campaign_report: "#2563EB",
  custom_prompt: "#DB2777",
  content_proposal: "#DB2777",
  market_signal: "#0D9488",
};

const RECURRENCE_OPTIONS = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "interval_hours", label: "Every N hours" },
  { value: "once", label: "One time" },
];

const STATUS_STYLE = {
  completed: { color: "#16A34A", border: "border-[#16A34A]" },
  blocked: { color: "#D97706", border: "border-[#D97706]" },
  error: { color: "#DC2626", border: "border-[#DC2626]" },
  running: { color: "#2563EB", border: "border-[#2563EB]" },
  skipped: { color: "#71717A", border: "border-zinc-400" },
};

export default function Agents() {
  const [kinds, setKinds] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [runs, setRuns] = useState([]);
  const [tab, setTab] = useState("schedules");
  const [createOpen, setCreateOpen] = useState(false);
  const [busy, setBusy] = useState({});
  const [load, setLoad] = useState(true);

  const [form, setForm] = useState({
    name: "", kind: "learning_report", recurrence_kind: "daily",
    recurrence_value: "02:00", enabled: true, customPrompt: "",
  });

  const refresh = () => {
    api.get("/agents/schedules").then((r) => setSchedules(r.data)).catch(() => {});
    api.get("/agents/runs").then((r) => setRuns(r.data)).catch(() => {});
  };

  useEffect(() => {
    api.get("/agents/kinds").then((r) => {
      const list = Object.entries(r.data).map(([k, v]) => ({ id: k, ...v }));
      setKinds(list);
      setForm((f) => ({ ...f, name: list[0]?.name || f.name }));
    }).catch(() => {});
    refresh();
    setLoad(false);
  }, []);

  const create = async () => {
    if (!form.name.trim()) return toast.error("Give the task a name");
    setBusy({ creating: true });
    try {
      const params = form.kind === "custom_prompt" ? { prompt: form.customPrompt } : {};
      await api.post("/agents/schedules", {
        name: form.name, kind: form.kind,
        recurrence_kind: form.recurrence_kind,
        recurrence_value: form.recurrence_kind === "interval_hours" ? 24 : form.recurrence_value,
        enabled: form.enabled, params,
      });
      toast.success("Agent scheduled — it runs inside your autonomy policy");
      setCreateOpen(false);
      refresh();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy({ creating: false });
    }
  };

  const toggle = async (s) => {
    setBusy((b) => ({ ...b, [s.id]: "toggle" }));
    try {
      await api.post(`/agents/schedules/${s.id}/toggle`, { enabled: !s.enabled });
      refresh();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy((b) => ({ ...b, [s.id]: null }));
    }
  };

  const runNow = async (s) => {
    setBusy((b) => ({ ...b, [s.id]: "run" }));
    try {
      const { data } = await api.post(`/agents/schedules/${s.id}/run`);
      toast[data.status === "blocked" ? "warning" : "success"](
        data.status === "blocked" ? "Blocked by autonomy policy — enable autonomy or lift the kill switch" : `Task ${data.status}: ${(data.summary || "").slice(0, 100)}`
      );
      refresh();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy((b) => ({ ...b, [s.id]: null }));
    }
  };

  const remove = async (s) => {
    setBusy((b) => ({ ...b, [s.id]: "delete" }));
    try {
      await api.delete(`/agents/schedules/${s.id}`);
      toast.success("Schedule removed");
      refresh();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy((b) => ({ ...b, [s.id]: null }));
    }
  };

  const fmtTime = (iso) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch {
      return iso;
    }
  };

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Autonomous Execution"
        title="Agent Automation"
        description="Give the engine a schedule and it executes the work for you — always inside your autonomy policy. Every run is recorded, audited and reviewable. Toggle the kill switch on the Learning page to pause all autonomous execution instantly."
        action={
          <div className="hidden sm:flex items-center gap-2 text-[10px] uppercase tracking-wider font-mono text-zinc-500 border border-border px-3 py-1.5">
            <Gear size={13} className="text-[#2563EB]" /> Policy-gated execution
          </div>
        }
      />

      <div className="flex gap-2 mb-6">
        {[
          { id: "schedules", label: "Schedules", icon: Clock },
          { id: "runs", label: "Run History", icon: ListChecks },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 border px-4 py-2 text-xs uppercase tracking-wider ${tab === t.id ? "border-[#2563EB] text-[#2563EB] bg-[#EFF6FF]" : "border-border text-zinc-500"}`}
          >
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {tab === "schedules" && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-xs uppercase tracking-[0.15em] text-zinc-500">{schedules.length} scheduled {schedules.length === 1 ? "task" : "tasks"}</h3>
            <button
              onClick={() => setCreateOpen(true)}
              className="bg-[#2563EB] text-white text-xs uppercase tracking-[0.15em] px-4 py-2.5 hover:bg-[#1D4ED8] flex items-center gap-2"
            >
              <Plus size={14} /> New Schedule
            </button>
          </div>

          {load ? <Loader label="Loading schedules" /> : schedules.length === 0 ? (
            <Section>
              <p className="text-sm text-zinc-500 mb-3">No agents scheduled yet. Pick a task below to automate.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {kinds.map((k) => (
                  <button
                    key={k.id}
                    onClick={() => { setForm((f) => ({ ...f, name: k.name, kind: k.id })); setCreateOpen(true); }}
                    className="border border-border bg-white px-4 py-3 text-left hover:border-[#2563EB] transition-colors"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="w-2 h-2 rounded-full" style={{ background: KIND_COLORS[k.id] || "#2563EB" }} />
                      <span className="text-sm font-medium">{k.name}</span>
                      <span className="text-[10px] uppercase tracking-wider font-mono text-zinc-500 ml-auto">{(k.min_autonomy || "").replace("_", " ")}</span>
                    </div>
                    <p className="text-xs text-zinc-500">{k.description}</p>
                  </button>
                ))}
              </div>
            </Section>
          ) : (
            <div className="space-y-3">
              {schedules.map((s) => {
                const st = STATUS_STYLE[s.last_run_status] || STATUS_STYLE.skipped;
                return (
                  <div key={s.id} className="border border-border bg-white">
                    <div className="px-4 py-3 border-b border-border bg-zinc-50 flex flex-wrap items-center gap-2">
                      <span className="w-2 h-2 rounded-full" style={{ background: KIND_COLORS[s.kind] || "#2563EB" }} />
                      <span className="text-sm font-medium">{s.name}</span>
                      <span className="text-[10px] uppercase tracking-wider font-mono text-zinc-500">{(s.kind || "").replace("_", " ")}</span>
                      <span className={`ml-auto px-2 py-0.5 text-[10px] uppercase tracking-wider font-mono border ${s.enabled ? "border-[#16A34A] text-[#16A34A]" : "border-zinc-400 text-zinc-500"}`}>
                        {s.enabled ? "active" : "paused"}
                      </span>
                    </div>
                    <div className="px-4 py-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-zinc-600">
                      <span className="flex items-center gap-1.5 font-mono text-[11px] text-zinc-500">
                        <Clock size={13} /> {s.recurrence_kind?.replace("_", " ")}
                        {s.recurrence_kind === "interval_hours" ? " every 24h" : s.recurrence_value ? ` ${s.recurrence_value}` : ""}
                      </span>
                      <span className="font-mono text-[11px] text-zinc-500">next: {fmtTime(s.next_run_at)}</span>
                      <span className="font-mono text-[11px]" style={{ color: st.color }}>last: {s.last_run_status || "never"} · {fmtTime(s.last_run_at)}</span>
                      {s.consecutive_failures > 0 && (
                        <span className="text-[11px] font-mono text-[#DC2626]">{s.consecutive_failures} consecutive failures</span>
                      )}
                      <div className="ml-auto flex items-center gap-2">
                        <button
                          onClick={() => runNow(s)}
                          disabled={busy[s.id]}
                          className="border border-border px-3 py-1.5 text-[11px] uppercase tracking-wider flex items-center gap-1.5 hover:border-[#2563EB] hover:text-[#2563EB] disabled:opacity-50"
                        >
                          {busy[s.id] === "run" ? <CircleNotch size={12} className="animate-spin" /> : <PlayCircle size={13} />} Run now
                        </button>
                        <button
                          onClick={() => toggle(s)}
                          disabled={busy[s.id]}
                          className={`border px-3 py-1.5 text-[11px] uppercase tracking-wider flex items-center gap-1.5 disabled:opacity-50 ${s.enabled ? "border-zinc-400 hover:border-[#D97706] hover:text-[#D97706]" : "border-[#16A34A] text-[#16A34A] hover:bg-[#F0FDF4]"}`}
                        >
                          {busy[s.id] === "toggle" ? <CircleNotch size={12} className="animate-spin" /> : s.enabled ? <Pause size={13} /> : <Play size={13} />}
                          {s.enabled ? "Pause" : "Resume"}
                        </button>
                        <button
                          onClick={() => remove(s)}
                          disabled={busy[s.id]}
                          className="border border-border px-3 py-1.5 text-zinc-400 text-[11px] uppercase tracking-wider flex items-center gap-1.5 hover:border-[#DC2626] hover:text-[#DC2626] disabled:opacity-50"
                        >
                          <Trash size={13} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {tab === "runs" && (
        <Fade>
          {runs.length === 0 ? (
            <Section>
              <p className="text-sm text-zinc-500">No runs yet. Trigger a task from the Schedules tab to see its history here.</p>
            </Section>
          ) : (
            <div className="space-y-2">
              {runs.map((r) => {
                const st = STATUS_STYLE[r.status] || STATUS_STYLE.skipped;
                return (
                  <div key={r.id} className="border border-border bg-white px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${r.status === "running" ? "animate-pulse" : ""}`} style={{ background: st.color }} />
                      <span className="text-sm font-medium">{r.name}</span>
                      <span className={`px-2 py-0.5 text-[10px] uppercase tracking-wider font-mono border ${st.border}`} style={{ color: st.color }}>{r.status}</span>
                      <span className="text-[10px] uppercase tracking-wider font-mono text-zinc-500">{r.trigger || "manual"}</span>
                      <span className="ml-auto text-[10px] uppercase tracking-wider font-mono text-zinc-500">{fmtTime(r.started_at)} · {r.duration_seconds ? `${r.duration_seconds}s` : "—"}</span>
                    </div>
                    {r.summary && <p className="text-xs text-zinc-600 mt-1.5 leading-relaxed">{r.summary}</p>}
                  </div>
                );
              })}
            </div>
          )}
        </Fade>
      )}

      {createOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-start justify-center pt-24 px-4" onClick={() => setCreateOpen(false)}>
          <div className="bg-white border border-border w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-3 border-b border-border text-xs uppercase tracking-[0.15em] text-zinc-500 flex items-center justify-between">
              <span className="flex items-center gap-2"><Robot size={14} className="text-[#2563EB]" /> New Scheduled Task</span>
              <button onClick={() => setCreateOpen(false)} className="text-zinc-400 hover:text-zinc-700"><XCircle size={16} /></button>
            </div>
            <div className="p-5 space-y-4">
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Task name"
                className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
              />
              <div>
                <label className="block text-[10px] uppercase tracking-wider font-mono text-zinc-500 mb-1.5">Task kind</label>
                <select
                  value={form.kind}
                  onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value }))}
                  className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                >
                  {kinds.map((k) => (
                    <option key={k.id} value={k.id}>{k.name} — {k.description}</option>
                  ))}
                </select>
              </div>
              {form.kind === "custom_prompt" && (
                <textarea
                  rows={4}
                  value={form.customPrompt}
                  onChange={(e) => setForm((f) => ({ ...f, customPrompt: e.target.value }))}
                  placeholder="Ask anything about your business — it runs against your Business Brain context…"
                  className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB] resize-none"
                />
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] uppercase tracking-wider font-mono text-zinc-500 mb-1.5">Frequency</label>
                  <select
                    value={form.recurrence_kind}
                    onChange={(e) => setForm((f) => ({ ...f, recurrence_kind: e.target.value }))}
                    className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                  >
                    {RECURRENCE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
                {form.recurrence_kind === "daily" && (
                  <div>
                    <label className="block text-[10px] uppercase tracking-wider font-mono text-zinc-500 mb-1.5">Time (UTC)</label>
                    <input
                      type="time"
                      value={form.recurrence_value}
                      onChange={(e) => setForm((f) => ({ ...f, recurrence_value: e.target.value }))}
                      className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                    />
                  </div>
                )}
                {form.recurrence_kind === "weekly" && (
                  <div>
                    <label className="block text-[10px] uppercase tracking-wider font-mono text-zinc-500 mb-1.5">Day</label>
                    <select
                      value={(form.recurrence_value || "mon 02:00").split(" ")[0]}
                      onChange={(e) => {
                        const time = (form.recurrence_value || "mon 02:00").split(" ")[1] || "02:00";
                        setForm((f) => ({ ...f, recurrence_value: `${e.target.value} ${time}` }));
                      }}
                      className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                    >
                      {["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between text-sm text-zinc-600 pt-1">
                <span>Start enabled</span>
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, enabled: !f.enabled }))}
                  className={`relative w-10 h-5 rounded-full border transition-colors ${form.enabled ? "bg-[#2563EB] border-[#2563EB]" : "bg-zinc-200 border-zinc-300"}`}
                >
                  <span className={`absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white transition-all ${form.enabled ? "left-5" : "left-0.5"}`} />
                </button>
              </div>
              <button
                onClick={create}
                disabled={busy.creating}
                className="w-full bg-[#2563EB] text-white text-xs uppercase tracking-[0.15em] py-3 hover:bg-[#1D4ED8] disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {busy.creating ? <CircleNotch size={15} className="animate-spin" /> : <CheckCircle size={15} />} Create schedule
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function formatApiError(detail) {
  if (!detail) return "Something went wrong";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg || String(d)).join("; ");
  return detail?.message || JSON.stringify(detail);
}
