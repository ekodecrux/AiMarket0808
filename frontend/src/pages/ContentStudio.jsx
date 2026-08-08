import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import { PenNib, Image as ImageIcon, Copy, Sparkle } from "@phosphor-icons/react";

const TEXT_TYPES = ["Blog Post", "LinkedIn Post", "Instagram Caption", "Twitter/X Post", "Facebook Post", "Email Campaign", "YouTube Script", "Whitepaper", "Case Study", "Landing Page Copy", "WhatsApp Campaign"];
const TONES = ["Professional", "Playful", "Bold", "Authoritative", "Friendly", "Luxury"];
const LANGS = ["English", "Spanish", "French", "German", "Hindi", "Arabic", "Portuguese"];

export default function ContentStudio() {
  const [tab, setTab] = useState("text");
  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="AI Content Studio"
        title="Generative Content Factory"
        description="Produce SEO-optimized, brand-compliant copy and original marketing creatives on demand."
        action={
          <div className="flex border border-border">
            {[["text", "Copywriting", PenNib], ["image", "Creatives", ImageIcon]].map(([id, label, Icon]) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                data-testid={`content-tab-${id}`}
                className={`flex items-center gap-2 px-4 py-2 text-xs uppercase tracking-wider transition-colors duration-200 ${tab === id ? "bg-[#FF3B30] text-white" : "text-zinc-500 hover:text-white"}`}
              >
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>
        }
      />
      {tab === "text" ? <TextStudio /> : <ImageStudio />}
    </div>
  );
}

function TextStudio() {
  const [form, setForm] = useState({ content_type: "Blog Post", topic: "", tone: "Professional", language: "English", keywords: "" });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const generate = async () => {
    if (!form.topic) return toast.error("Topic is required");
    setBusy(true); setResult(null);
    try {
      const { data } = await api.post("/content/generate", form);
      setResult(data.result);
      toast.success("Content generated");
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };

  const copy = (t) => { navigator.clipboard.writeText(t); toast.success("Copied"); };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Section title="Brief" className="lg:col-span-1 self-start">
        <div className="space-y-4">
          <SelectField label="Content Type" value={form.content_type} options={TEXT_TYPES} onChange={(v) => setForm({ ...form, content_type: v })} testid="content-type" />
          <div>
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Topic</label>
            <textarea rows={3} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} data-testid="content-topic"
              placeholder="What should the AI write about?"
              className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200 resize-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <SelectField label="Tone" value={form.tone} options={TONES} onChange={(v) => setForm({ ...form, tone: v })} testid="content-tone" />
            <SelectField label="Language" value={form.language} options={LANGS} onChange={(v) => setForm({ ...form, language: v })} testid="content-language" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Keywords (optional)</label>
            <input value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} data-testid="content-keywords"
              className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200" />
          </div>
          <button onClick={generate} disabled={busy} data-testid="generate-content-btn"
            className="w-full flex items-center justify-center gap-2 bg-[#FF3B30] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">
            <Sparkle size={16} weight="fill" /> {busy ? "Writing" : "Generate"}
          </button>
        </div>
      </Section>

      <div className="lg:col-span-2">
        {busy && <Section><Loader label="Content Agent is writing" /></Section>}
        {!busy && !result && <Section><div className="text-center py-16 text-zinc-500"><PenNib size={40} className="mx-auto mb-4 text-zinc-700" /><div className="text-sm">Generated copy appears here.</div></div></Section>}
        {result && !result._error && (
          <Fade><div className="space-y-4">
            <Section title="Generated Content">
              <div className="flex items-start justify-between gap-4">
                <h3 className="font-display text-xl">{result.title}</h3>
                <button onClick={() => copy(`${result.title}\n\n${result.body}`)} data-testid="copy-content-btn" className="text-zinc-500 hover:text-white transition-colors duration-200"><Copy size={18} /></button>
              </div>
              <p className="text-sm text-zinc-700 whitespace-pre-wrap leading-relaxed mt-4">{result.body}</p>
              {result.cta && <div className="mt-4 pt-4 border-t border-border text-sm"><span className="text-zinc-500 uppercase text-xs tracking-wider">CTA · </span>{result.cta}</div>}
            </Section>
            {(result.hashtags?.length || result.seo_keywords?.length) && (
              <Section title="SEO & Distribution">
                {result.hashtags?.length > 0 && <div className="flex flex-wrap gap-2 mb-3">{result.hashtags.map((h, i) => <span key={i} className="text-xs font-mono text-[#007AFF] border border-[#007AFF]/30 px-2 py-1">{h}</span>)}</div>}
                {result.seo_keywords?.length > 0 && <div className="flex flex-wrap gap-2">{result.seo_keywords.map((k, i) => <span key={i} className="text-xs font-mono text-zinc-500 border border-zinc-200 px-2 py-1">{k}</span>)}</div>}
                {result.meta_description && <p className="text-xs text-zinc-500 mt-3"><span className="uppercase tracking-wider">Meta · </span>{result.meta_description}</p>}
              </Section>
            )}
          </div></Fade>
        )}
        {result?._error && <Section title="Raw Output"><pre className="text-xs text-zinc-500 whitespace-pre-wrap">{result._raw}</pre></Section>}
      </div>
    </div>
  );
}

