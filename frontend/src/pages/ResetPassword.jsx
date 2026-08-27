import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, Key } from "@phosphor-icons/react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";

export default function ResetPassword() {
  const { confirmPasswordReset } = useAuth(); const [params] = useSearchParams(); const navigate = useNavigate();
  const [token, setToken] = useState(params.get("token") || ""); const [password, setPassword] = useState(""); const [confirm, setConfirm] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (event) => { event.preventDefault(); if (!token || !password) return setError("Enter the reset token and your new password."); if (password !== confirm) return setError("The password confirmation does not match."); setBusy(true); setError(""); try { await confirmPasswordReset(token, password); toast.success("Password reset. Please sign in."); navigate("/login"); } catch (err) { setError(formatApiError(err.response?.data?.detail) || err.message); } finally { setBusy(false); } };
  return <div className="noise-bg min-h-screen bg-background flex items-center justify-center p-6"><div className="w-full max-w-sm border border-border bg-white p-6"><div className="w-10 h-10 bg-[#2563EB] text-white flex items-center justify-center mb-5"><Key size={20} /></div><div className="text-xs font-bold uppercase tracking-[0.2em] text-[#2563EB] mb-2">ACCOUNT RECOVERY</div><h1 className="font-display text-2xl font-medium tracking-tight">Choose a new password</h1><p className="text-sm text-zinc-500 mt-2 mb-6">Reset links are single-use and expire after 30 minutes.</p><form onSubmit={submit} className="space-y-4"><Field label="Reset token" value={token} onChange={setToken} /><Field label="New password" value={password} onChange={setPassword} type="password" /><Field label="Confirm new password" value={confirm} onChange={setConfirm} type="password" />{error && <div className="text-sm text-[#2563EB] border border-[#2563EB]/30 bg-[#2563EB]/5 px-3 py-2">{error}</div>}<button type="submit" disabled={busy} className="w-full flex items-center justify-center gap-2 bg-[#2563EB] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] disabled:opacity-50">{busy ? "Updating" : "Set new password"}<ArrowRight size={16} /></button></form><button type="button" onClick={() => navigate("/login")} className="mt-5 text-xs text-zinc-500 hover:text-zinc-950">Back to sign in</button></div></div>;
}

const Field = ({ label, value, onChange, type = "text" }) => <div><label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{label}</label><input type={type} required value={value} onChange={(event) => onChange(event.target.value)} className="w-full bg-transparent border border-zinc-200 px-3 py-2.5 text-sm text-zinc-950 focus:outline-none focus:border-[#2563EB]" /></div>;
