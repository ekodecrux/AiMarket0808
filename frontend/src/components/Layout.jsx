import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useClient } from "@/context/ClientContext";
import {
  ChartLineUp, Strategy, PenNib, ShareNetwork, Megaphone,
  UsersThree, ChatCircleText, ChartBar, Robot, SignOut, List, X, Lightning, Crosshair,
  Buildings, PlugsConnected, CaretDown, ChartPieSlice, Path, SealCheck,
  Target, Users, Lightbulb,
} from "@phosphor-icons/react";

const NAV = [
  { section: "Overview", items: [
    { to: "/flow", label: "Autonomous Flow", icon: Path, id: "flow" },
    { to: "/", label: "Command Center", icon: ChartLineUp, id: "dashboard" },
    { to: "/approvals", label: "Approvals", icon: SealCheck, id: "approvals" },
    { to: "/analytics", label: "Analytics Engine", icon: ChartBar, id: "analytics" },
  ]},
  { section: "Create & Publish", items: [
    { to: "/strategy", label: "Strategy Generator", icon: Strategy, id: "strategy" },
    { to: "/content", label: "Content Studio", icon: PenNib, id: "content" },
    { to: "/social", label: "Social Manager", icon: ShareNetwork, id: "social" },
    { to: "/campaigns", label: "Campaigns", icon: Megaphone, id: "campaigns" },
    { to: "/budget", label: "Budget Planner", icon: ChartPieSlice, id: "budget" },
  ]},
  { section: "Grow & Convert", items: [
    { to: "/leads", label: "Lead Management", icon: UsersThree, id: "leads" },
    { to: "/sales", label: "Sales Assistant", icon: ChatCircleText, id: "sales" },
    { to: "/radar", label: "Competitor Radar", icon: Crosshair, id: "radar" },
  ]},
  { section: "Engine Intelligence", items: [
    { to: "/missions", label: "Mission Planner", icon: Target, id: "missions" },
    { to: "/brain", label: "Business Brain", icon: Strategy, id: "brain" },
    { to: "/intel", label: "Revenue Intelligence", icon: Users, id: "intel" },
    { to: "/learning", label: "Learning & Governance", icon: Lightbulb, id: "learning" },
  ]},
  { section: "Workspace", items: [
    { to: "/clients", label: "Clients", icon: Buildings, id: "clients" },
    { to: "/settings", label: "Settings & Integrations", icon: PlugsConnected, id: "settings" },
    { to: "/agents", label: "AI Agents", icon: Robot, id: "agents" },
  ]},
];

const NAV_CLIENT = [{ section: "My Marketing", items: [
  { to: "/", label: "Dashboard", icon: ChartLineUp, id: "dashboard" },
  { to: "/analytics", label: "Analytics", icon: ChartBar, id: "analytics" },
  { to: "/campaigns", label: "Campaigns", icon: Megaphone, id: "campaigns" },
  { to: "/leads", label: "Leads", icon: UsersThree, id: "leads" },
]}];

export const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const { clients, activeClientId, setActive } = useClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const isClient = user?.role === "client";
  const navGroups = isClient ? NAV_CLIENT : NAV;

  const handleLogout = async () => { await logout(); navigate("/login"); };

  return (
    <div className="noise-bg min-h-screen bg-background flex">
      <aside className={`fixed lg:static z-40 h-screen w-72 bg-white border-r border-border flex flex-col transition-transform duration-200 ${open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`} data-testid="sidebar">
        <div className="h-16 flex items-center gap-3 px-6 border-b border-border shrink-0">
          <div className="w-8 h-8 bg-[#2563EB] rounded-sm flex items-center justify-center shadow-sm"><Lightning weight="fill" className="text-white" size={17} /></div>
          <div><div className="font-display font-bold text-sm tracking-tight leading-none text-zinc-950">NEXUS</div><div className="text-[9px] uppercase tracking-[0.2em] text-zinc-500 mt-1">{isClient ? "Client Portal" : "AI Marketing OS"}</div></div>
        </div>

        <nav className="flex-1 py-4 overflow-y-auto">
          {navGroups.map((group) => <div key={group.section} className="mb-5">
            <div className="px-6 py-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-500">{group.section}</div>
            {group.items.map((item) => { const Icon = item.icon; return <NavLink key={item.id} to={item.to} end={item.to === "/"} onClick={() => setOpen(false)} data-testid={`sidebar-nav-${item.id}`} className={({ isActive }) => `group mx-3 flex items-center gap-3 rounded-md px-3 py-2.5 text-sm border-l-2 transition-all duration-200 ${isActive ? "border-[#2563EB] bg-[#EFF6FF] text-zinc-950 font-medium" : "border-transparent text-zinc-500 hover:text-zinc-950 hover:bg-zinc-50"}`}><Icon size={17} weight="regular" /><span>{item.label}</span></NavLink>; })}
          </div>)}
        </nav>

        <div className="border-t border-border p-4 shrink-0 bg-zinc-50/70">
          <div className="flex items-center gap-3 mb-3"><div className="w-8 h-8 rounded-full bg-zinc-900 text-white flex items-center justify-center text-xs font-mono uppercase">{(user?.name || user?.email || "U").slice(0, 2)}</div><div className="min-w-0"><div className="text-sm truncate text-zinc-900">{user?.name || "User"}</div><div className="text-[11px] text-zinc-500 truncate">{user?.email}</div></div></div>
          <button onClick={handleLogout} data-testid="logout-btn" className="w-full flex items-center justify-center gap-2 rounded-md px-3 py-2 text-xs uppercase tracking-wider border border-zinc-200 text-zinc-500 hover:border-zinc-400 hover:text-zinc-950 transition-colors duration-200"><SignOut size={14} /> Sign Out</button>
        </div>
      </aside>

      {open && <div className="fixed inset-0 z-30 bg-zinc-950/20 lg:hidden" onClick={() => setOpen(false)} />}

      <div className="flex-1 min-w-0 flex flex-col relative z-10">
        <header className="h-16 border-b border-border flex items-center justify-between px-5 lg:px-8 bg-white gap-4 sticky top-0 z-20">
          <button className="lg:hidden text-zinc-500" onClick={() => setOpen(!open)} data-testid="mobile-menu-toggle">{open ? <X size={22} /> : <List size={22} />}</button>
          <div className="hidden lg:flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-[#34C759] animate-pulse-dot" /><span className="text-xs uppercase tracking-[0.18em] text-zinc-500">Autonomous Engine · Online</span></div>
          <div className="flex items-center gap-3 ml-auto">
            {isClient ? <div className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5"><Buildings size={14} className="text-[#2563EB]" /><span className="text-sm text-zinc-700" data-testid="client-portal-badge">Your Workspace</span></div> : <div className="relative flex items-center gap-2 rounded-md border border-border px-3 py-1.5"><Buildings size={14} className="text-zinc-500" /><select value={activeClientId} onChange={(e) => setActive(e.target.value)} data-testid="active-client-select" className="bg-transparent text-sm text-zinc-700 focus:outline-none pr-5 appearance-none cursor-pointer"><option value="">Platform (All Clients)</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select><CaretDown size={12} className="text-zinc-500 absolute right-2 pointer-events-none" /></div>}
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
};