function ImageStudio() {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("Modern marketing poster");
  const [busy, setBusy] = useState(false);
  const [gallery, setGallery] = useState([]);

  const load = () => api.get("/content").then((r) => setGallery(r.data.filter((c) => c.kind === "image"))).catch(() => {});
  useEffect(() => { load(); }, []);

  const generate = async () => {
    if (!prompt) return toast.error("Describe the creative");
    setBusy(true);
    try {
      await api.post("/content/image", { prompt, style });
      toast.success("Creative generated");
      setPrompt("");
      load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Section title="Creative Brief" className="lg:col-span-1 self-start">
        <div className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Describe your creative</label>
            <textarea rows={4} value={prompt} onChange={(e) => setPrompt(e.target.value)} data-testid="image-prompt"
              placeholder="e.g. A bold banner for a Black Friday SaaS sale with abstract red geometry"
              className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200 resize-none" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">Style</label>
            <input value={style} onChange={(e) => setStyle(e.target.value)} data-testid="image-style"
              className="w-full bg-transparent border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200" />
          </div>
          <button onClick={generate} disabled={busy} data-testid="generate-image-btn"
            className="w-full flex items-center justify-center gap-2 bg-[#FF3B30] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">
            <Sparkle size={16} weight="fill" /> {busy ? "Rendering" : "Generate Creative"}
          </button>
          <p className="text-xs text-zinc-500">Powered by Gemini Nano Banana. Rendering can take ~10-20s.</p>
        </div>
      </Section>

      <div className="lg:col-span-2">
        {busy && <Section><Loader label="Creative Agent is rendering" /></Section>}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-0">
          {gallery.map((g) => (
            <Fade key={g.id}>
              <div className="border border-border bg-white">
                <img src={g.result.image_url} alt={g.topic} className="w-full aspect-square object-cover" data-testid={`creative-${g.id}`} />
                <div className="p-3 text-xs text-zinc-500 truncate">{g.topic}</div>
              </div>
            </Fade>
          ))}
        </div>
        {!busy && gallery.length === 0 && <Section><div className="text-center py-16 text-zinc-500"><ImageIcon size={40} className="mx-auto mb-4 text-zinc-700" /><div className="text-sm">Your generated creatives appear here.</div></div></Section>}
      </div>
    </div>
  );
}

function SelectField({ label, value, options, onChange, testid }) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid}
        className="w-full bg-white border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:border-[#FF3B30] transition-colors duration-200">
        {options.map((o) => <option key={o} value={o} className="bg-white">{o}</option>)}
      </select>
    </div>
  );
}
