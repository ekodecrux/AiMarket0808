import { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader, StatCard, Loader, Fade, Section } from "@/components/common";
import { useCurrency } from "@/context/CurrencyContext";
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, RadialBarChart, RadialBar, PolarAngleAxis,
} from "recharts";

const tip = {
  contentStyle: { background: "#0A0A0A", border: "1px solid #27272A", borderRadius: 0, fontSize: 12, fontFamily: "JetBrains Mono" },
  labelStyle: { color: "#A1A1AA" },
};

export default function Analytics() {
  const [data, setData] = useState(null);
  const { format } = useCurrency();
  useEffect(() => { api.get("/analytics/overview").then((r) => setData(r.data)).catch(() => {}); }, []);
  if (!data) return <div className="p-8"><Loader label="Crunching your data" /></div>;
  const k = data.kpis;
  const roiData = [{ name: "ROI", value: Math.max(Math.min(k.roi, 100), 0), fill: "#FF3B30" }];

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Analytics Engine"
        title="Performance Insights"
        description="Every metric below is computed live from your real leads, campaigns and content."
      />

      <Fade>
        <div className="grid grid-cols-2 lg:grid-cols-4 border-t border-l border-border mb-8">
          <StatCard label="ROAS Blended" value={`${k.total_spend ? (k.revenue / k.total_spend).toFixed(2) : "0.00"}x`} accent />
          <StatCard label="Revenue" value={format(k.revenue)} />
          <StatCard label="CAC" value={format(k.cac)} />
          <StatCard label="Conversions" value={k.conversions} sub={`${k.ctr}% CTR`} />
        </div>
      </Fade>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Fade delay={0.05}>
          <div className="border border-border bg-[#0A0A0A]">
            <div className="px-5 py-3 border-b border-border text-xs uppercase tracking-[0.15em] text-zinc-400">Lead Acquisition (6mo)</div>
            <div className="p-4 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.trend}>
                  <CartesianGrid stroke="#18181B" vertical={false} />
                  <XAxis dataKey="month" stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip {...tip} />
                  <Line type="monotone" dataKey="leads" stroke="#FF3B30" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="conversions" stroke="#A1A1AA" strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Fade>
        <Fade delay={0.1}>
          <div className="border border-border bg-[#0A0A0A]">
            <div className="px-5 py-3 border-b border-border text-xs uppercase tracking-[0.15em] text-zinc-400">Revenue Trend</div>
            <div className="p-4 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.trend}>
                  <defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#FF3B30" stopOpacity={0.25} /><stop offset="100%" stopColor="#FF3B30" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid stroke="#18181B" vertical={false} />
                  <XAxis dataKey="month" stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip {...tip} />
                  <Area type="monotone" dataKey="revenue" stroke="#FF3B30" strokeWidth={2} fill="url(#ar)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Fade>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Fade delay={0.15}>
          <div className="lg:col-span-2 border border-border bg-[#0A0A0A]">
            <div className="px-5 py-3 border-b border-border text-xs uppercase tracking-[0.15em] text-zinc-400">Channel ROAS</div>
            <div className="p-4 h-64">
              {data.channel_performance.length === 0 ? (
                <div className="h-full flex items-center justify-center text-sm text-zinc-600">Add campaigns to populate channel analytics.</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.channel_performance} layout="vertical">
                    <CartesianGrid stroke="#18181B" horizontal={false} />
                    <XAxis type="number" stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="channel" stroke="#52525B" fontSize={11} tickLine={false} axisLine={false} width={90} />
                    <Tooltip {...tip} cursor={{ fill: "#141414" }} />
                    <Bar dataKey="roas" fill="#FF3B30" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </Fade>
        <Fade delay={0.2}>
          <div className="border border-border bg-[#0A0A0A]">
            <div className="px-5 py-3 border-b border-border text-xs uppercase tracking-[0.15em] text-zinc-400">ROI Gauge</div>
            <div className="p-4 h-64 flex items-center justify-center relative">
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart innerRadius="70%" outerRadius="100%" data={roiData} startAngle={90} endAngle={-270}>
                  <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                  <RadialBar background={{ fill: "#141414" }} dataKey="value" cornerRadius={0} />
                </RadialBarChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <div className="font-mono text-3xl text-[#FF3B30]">{k.roi}%</div>
                <div className="text-xs text-zinc-500 uppercase tracking-wider">Return on Spend</div>
              </div>
            </div>
          </div>
        </Fade>
      </div>
    </div>
  );
}
