import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import { Sparkle, CalendarPlus, Trash, PaperPlaneTilt, Copy } from "@phosphor-icons/react";
import { LinkedinLogo, FacebookLogo, InstagramLogo, XLogo, YoutubeLogo, TiktokLogo, RedditLogo, PinterestLogo } from "@phosphor-icons/react";

const PLATFORMS = [
  { id: "LinkedIn", icon: LinkedinLogo }, { id: "Facebook", icon: FacebookLogo },
  { id: "Instagram", icon: InstagramLogo }, { id: "Twitter/X", icon: XLogo },
  { id: "YouTube", icon: YoutubeLogo }, { id: "TikTok", icon: TiktokLogo },
  { id: "Reddit", icon: RedditLogo }, { id: "Pinterest", icon: PinterestLogo },
];

export default function Social() {
  const [platform, setPlatform] = useState("LinkedIn");
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState(null);
  const [when, setWhen] = useState("");
  const [posts, setPosts] = useState([]);

  const load = () => api.get("/social/posts").then((r) => setPosts(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const generate = async () => {
    if (!topic) return toast.error("Enter a topic");
    setBusy(true); setDraft(null);
    try {
      const { data } = await api.post("/social/generate", { platform, topic });
      const text = `${data.content || ""}\n\n${(data.hashtags || []).join(" ")}`.trim();
      setDraft({ ...data, text });
      toast.success("Draft ready");
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };

  const schedule = async () => {
    if (!draft) return;
    try {
      await api.post("/social/schedule", { platform, content: draft.text, scheduled_time: when || new Date().toISOString() });
      toast.success("Scheduled to content calendar");
      setDraft(null); setTopic(""); setWhen(""); load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const publish = async (id) => { await api.patch(`/social/posts/${id}/publish`); toast.success("Marked published"); load(); };
  const del = async (id) => { await api.delete(`/social/posts/${id}`); load(); };

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Social Media Manager"
        title="AI Content Calendar"
        description="Generate platform-native posts with AI and schedule them. Publishing posts live to a network requires that network's credentials in Settings."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <Section title="Compose">
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Platform</label>
            <div className="grid grid-cols-4 gap-2 mb-4">
              {PLATFORMS.map((p) => (
                <button key={p.id} onClick={() => setPlatform(p.id)} data-testid={`platform-${p.id}`}
                  className={`aspect-square flex items-center justify-center border transition-colors duration-200 ${platform === p.id ? "border-[#FF3B30] text-[#FF3B30] bg-[#FF3B30]/5" : "border-zinc-200 text-zinc-500 hover:text-white"}`}
                  title={p.id}>
                  <p.icon size={20} />
                </button>
              ))}
            </div>
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Topic</label>
            <textarea rows={3} value={topic} onChange={(e) => setTopic(e.target.value)} data-testid="social-topic"
              placeholder={`What should the ${platform} post be about?`}
              className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200 resize-none mb-4" />
            <button onClick={generate} disabled={busy} data-testid="generate-social-btn"
              className="w-full flex items-center justify-center gap-2 bg-[#FF3B30] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">
              <Sparkle size={16} weight="fill" /> {busy ? "Writing" : "Generate Post"}
            </button>
          </Section>

          {draft && (
            <Fade><Section title={`Draft · ${platform}`}>
              <div className="flex justify-end mb-2"><button onClick={() => { navigator.clipboard.writeText(draft.text); toast.success("Copied"); }} className="text-zinc-500 hover:text-white transition-colors duration-200"><Copy size={16} /></button></div>
              <p className="text-sm text-zinc-700 whitespace-pre-wrap leading-relaxed" data-testid="social-draft">{draft.text}</p>
              {draft.best_time && <div className="text-xs text-zinc-500 mt-3">AI suggested time: <span className="text-[#FFCC00] font-mono">{draft.best_time}</span></div>}
              <div className="mt-4 pt-4 border-t border-border">
                <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Schedule for</label>
                <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} data-testid="social-schedule-time"
                  className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm text-zinc-700 focus:outline-none focus:border-[#FF3B30] transition-colors duration-200 mb-3" />
                <button onClick={schedule} data-testid="schedule-social-btn"
                  className="w-full flex items-center justify-center gap-2 border border-zinc-300 py-2.5 text-sm uppercase tracking-wider hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors duration-200">
                  <CalendarPlus size={16} /> Add to Calendar
                </button>
              </div>
            </Section></Fade>
          )}
        </div>

        <div className="lg:col-span-2">
          <Section title={`Content Calendar · ${posts.length}`}>
            {posts.length === 0 ? (
              <div className="text-center py-16 text-zinc-500 text-sm">No scheduled posts yet. Generate and schedule one.</div>
            ) : (
              <div className="space-y-3">
                {posts.map((p) => {
                  const P = PLATFORMS.find((x) => x.id === p.platform);
                  const Icon = P?.icon || PaperPlaneTilt;
                  return (
                    <Fade key={p.id}>
                      <div className="border border-zinc-200 p-4" data-testid={`social-post-${p.id}`}>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2 text-sm"><Icon size={16} className="text-[#FF3B30]" /> {p.platform}</div>
                          <span className={`text-xs px-2 py-0.5 border ${p.status === "Published" ? "text-[#34C759] border-[#34C759]/40" : "text-[#FFCC00] border-[#FFCC00]/40"}`}>{p.status}</span>
                        </div>
                        <p className="text-sm text-zinc-700 whitespace-pre-wrap leading-relaxed line-clamp-4">{p.content}</p>
                        <div className="flex items-center justify-between mt-3 pt-3 border-t border-zinc-900">
                          <span className="text-xs font-mono text-zinc-500">{p.scheduled_time ? new Date(p.scheduled_time).toLocaleString() : "—"}</span>
                          <div className="flex items-center gap-2">
                            {p.status !== "Published" && <button onClick={() => publish(p.id)} data-testid={`publish-${p.id}`} className="flex items-center gap-1 text-xs border border-zinc-200 px-2 py-1 hover:border-[#34C759] hover:text-[#34C759] transition-colors duration-200"><PaperPlaneTilt size={12} /> Publish</button>}
                            <button onClick={() => del(p.id)} className="text-zinc-500 hover:text-[#FF3B30] transition-colors duration-200"><Trash size={14} /></button>
                          </div>
                        </div>
                      </div>
                    </Fade>
                  );
                })}
              </div>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}
