import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Lightning, ArrowRight, DeviceMobile } from "@phosphor-icons/react";

export default function Login() {
  const { login, register, requestOtp, verifyOtp } = useAuth();
  const navigate = useNavigate();
  const [method, setMethod] = useState("password"); // password | otp
  const [mode, setMode] = useState("login"); // login | register (password only)
  const [form, setForm] = useState({ name: "", email: "", password: "", phone: "" });
  const [otp, setOtp] = useState({ identifier: "", code: "", sent: false, channel: "", sentTo: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submitPassword = async (e) => {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      if (mode === "login") await login(form.email, form.password);
      else await register(form.name, form.email, form.password, form.phone);
      navigate("/");
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setBusy(false); }
  };

  const sendOtp = async (e) => {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      const data = await requestOtp(otp.identifier);
      setOtp({ ...otp, sent: true, channel: data.channel, sentTo: data.sent_to });
      toast.success(data.channel === "sms" ? `Code sent via SMS to ${data.sent_to}` : `Code sent to ${data.sent_to}`);
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setBusy(false); }
  };

  const confirmOtp = async (e) => {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      await verifyOtp(otp.identifier, otp.code);
      navigate("/");
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setBusy(false); }
  };

  return (
    <div className="noise-bg min-h-screen bg-background flex">
      <div className="hidden lg:flex w-1/2 flex-col justify-between p-12 border-r border-border relative z-10">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-[#FF3B30] flex items-center justify-center"><Lightning weight="fill" className="text-white" size={18} /></div>
          <span className="font-display font-bold tracking-tight">NEXUS</span>
        </div>
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF3B30] mb-4">Autonomous Marketing OS</div>
          <h1 className="font-display text-5xl font-light leading-[1.05] tracking-tight max-w-lg">The world's first fully autonomous AI marketing engine.</h1>
          <p className="text-zinc-500 mt-6 max-w-md text-sm leading-relaxed">From business profile to campaign reporting — planned, created, executed and optimized by a fleet of AI agents, with you in the loop.</p>
        </div>
        <div className="grid grid-cols-3 gap-px border border-border bg-border">
          {[["90-95%", "Automated Ops"], ["12", "AI Agents"], ["∞", "Scale"]].map(([v, l]) => (
            <div key={l} className="bg-white p-4"><div className="font-mono text-2xl">{v}</div><div className="text-[10px] uppercase tracking-wider text-zinc-500 mt-1">{l}</div></div>
          ))}
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-6 relative z-10">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-[#FF3B30] flex items-center justify-center"><Lightning weight="fill" className="text-white" size={18} /></div>
            <span className="font-display font-bold tracking-tight">NEXUS</span>
          </div>

          {/* Method switch */}
          <div className="flex border border-border mb-8">
            {[["password", "Password"], ["otp", "OTP Login"]].map(([id, label]) => (
              <button key={id} onClick={() => { setMethod(id); setError(""); }} data-testid={`method-${id}`}
                className={`flex-1 py-2 text-xs uppercase tracking-wider transition-colors duration-200 ${method === id ? "bg-[#FF3B30] text-white" : "text-zinc-500 hover:text-white"}`}>
                {label}
              </button>
            ))}
          </div>

          {method === "password" ? (
            <>
              <h2 className="font-display text-2xl font-medium tracking-tight mb-1">{mode === "login" ? "Sign in" : "Create account"}</h2>
              <p className="text-sm text-zinc-500 mb-8">{mode === "login" ? "Access your marketing command center." : "Deploy your AI marketing fleet."}</p>
              <form onSubmit={submitPassword} className="space-y-4">
                {mode === "register" && <Field label="Full Name" type="text" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testid="name-input" />}
                <Field label="Email" type="email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} testid="email-input" />
                {mode === "register" && <Field label="Phone (for OTP login)" type="tel" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} testid="phone-input" required={false} />}
                <Field label="Password" type="password" value={form.password} onChange={(v) => setForm({ ...form, password: v })} testid="password-input" />
                {error && <div className="text-sm text-[#FF3B30] border border-[#FF3B30]/30 bg-[#FF3B30]/5 px-3 py-2" data-testid="auth-error">{error}</div>}
                <button type="submit" disabled={busy} data-testid="submit-btn" className="w-full flex items-center justify-center gap-2 bg-[#FF3B30] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">
                  {busy ? "Please wait" : mode === "login" ? "Sign In" : "Create Account"} <ArrowRight size={16} />
                </button>
              </form>
              <div className="mt-6 text-sm text-zinc-500">
                {mode === "login" ? "No account? " : "Already registered? "}
                <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }} className="text-white underline underline-offset-4 hover:text-[#FF3B30] transition-colors duration-200" data-testid="toggle-mode-btn">
                  {mode === "login" ? "Create one" : "Sign in"}
                </button>
              </div>
              <div className="mt-8 pt-6 border-t border-border text-xs text-zinc-500 font-mono">Demo · admin@marketing.ai / admin123</div>
            </>
          ) : (
            <>
              <h2 className="font-display text-2xl font-medium tracking-tight mb-1 flex items-center gap-2"><DeviceMobile size={22} /> OTP Login</h2>
              <p className="text-sm text-zinc-500 mb-8">Enter your email or registered phone. We'll send a one-time code.</p>
              {!otp.sent ? (
                <form onSubmit={sendOtp} className="space-y-4">
                  <Field label="Email or Phone" type="text" value={otp.identifier} onChange={(v) => setOtp({ ...otp, identifier: v })} testid="otp-identifier" />
                  {error && <div className="text-sm text-[#FF3B30] border border-[#FF3B30]/30 bg-[#FF3B30]/5 px-3 py-2" data-testid="auth-error">{error}</div>}
                  <button type="submit" disabled={busy} data-testid="request-otp-btn" className="w-full flex items-center justify-center gap-2 bg-[#FF3B30] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">
                    {busy ? "Sending" : "Send OTP"} <ArrowRight size={16} />
                  </button>
                </form>
              ) : (
                <form onSubmit={confirmOtp} className="space-y-4">
                  <div className="text-sm border border-[#34C759]/40 bg-[#34C759]/5 text-[#34C759] px-3 py-2" data-testid="otp-sent">
                    A 6-digit code was sent {otp.channel === "sms" ? "via SMS" : "to your email"}: <span className="font-mono">{otp.sentTo}</span>
                  </div>
                  <Field label="6-Digit Code" type="text" value={otp.code} onChange={(v) => setOtp({ ...otp, code: v })} testid="otp-code" />
                  {error && <div className="text-sm text-[#FF3B30] border border-[#FF3B30]/30 bg-[#FF3B30]/5 px-3 py-2" data-testid="auth-error">{error}</div>}
                  <button type="submit" disabled={busy} data-testid="verify-otp-btn" className="w-full flex items-center justify-center gap-2 bg-[#FF3B30] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#D63026] disabled:opacity-50 transition-colors duration-200">
                    {busy ? "Verifying" : "Verify & Sign In"} <ArrowRight size={16} />
                  </button>
                  <button type="button" onClick={() => setOtp({ ...otp, sent: false, code: "" })} className="w-full text-xs text-zinc-500 hover:text-white transition-colors duration-200">Use a different identifier</button>
                </form>
              )}
              <div className="mt-8 pt-6 border-t border-border text-xs text-zinc-500 font-mono">Demo · admin@marketing.ai</div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const Field = ({ label, value, onChange, testid, type, required = true }) => (
  <div>
    <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{label}</label>
    <input type={type} required={required} value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid}
      className="w-full bg-transparent border border-zinc-200 px-3 py-2.5 text-sm text-white focus:outline-none focus:border-[#FF3B30] transition-colors duration-200" />
  </div>
);
