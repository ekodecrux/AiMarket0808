import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Key, ArrowRight } from "@phosphor-icons/react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";

export default function AccountSecurity() {
  const { user, changePassword } = useAuth(); const navigate = useNavigate(); const [current, setCurrent] = useState(""); const [password, setPassword] = useState(""); const [confirm, setConfirm] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (event) => { event.preventDefault(); if (password !== confirm) return setError("The password confirmation does not match."); setBusy(true); setError(""); try { await changePassword(current, password); toast.success("Password changed. Please sign in again."); navigate("/login"); } catch (err) { setError(formatApiError(err.response?.data?.detail) || err.message); } finally { setBusy(false); } };
  return <div className="max-w-xl mx-auto p-5 lg:p-8"><div className="border border-border bg-white p-6"><div className="flex items-start gap-4"><div className="w-10 h-10 bg-[#2563EB] text-white flex items-center justify-center shrink-0"><Key size={20} /></div><div><div className="text-xs font-bold uppercase tracking-[0.2em] text-[#2563EB]">ACCOUNT SECURITY</div><h1 className="font-display text-2xl font-medium tracking-tight mt-1">Change password</h1><p className="text-sm text-zinc-500 mt-2">{user?.must_change_password ? "Your temporary password must be replaced before continuing." : "Use a unique password of at least 12 characters with letters and numbers."}</p></div></div><form onSubmit={submit} className="space-y-4 mt-7"><Field label="Current password" value={current} onChange={setCurrent} /><Field label="New password" value={password} onChange={setPassword} /><Field label="Confirm new password" value={confirm} onChange={setConfirm} />{error && <div className="text-sm text-[#2563EB] border border-[#2563EB]/30 bg-[#2563EB]/5 px-3 py-2">{error}</div>}<button type="submit" disabled={busy} className="w-full flex items-center justify-center gap-2 bg-[#2563EB] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] disabled:opacity-50">{busy ? "Updating" : "Change password"}<ArrowRight size={16} /></button></form></div></div>;
}

const Field = ({ label, value, onChange }) => <div><label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{label}</label><input type="password" required value={value} onChange={(event) => onChange(event.target.value)} className="w-full bg-transparent border border-zinc-200 px-3 py-2.5 text-sm text-zinc-950 focus:outline-none focus:border-[#2563EB]" /></div>;
