import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import {
  Brain as BrainIcon, LinkSimple, FileText, ShieldCheck, MagnifyingGlass,
  Trash, Plus, Sparkle, CaretRight, Globe,
} from "@phosphor-icons/react";

export default function Brain() {
  const [sources, setSources] = useState([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [mode, setMode] = useState("webpage");
  const [url, setUrl] = useState("");
  const [content, setContent] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [searching, setSearching] = useState(false);
  const [load, setLoad] = useState(true);

  const loadSources = () =>
    api.get("/brain/sources").then((r) => { setSources(r.data); setLoad(false); }).catch(() => setLoad(false));

  useEffect(() => { loadSources(); }, []);

  const ingest = async () => {
    if (mode === "webpage" && !url.trim()) return toast.error("Enter a website URL");
    if (mode === "document" && !content.trim()) return toast.error("Paste your document content");
    setBusy(true);
    try {
      const { data } = await api.post("/brain/ingest", {
        url: url || undefined,
        title: title || undefined,
        content: content || undefined,
        kind: mode,
      });
      toast.success(data.message);
      loadSources();
      setUrl(""); setTitle(""); setContent("");
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (s) => {
    setBusy(true);
    try {
      await api.delete(`/brain/sources/${s.id}`);
      toast.success(`Removed "${s.title}" and its chunks`);
      loadSources();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  const search = async () => {
    if (query.trim().length < 3) return toast.error("Enter a longer query");
    setSearching(true);
    try {
      const { data } = await api.post("/brain/query", { query, top_k: 6, with_answer: true });
      setResults(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Module A — Business Brain"
        title="Business Brain"
        description="This is the engine's memory. Every piece of content you ingest — website pages, documents, claims, past campaigns — grounds the AI so it never hallucinates your business facts. All generation pulls approved context with source attribution."
        action={
          <div className="hidden sm:flex items-center gap-2 text-[10px] uppercase tracking-wider font-mono text-zinc-500 border border-border px-3 py-1.5">
            <ShieldCheck size={13} className="text-[#2563EB]" /> Source-attributed retrieval
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ingest */}
        <div className="space-y-4">
          <Section title="Add Knowledge">
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setMode("webpage")}
                className={`flex-1 flex items-center justify-center gap-2 border px-3 py-2 text-xs uppercase tracking-wider ${mode === "webpage" ? "border-[#2563EB] text-[#2563EB] bg-[#EFF6FF]" : "border-border text-zinc-500"}`}
              >
                <Globe size={14} /> Website
              </button>
              <button
                onClick={() => setMode("document")}
                className={`flex-1 flex items-center justify-center gap-2 border px-3 py-2 text-xs uppercase tracking-wider ${mode === "document" ? "border-[#2563EB] text-[#2563EB] bg-[#EFF6FF]" : "border-border text-zinc-500"}`}
              >
                <FileText size={14} /> Document
              </button>
            </div>
            <div className="space-y-4">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Knowledge title (optional)"
                className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
              />
              {mode === "webpage" ? (
                <input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://yourcompany.com — will crawl & chunk"
                  className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
                />
              ) : (
                <textarea
                  rows={6}
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Paste your document: product claims, FAQs, pricing, positioning, past campaign learnings…"
                  className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB] resize-none"
                />
              )}
              {mode === "webpage" && (
                <textarea
                  rows={3}
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Additional notes to ingest (optional)"
                  className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB] resize-none"
                />
              )}
              <button
                onClick={ingest}
                disabled={busy}
                className="w-full bg-[#2563EB] text-white text-xs uppercase tracking-[0.15em] py-3 hover:bg-[#1D4ED8] disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {busy ? <><CircleNotch size={15} className="animate-spin" /> Ingesting…</> : <><Plus size={15} /> Add to Brain</>}
              </button>
              <p className="text-[11px] text-zinc-500">
                Content is chunked, vector-embedded and keyword-indexed, then scoped to your workspace. Re-ingesting the same URL replaces the old chunks.
              </p>
            </div>
          </Section>

          <Section title="Knowledge Sources">
            {load ? <Loader label="Loading sources" /> : sources.length === 0 ? (
              <div className="text-xs text-zinc-500 font-mono">No sources yet. Add your website or documents.</div>
            ) : (
              <div className="space-y-2">
                {sources.map((s) => (
                  <div key={s.id} className="border border-border px-3 py-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{s.title || s.url}</div>
                        <div className="flex items-center gap-2 mt-1 text-[10px] uppercase tracking-wider font-mono text-zinc-500">
                          <span>{s.kind}</span>
                          <span>{s.chunk_count} chunks</span>
                          <span>{s.char_count?.toLocaleString()} chars</span>
                        </div>
                      </div>
                      <button
                        onClick={() => remove(s)}
                        disabled={busy}
                        className="text-zinc-400 hover:text-red-500 shrink-0"
                        title="Remove source"
                      >
                        <Trash size={15} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Section>
        </div>

        {/* Query */}
        <div className="lg:col-span-2 space-y-4">
          <Section title="Query the Brain">
            <p className="text-sm text-zinc-500 mb-4">
              Ask anything about your business. The engine retrieves the exact passages it will use when generating
              strategies, content and outreach — so you can see and verify what the AI "knows".
            </p>
            <div className="flex gap-2">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && search()}
                placeholder="e.g. What is our pricing model and who is our target audience?"
                className="flex-1 border border-border px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-[#2563EB]"
              />
              <button
                onClick={search}
                disabled={searching}
                className="bg-zinc-950 text-white text-xs uppercase tracking-[0.15em] px-5 hover:bg-zinc-800 disabled:opacity-50 flex items-center gap-2"
              >
                {searching ? <CircleNotch size={15} className="animate-spin" /> : <MagnifyingGlass size={15} />}
                Retrieve
              </button>
            </div>
          </Section>

          {searching && <Loader label="Retrieving business context" />}

          {!searching && results && (
            <Fade>
              {results.results.length === 0 ? (
                <Section>
                  <p className="text-sm text-zinc-500">No matching context found. Add more knowledge sources covering this topic.</p>
                </Section>
              ) : (
                <div className="space-y-3">
                  {results.answer && results.answer.text && (
                    <Section title="Answer" className="border-l-4 border-l-[#16A34A]">
                      <div className="flex items-start gap-3">
                        <Sparkle size={18} className="text-[#16A34A] shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm text-zinc-800 leading-relaxed">{results.answer.text}</p>
                          <div className="flex flex-wrap items-center gap-3 mt-2 text-[10px] uppercase tracking-wider font-mono text-zinc-500">
                            <span className={`px-2 py-0.5 border ${results.answer.confidence === "high" ? "border-[#16A34A] text-[#16A34A]" : "border-zinc-400"}`}>
                              confidence: {results.answer.confidence}
                            </span>
                            {results.answer.cited_sources?.length > 0 && (
                              <span>sources: {results.answer.cited_sources.join(", ")}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </Section>
                  )}
                  <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wider font-mono text-zinc-500 border border-border px-3 py-2 bg-white">
                    <Sparkle size={12} className="text-[#2563EB]" />
                    retrieval: {results.retrieval_mode || "hybrid"} · matched terms: {results.context_terms?.join(", ")}
                  </div>
                  {results.results.map((r, i) => (
                    <div key={i} className="border border-border bg-white">
                      <div className="flex items-center justify-between gap-2 px-4 py-2.5 border-b border-border bg-zinc-50">
                        <div className="flex items-center gap-2 min-w-0">
                          {r.url ? <LinkSimple size={14} className="text-[#2563EB] shrink-0" /> : <FileText size={14} className="text-[#2563EB] shrink-0" />}
                          <span className="text-xs font-medium truncate">{r.title || r.kind}</span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {r.url && (
                            <a href={r.url} target="_blank" rel="noreferrer" className="text-[10px] uppercase tracking-wider font-mono text-[#2563EB] flex items-center gap-1">
                              <CaretRight size={11} /> source
                            </a>
                          )}
                          <span className="text-[10px] uppercase tracking-wider font-mono text-zinc-500">
                            sem {Math.round((r.semantic ?? 0) * 100)}% · kw {Math.round((r.keyword ?? 0) * 100)}%
                          </span>
                        </div>
                      </div>
                      <div className="px-4 py-3 text-sm text-zinc-700 leading-relaxed">{r.text}</div>
                    </div>
                  ))}
                </div>
              )}
            </Fade>
          )}

          <Section title="How the Brain Works">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-zinc-600">
              <div className="flex gap-2">
                <Brain size={16} className="text-[#2563EB] shrink-0" />
                <p><b className="text-zinc-900">Ingest.</b> Websites are crawled and chunked into passages, each converted to a vector embedding and a keyword index side by side.</p>
              </div>
              <div className="flex gap-2">
                <MagnifyingGlass size={16} className="text-[#2563EB] shrink-0" />
                <p><b className="text-zinc-900">Retrieve.</b> Semantic vectors catch meaning, keywords catch exact terms — the two are fused and re-ranked so every AI generation pulls the strongest workspace passages only.</p>
              </div>
              <div className="flex gap-2">
                <ShieldCheck size={16} className="text-[#2563EB] shrink-0" />
                <p><b className="text-zinc-900">Attribute.</b> Each retrieved passage keeps its source and URL, so you can verify everything the engine claims about your business.</p>
              </div>
            </div>
          </Section>
        </div>
      </div>
    </div>
  );
}
