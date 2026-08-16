import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, Loader, Fade, Section } from "@/components/common";
import { toast } from "sonner";
import {
  MagnifyingGlass, FileText, CheckCircle, XCircle, X,
  Spinner, Globe, LinkSimple, Lightning, TrendUp, Plus,
} from "@phosphor-icons/react";

export default function Seo() {
  const [tab, setTab] = useState("audit");
  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="SEO & Keyword Intelligence"
        title="Organic Growth Engine"
        description="NEXUS crawls your website for technical SEO findings, researches revenue-weighted keywords from your seeds, competitors and industry, clusters them by topic and intent, and produces execution-ready content briefs."
        action={
          <div className="flex border border-border">
            {[
              ["audit", "Technical Audit", MagnifyingGlass],
              ["keywords", "Keyword Research", Lightning],
              ["briefs", "Content Briefs", FileText],
            ].map(([id, label, Icon]) => (
              <button key={id} onClick={() => setTab(id)} data-testid={`seo-tab-${id}`}
                className={`flex items-center gap-2 px-4 py-2 text-xs uppercase tracking-wider transition-colors duration-200 ${tab === id ? "bg-[#2563EB] text-white" : "text-zinc-500 hover:text-zinc-950"}`}>
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>
        }
      />
      {tab === "audit" ? <Audit /> : tab === "keywords" ? <Keywords /> : <Briefs />}
    </div>
  );
}

// ---------------- Technical SEO Audit ----------------
function Audit() {
  const [site, setSite] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const runAudit = async () => {
    if (!site.trim()) { toast.error("Enter your website URL"); return; }
    let url = site.trim();
    if (!url.startsWith("http")) url = "https://" + url;
    setLoading(true);
    try {
      const { data } = await api.post("/seo/audit", { url });
      setResult(data);
      toast.success(`Technical audit complete — ${data.pages_audited} pages analyzed`);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setLoading(false); }
  };

  return (
    <div>
      <div className="flex gap-3 mb-8 items-center">
        <input value={site} onChange={(e) => setSite(e.target.value)}
          placeholder="https://yourcompany.com"
          className="flex-1 border border-border px-4 py-3 text-sm bg-white focus:outline-none focus:border-[#2563EB] transition-colors" />
        <button onClick={runAudit} disabled={loading}
          className="flex items-center gap-2 bg-[#2563EB] text-white px-5 py-3 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] disabled:opacity-60 transition-colors duration-200">
          {loading ? <Spinner size={15} className="animate-spin" /> : <Globe size={15} />}
          {loading ? "Crawling..." : "Run Audit"}
        </button>
      </div>
      {!result && !loading && (
        <Section>
          <div className="text-center py-16 text-zinc-500 text-sm">
            Enter your website to crawl it. NEXUS audits title tags, meta descriptions, headings,
            canonicals, structured data, image alt text and content depth across your pages.
          </div>
        </Section>
      )}
      {loading && <Loader label="Crawling pages" />}
      {result && (
        <div className="space-y-8">
          <Fade>
            <Section>
              <div className="flex items-center justify-between mb-4">
                <div className="text-sm uppercase tracking-wider text-zinc-500">Audit Summary</div>
                <div className="flex items-center gap-2">
                  <span className={`text-2xl font-semibold ${result.score >= 80 ? "text-green-600" : result.score >= 60 ? "text-amber-600" : "text-red-600"}`}>
                    {result.score}
                  </span>
                  <span className="text-xs text-zinc-500">/ 100</span>
                </div>
              </div>
              <div className="text-sm text-zinc-700">{result.pages_audited} page(s) audited at {result.site}</div>
            </Section>
          </Fade>
          <Fade>
            <Section>
              <div className="text-sm uppercase tracking-wider text-zinc-500 mb-4">Recurring Issues (fix first)</div>
              {result.recurring_issues.length === 0 ? (
                <div className="text-sm text-green-600 flex items-center gap-2"><CheckCircle size={15} /> No recurring issues found</div>
              ) : (
                <div className="divide-y divide-border">
                  {result.recurring_issues.map((r, i) => (
                    <div key={i} className="py-3 flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2 text-zinc-800"><XCircle size={15} className="text-red-500" /> {r.issue}</div>
                      <div className="text-xs text-zinc-500">{r.pages_affected} page(s)</div>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          </Fade>
          {result.audits.map((a, i) => (
            <Fade key={i}>
              <Section>
                <div className="flex items-center gap-2 text-sm font-medium mb-3">
                  <LinkSimple size={15} /> <a href={a.url} target="_blank" rel="noreferrer" className="text-[#2563EB]">{a.url}</a>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-4">
                  <Stat label="Words" value={a.word_count} />
                  <Stat label="Images" value={`${a.images_missing_alt} missing alt`} />
                  <Stat label="Title" value={a.title || "(none)"} long />
                  <Stat label="Schema" value={a.schema.length ? a.schema.join(", ") : "(none)"} long />
                </div>
                <div className="space-y-1.5">
                  {a.issues.map((x, j) => (
                    <div key={j} className="text-sm flex items-center gap-2 text-red-600"><XCircle size={13} /> {x}</div>
                  ))}
                  {a.strengths.map((x, j) => (
                    <div key={j} className="text-sm flex items-center gap-2 text-green-600"><CheckCircle size={13} /> {x}</div>
                  ))}
                  {a.issues.length === 0 && a.strengths.length === 0 && (
                    <div className="text-sm text-zinc-500">No findings</div>
                  )}
                </div>
              </Section>
            </Fade>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, long }) {
  return (
    <div className="border border-border p-3">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={`mt-1 text-zinc-800 ${long ? "truncate" : "font-medium"}`} title={value}>{value}</div>
    </div>
  );
}

// ---------------- Keyword Research ----------------
function Keywords() {
  const [seeds, setSeeds] = useState("");
  const [industry, setIndustry] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const run = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/seo/keywords", {
        seeds: seeds.split(",").map((s) => s.trim()).filter(Boolean),
        industry: industry.trim() || "SaaS",
      });
      setResult(data);
      toast.success(`Researched ${(data.keywords || []).length} keywords with revenue-weighted scoring`);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setLoading(false); }
  };

  const byPriority = (result?.keywords || []).slice().sort((a, b) => (b.priority_score || 0) - (a.priority_score || 0));

  return (
    <div>
      <div className="flex gap-3 mb-6 flex-wrap items-center">
        <input value={seeds} onChange={(e) => setSeeds(e.target.value)}
          placeholder="Seed keywords — e.g. crm software, sales pipeline tool"
          className="flex-1 min-w-64 border border-border px-4 py-3 text-sm bg-white focus:outline-none focus:border-[#2563EB] transition-colors" />
        <input value={industry} onChange={(e) => setIndustry(e.target.value)}
          placeholder="Industry — e.g. SaaS"
          className="w-56 border border-border px-4 py-3 text-sm bg-white focus:outline-none focus:border-[#2563EB] transition-colors" />
        <button onClick={run} disabled={loading}
          className="flex items-center gap-2 bg-[#2563EB] text-white px-5 py-3 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] disabled:opacity-60 transition-colors duration-200">
          {loading ? <Spinner size={15} className="animate-spin" /> : <Lightning size={15} />}
          {loading ? "Researching..." : "Research Keywords"}
        </button>
      </div>
      {!result && !loading && (
        <Section>
          <div className="text-center py-16 text-zinc-500 text-sm">
            Provide seed keywords and your industry. NEXUS discovers keywords from your seeds, your
            tracked competitors and industry content gaps, clusters them by topic and intent, and scores
            each keyword for commercial intent, ranking feasibility and predicted conversion value —
            so the priority list connects keywords to pipeline and revenue, not vanity volume.
          </div>
        </Section>
      )}
      {loading && <Loader label="Researching keywords" />}
      {result && (
        <div className="space-y-8">
          <Fade>
            <Section>
              <div className="text-sm uppercase tracking-wider text-zinc-500 mb-3">Priority Cluster Summary</div>
              {(result.cluster_summary?.clusters || []).length === 0 ? (
                <div className="text-sm text-zinc-500">No cluster summary returned</div>
              ) : (
                <div className="grid md:grid-cols-3 gap-4">
                  {result.cluster_summary.clusters.map((c, i) => (
                    <div key={i} className="border border-border p-4">
                      <div className="font-medium text-sm text-zinc-900">{c.name}</div>
                      <div className="text-xs text-zinc-500 mt-1">{c.keyword_count} keywords · priority {c.priority}</div>
                      <div className="text-xs text-zinc-600 mt-2">{c.revenue_potential}</div>
                    </div>
                  ))}
                </div>
              )}
              {(result.content_gaps || []).length > 0 && (
                <>
                  <div className="text-sm uppercase tracking-wider text-zinc-500 mb-3 mt-6">Content Gaps vs Competitors</div>
                  <div className="space-y-1.5">
                    {result.content_gaps.map((g, i) => (
                      <div key={i} className="text-sm flex items-center gap-2 text-zinc-700"><MagnifyingGlass size={13} className="text-amber-500" /> {g}</div>
                    ))}
                  </div>
                </>
              )}
            </Section>
          </Fade>
          <Fade>
            <Section>
              <div className="text-sm uppercase tracking-wider text-zinc-500 mb-4">Keyword Scoreboard — sorted by priority</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-zinc-500 border-b border-border">
                      <th className="py-2 pr-3">Keyword</th><th className="py-2 pr-3">Cluster</th>
                      <th className="py-2 pr-3">Intent</th><th className="py-2 pr-3">Demand</th>
                      <th className="py-2 pr-3">Comm.</th><th className="py-2 pr-3">Feasibility</th>
                      <th className="py-2 pr-3">Funnel</th><th className="py-2 pr-3">Content Type</th>
                      <th className="py-2 pr-3 text-right">Priority</th><th className="py-2">Why</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byPriority.map((k, i) => (
                      <tr key={i} className="border-b border-border/60 hover:bg-zinc-50/60">
                        <td className="py-2.5 pr-3 font-medium whitespace-nowrap">{k.keyword}</td>
                        <td className="py-2.5 pr-3 text-zinc-600 whitespace-nowrap">{k.topic_cluster}</td>
                        <td className="py-2.5 pr-3"><IntentBadge intent={k.search_intent} /></td>
                        <td className="py-2.5 pr-3 text-zinc-600">{k.demand}</td>
                        <td className="py-2.5 pr-3">{Math.round((k.commercial_intent || 0) * 100)}%</td>
                        <td className="py-2.5 pr-3">{Math.round((k.ranking_feasibility || 0) * 100)}% · {k.competition}</td>
                        <td className="py-2.5 pr-3 text-zinc-600 uppercase">{k.funnel_stage}</td>
                        <td className="py-2.5 pr-3 text-zinc-600 whitespace-nowrap">{k.recommended_content_type}</td>
                        <td className="py-2.5 pr-3 text-right"><Priority value={k.priority_score} /></td>
                        <td className="py-2.5 text-zinc-500 text-xs max-w-56">{k.why}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          </Fade>
        </div>
      )}
    </div>
  );
}

function IntentBadge({ intent }) {
  const cls = {
    transactional: "bg-green-100 text-green-700",
    commercial: "bg-amber-100 text-amber-700",
    informational: "bg-zinc-100 text-zinc-600",
    navigational: "bg-blue-100 text-blue-700",
  }[intent] || "bg-zinc-100 text-zinc-600";
  return <span className={`text-[10px] px-1.5 py-0.5 rounded ${cls} uppercase tracking-wide`}>{intent}</span>;
}

function Priority({ value }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div className="flex items-center justify-end gap-2">
      <div className="w-14 h-1.5 bg-zinc-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${pct >= 70 ? "bg-green-500" : pct >= 45 ? "bg-amber-500" : "bg-zinc-400"}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-medium">{pct}</span>
    </div>
  );
}

// ---------------- Content Briefs ----------------
function Briefs() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get("/seo/keywords").then((r) => {
      const items = r.data || [];
      const latest = items[0];
      if (latest?.result?.keywords) setResult(latest.result);
    }).catch(() => {});
  }, []);

  const run = async () => {
    if (!result || !result.keywords?.length) { toast.error("Run Keyword Research first to get keywords to brief"); return; }
    setLoading(true);
    try {
      const { data } = await api.post("/seo/briefs", {
        keywords: result.keywords.slice(0, 12),
        industry: result.cluster_summary ? "" : "",
      });
      setResult((r) => ({ ...r, briefs: data.briefs, site_architecture_notes: data.site_architecture_notes }));
      toast.success(`Generated ${data.briefs?.length || 0} content briefs`);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setLoading(false); }
  };

  return (
    <div>
      <div className="flex justify-end mb-6">
        <button onClick={run} disabled={loading}
          className="flex items-center gap-2 bg-[#2563EB] text-white px-5 py-3 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] disabled:opacity-60 transition-colors duration-200">
          {loading ? <Spinner size={15} className="animate-spin" /> : <Plus size={15} />}
          {loading ? "Generating..." : "Generate Briefs"}
        </button>
      </div>
      {!result && !loading && (
        <Section>
          <div className="text-center py-16 text-zinc-500 text-sm">
            Run Keyword Research first. Briefs turn your researched keywords into execution-ready content:
            outlines, internal-link plans, schema recommendations and refresh plans, each tied to expected
            pipeline outcome.
          </div>
        </Section>
      )}
      {result?.briefs && (
        <div className="space-y-6">
          {result.briefs.map((b, i) => (
            <Fade key={i}>
              <Section>
                <div className="flex items-center gap-2 text-sm font-medium mb-1">
                  <FileText size={15} className="text-[#2563EB]" /> {b.working_title || b.keyword}
                </div>
                <div className="text-xs text-zinc-500 mb-4">Target keyword: {b.keyword} · intent: {b.target_intent}</div>
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Outline</div>
                    <ol className="list-decimal list-inside space-y-1 text-zinc-700">
                      {(b.outline || []).map((s, j) => <li key={j}>{s}</li>)}
                    </ol>
                  </div>
                  <div className="space-y-3">
                    <Info label="Primary keyword" value={b.primary_keyword} />
                    <Info label="Secondary keywords" value={(b.secondary_keywords || []).join(", ")} />
                    <Info label="Schema recommendation" value={b.schema_recommendation} />
                    <Info label="Refresh plan" value={b.refresh_plan} />
                  </div>
                </div>
                <div className="mt-4 pt-3 border-t border-border">
                  <div className="text-xs uppercase tracking-wider text-zinc-500 mb-1">Internal link plan</div>
                  {(b.internal_link_plan || []).map((l, j) => (
                    <div key={j} className="text-sm flex items-center gap-2 text-zinc-700"><LinkSimple size={12} /> {l}</div>
                  ))}
                </div>
                <div className="mt-3 flex items-center gap-2 text-xs text-green-700">
                  <TrendUp size={13} /> {b.expected_outcome}
                </div>
              </Section>
            </Fade>
          ))}
          {result.site_architecture_notes?.length > 0 && (
            <Fade>
              <Section>
                <div className="text-sm uppercase tracking-wider text-zinc-500 mb-3">Site Architecture Notes</div>
                <div className="space-y-1.5">
                  {result.site_architecture_notes.map((n, i) => (
                    <div key={i} className="text-sm flex items-center gap-2 text-zinc-700"><LinkSimple size={13} className="text-[#2563EB]" /> {n}</div>
                  ))}
                </div>
              </Section>
            </Fade>
          )}
        </div>
      )}
      {result && !result.briefs && !loading && (
        <Section>
          <div className="text-center py-10 text-zinc-500 text-sm">
            No briefs yet. Click "Generate Briefs" to turn your researched keywords into content briefs.
          </div>
        </Section>
      )}
      {loading && <Loader label="Writing briefs" />}
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-zinc-500">{label}</div>
      <div className="text-zinc-800">{value || "—"}</div>
    </div>
  );
}
