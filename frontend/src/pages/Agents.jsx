import { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader, Loader, Fade } from "@/components/common";
import { Robot } from "@phosphor-icons/react";

export default function Agents() {
  const [agents, setAgents] = useState(null);
  useEffect(() => { api.get("/agents").then((r) => setAgents(r.data)).catch(() => setAgents([])); }, []);

  return (
    <div className="p-5 lg:p-8">
      <PageHeader
        overline="AI Agent Marketplace"
        title="Autonomous Agent Fleet"
        description="Dedicated AI agents that plan, execute and optimize each marketing function continuously."
      />
      {!agents ? <Loader label="Loading agents" /> : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border border border-border">
          {agents.map((a, i) => (
            <Fade key={a.name} delay={i * 0.03}>
              <div className="bg-white p-6 h-full hover:bg-zinc-50 transition-colors duration-200" data-testid={`agent-${a.name.replace(/\s+/g, "-").toLowerCase()}`}>
                <div className="flex items-start justify-between">
                  <div className="w-10 h-10 border border-zinc-200 flex items-center justify-center">
                    <Robot size={20} className="text-[#2563EB]" />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className={`w-1.5 h-1.5 ${a.status === "Active" ? "bg-[#34C759] animate-pulse-dot" : "bg-zinc-600"}`} />
                    <span className="text-[10px] uppercase tracking-wider text-zinc-500">{a.status}</span>
                  </div>
                </div>
                <div className="font-display text-lg mt-4">{a.name}</div>
                <div className="text-sm text-zinc-500 mt-1">{a.role}</div>
              </div>
            </Fade>
          ))}
        </div>
      )}
    </div>
  );
}
