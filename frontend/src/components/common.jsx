import { motion } from "framer-motion";
import { CircleNotch } from "@phosphor-icons/react";

export const PageHeader = ({ overline, title, description, action }) => (
  <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
    <div>
      {overline && (
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF3B30] mb-2">
          {overline}
        </div>
      )}
      <h1 className="font-display text-3xl sm:text-4xl font-light tracking-tight">{title}</h1>
      {description && <p className="text-sm text-zinc-500 mt-2 max-w-2xl">{description}</p>}
    </div>
    {action}
  </div>
);

export const SimBadge = ({ label = "Simulated Data" }) => (
  <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-mono px-2 py-1 border border-[#FFCC00]/40 text-[#FFCC00] bg-[#FFCC00]/5">
    <span className="w-1.5 h-1.5 bg-[#FFCC00]" />
    {label}
  </span>
);

export const StatCard = ({ label, value, sub, accent }) => (
  <div className="p-5 border-r border-b border-border" data-testid={`stat-${label?.toLowerCase().replace(/\s+/g, "-")}`}>
    <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-3">{label}</div>
    <div className={`font-mono text-3xl tracking-tighter ${accent ? "text-[#FF3B30]" : "text-white"}`}>
      {value}
    </div>
    {sub && <div className="text-xs text-zinc-600 mt-2">{sub}</div>}
  </div>
);

export const Loader = ({ label = "AI is working" }) => (
  <div className="flex items-center gap-3 text-zinc-400 text-sm py-8">
    <CircleNotch size={18} className="animate-spin text-[#FF3B30]" />
    <span className="font-mono tracking-tight">{label}...</span>
  </div>
);

export const Fade = ({ children, delay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.35, delay, ease: "easeOut" }}
  >
    {children}
  </motion.div>
);

export const Section = ({ title, children, className = "" }) => (
  <div className={`border border-border bg-[#0A0A0A] ${className}`}>
    {title && (
      <div className="px-5 py-3 border-b border-border text-xs uppercase tracking-[0.15em] text-zinc-400">
        {title}
      </div>
    )}
    <div className="p-5">{children}</div>
  </div>
);
