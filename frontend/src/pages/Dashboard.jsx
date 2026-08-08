import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { PageHeader, StatCard, Loader, Fade } from "@/components/common";
import { useCurrency } from "@/context/CurrencyContext";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar,
} from "recharts";
import { ArrowUpRight, Strategy, PenNib, UsersThree } from "@phosphor-icons/react";

const chartTip = {
  contentStyle: {
    background: "#0A0A0A",
    border: "1px solid #27272A",
    borderRadius: 0,
    fontSize: 12,
    fontFamily: "JetBrains Mono",
  },
  labelStyle: { color: "#A1A1AA" },
};

export default function Dashboard() {
  const [data, setData] = useState(null);
  const { format } = useCurrency();

  useEffect(() => {
    api.get("/analytics/overview").then((r) => setData(r.data)).catch(() => {});
  }, []);

  if (!data) return <div className="p-8"><Loader label="Loading command center" /></div>;
  const k = data.kpis;

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Executive Command Center"
        title="Marketing Overview"
        description="Real-time visibility across every AI agent, campaign, and revenue signal — computed live from your data."
      />

      {/* KPI grid */}
      <Fade>
        <div className="grid grid-cols-2 lg:grid-cols-4 border-t border-l border-border mb-8">
          <StatCard label="Total Leads" value={k.total_leads} sub={`${k.hot_leads} hot / sales-ready`} />
          <StatCard label="Revenue" value={format(k.revenue)} sub="attributed" accent />
          <StatCard label="ROI" value={`${k.roi}%`} sub="return on spend" />
          <StatCard label="CAC" value={format(k.cac)} sub="cost per acquisition" />
          <StatCard label="Ad Spend" value={format(k.total_spend)} sub={`${k.campaigns} campaigns`} />
          <StatCard label="Conversions" value={k.conversions} sub={`${k.ctr}% CTR`} />
          <StatCard label="Content" value={k.content_generated} sub="assets generated" />
          <StatCard label="Strategies" value={k.strategies} sub="AI roadmaps" />
        </div>
      </Fade>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <Fade delay={0.05}>
          <div className="lg:col-span-2 border border-border bg-white">
            <div className="px-5 py-3 border-b border-border text-xs uppercase tracking-[0.15em] text-zinc-500">
              Leads & Revenue Trend
            </div>
            <div className="p-4 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.trend}>
                  <defs>
                    <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#FF3B30" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#FF3B30" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#18181B" vertical={false} />
                  <XAxis dataKey="month" stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip {...chartTip} />
                  <Area type="monotone" dataKey="revenue" stroke="#FF3B30" strokeWidth={2} fill="url(#g1)" />
                  <Area type="monotone" dataKey="leads" stroke="#A1A1AA" strokeWidth={1.5} fill="none" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Fade>

        <Fade delay={0.1}>
          <div className="border border-border bg-white">
            <div className="px-5 py-3 border-b border-border text-xs uppercase tracking-[0.15em] text-zinc-500">
              Conversion Funnel
            </div>
            <div className="p-5 space-y-3">
              {data.funnel.map((f, i) => {
                const max = data.funnel[0].value;
                const pct = Math.max((f.value / max) * 100, 4);
                return (
                  <div key={f.stage}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-zinc-500">{f.stage}</span>
                      <span className="font-mono text-zinc-700">{f.value.toLocaleString()}</span>
                    </div>
                    <div className="h-2 bg-zinc-100">
                      <div
                        className="h-full bg-[#FF3B30] transition-all duration-500"
                        style={{ width: `${pct}%`, opacity: 1 - i * 0.14 }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Fade>
      </div>

      <Fade delay={0.15}>
        <div className="border border-border bg-white mb-8">
          <div className="px-5 py-3 border-b border-border text-xs uppercase tracking-[0.15em] text-zinc-500">
            Channel Performance · ROAS
          </div>
          <div className="p-4 h-64">
            {data.channel_performance.length === 0 ? (
              <div className="h-full flex items-center justify-center text-sm text-zinc-500">
                No campaigns yet — create one in Campaigns to see channel ROAS.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.channel_performance}>
                  <CartesianGrid stroke="#18181B" vertical={false} />
                  <XAxis dataKey="channel" stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip {...chartTip} cursor={{ fill: "#141414" }} />
                  <Bar dataKey="roas" fill="#FF3B30" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </Fade>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          { to: "/strategy", icon: Strategy, title: "Generate Strategy", desc: "Build a full AI marketing roadmap" },
          { to: "/content", icon: PenNib, title: "Create Content", desc: "Blogs, posts, emails & creatives" },
          { to: "/leads", icon: UsersThree, title: "Score Leads", desc: "AI qualification & pipeline" },
        ].map((c, i) => (
          <Fade key={c.to} delay={0.2 + i * 0.05}>
            <Link
              to={c.to}
              data-testid={`quick-${c.to.slice(1)}`}
              className="group block border border-border bg-white p-5 hover:border-[#FF3B30] transition-colors duration-200"
            >
              <div className="flex items-start justify-between">
                <c.icon size={24} className="text-[#FF3B30]" />
                <ArrowUpRight size={18} className="text-zinc-500 group-hover:text-white transition-colors duration-200" />
              </div>
              <div className="font-display text-lg mt-4">{c.title}</div>
              <div className="text-xs text-zinc-500 mt-1">{c.desc}</div>
            </Link>
          </Fade>
        ))}
      </div>
    </div>
  );
}
