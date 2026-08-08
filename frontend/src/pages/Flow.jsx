import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useClient } from "@/context/ClientContext";
import { PageHeader, Loader, Fade } from "@/components/common";
import { CheckCircle, Circle, ArrowRight, Path } from "@phosphor-icons/react";

export default function Flow() {
  const { activeClientId, activeClient } = useClient();
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const q = activeClientId ? `?client_id=${activeClientId}` : "";
    api.get(`/flow/status${q}`).then((r) => setData(r.data)).catch(() => {});
  }, [activeClientId]);

  if (!data) return <div className="p-8"><Loader label="Mapping your flow" /></div>;
  const pct = Math.round((data.completed / data.total) * 100);

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="Autonomous Flow"
        title="Your Marketing Journey"
        description={`${activeClient ? activeClient.name + " · " : ""}Follow the pipeline from business profile to campaign reporting. Each step turns green as the AI agents complete it.`}
      />

      <Fade>
        <div className="border border-border bg-white p-5 mb-8">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs uppercase tracking-[0.15em] text-zinc-500 flex items-center gap-2"><Path size={16} className="text-[#FF3B30]" /> Pipeline Progress</span>
            <span className="font-mono text-sm">{data.completed}/{data.total} · {pct}%</span>
          </div>
          <div className="h-2 bg-zinc-100"><div className="h-full bg-[#FF3B30] transition-all duration-500" style={{ width: `${pct}%` }} /></div>
        </div>
      </Fade>

      <div className="relative">
        <div className="absolute left-[19px] top-2 bottom-2 w-px bg-border lg:hidden" />
        <div className="grid grid-cols-1 gap-3">
          {data.steps.map((s, i) => (
            <Fade key={s.key} delay={i * 0.04}>
              <button
                onClick={() => navigate(s.route)}
                data-testid={`flow-step-${s.key}`}
                className="group w-full flex items-center gap-4 border border-border bg-white p-4 text-left hover:border-[#FF3B30] transition-colors duration-200"
              >
                <div className="shrink-0">
                  {s.done
                    ? <CheckCircle size={28} weight="fill" className="text-[#34C759]" />
                    : <Circle size={28} className="text-zinc-700" />}
                </div>
                <div className="w-8 font-mono text-sm text-zinc-500">{String(i + 1).padStart(2, "0")}</div>
                <div className="flex-1 min-w-0">
                  <div className="font-display text-lg">{s.label}</div>
                  <div className="text-xs text-zinc-500">{s.done ? `${s.count} ready` : "Not started — click to begin"}</div>
                </div>
                <ArrowRight size={18} className="text-zinc-500 group-hover:text-[#FF3B30] transition-colors duration-200" />
              </button>
            </Fade>
          ))}
        </div>
      </div>
    </div>
  );
}
