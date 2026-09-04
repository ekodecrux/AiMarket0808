import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { ArrowRight, DeviceMobile, EnvelopeSimple, Lightning } from "@phosphor-icons/react";

const Field = ({ label, value, onChange, type = "text", required = true, inputMode }) => (
  <div>
    <label className="block text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">{label}</label>
    <input type={type} inputMode={inputMode} required={required} value={value} onChange={(event) => onChange(event.target.value)} className="w-full bg-transparent border border-zinc-200 px-3 py-2.5 text-sm text-zinc-950 focus:outline-none focus:border-[#2563EB]" />
  </div>
);
const Notice = ({ children, tone = "info" }) => <div className={`text-sm border px-3 py-2 ${tone === "error" ? "text-red-700 border-red-300 bg-red-50" : "text-[#2563EB] border-[#2563EB]/30 bg-[#2563EB]/5"}`}>{children}</div>;
const Submit = ({ busy, label }) => <button type="submit" disabled={busy} className="w-full flex items-center justify-center gap-2 bg-[#2563EB] text-white py-3 text-sm uppercase tracking-wider hover:bg-[#1D4ED8] disabled:opacity-50">{busy ? "Please wait" : label}<ArrowRight size={16} /></button>;

export default function Login() {
  const { login, register, requestOtp, verifyOtp, requestPasswordReset, getProviderReadiness, startGoogleSignIn, exchangeGoogleCode, requestPhoneOtp, verifyPhoneOtp } = useAuth();
  const navigate = useNavigate();
  const [method, setMethod] = useState("password");
  const [mode, setMode] = useState("login");
  const [generated, setGenerated] = useState(true);
  const [form, setForm] = useState({ name: "", email: "", password: "", phone: "" });
  const [otp, setOtp] = useState({ identifier: "", code: "", sent: false, channel: "" });
  const [phoneOtp, setPhoneOtp] = useState({ phone: "", name: "", code: "", sent: false, intent: "login", consent: false });
  const [providers, setProviders] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getProviderReadiness().then(setProviders).catch(() => setProviders({ google: { available: false }, phone_otp: { available: false } }));
  }, []);

  useEffect(() => {
    const googleCode = new URLSearchParams(window.location.search).get("google_code");
    if (!googleCode) return;
    setBusy(true);
    exchangeGoogleCode(googleCode).then(() => {
      window.history.replaceState({}, "", "/login");
      navigate("/", { replace: true });
    }).catch((err) => setError(formatApiError(err.response?.data?.detail) || err.message)).finally(() => setBusy(false));
  }, []);

  const chooseMode = (next) => { setMode(next); setGenerated(next !== "login"); setError(""); };
  const chooseMethod = (next) => { setMethod(next); setError(""); };
  const submitPassword = async (event) => {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      if (mode === "login") { await login(form.email, form.password); navigate("/"); }
      else if (mode === "register") {
        const result = await register(form.name, form.email, form.password, form.phone, generated);
        if (result.temporary_password_emailed) toast.success("A temporary password was sent securely. Change it now.");
        navigate(generated ? "/account-security" : "/");
      } else {
        await requestPasswordReset(form.email, generated ? "temporary" : "link");
        toast.success("If an account exists, password instructions have been sent."); chooseMode("login");
      }
    } catch (err) { setError(formatApiError(err.response?.data?.detail) || err.message); } finally { setBusy(false); }
  };
  const sendEmailOtp = async (event) => {
    event.preventDefault(); setError(""); setBusy(true);
    try { const data = await requestOtp(otp.identifier); setOtp({ ...otp, sent: true, channel: data.channel }); toast.success("Code sent to your email."); }
    catch (err) { setError(formatApiError(err.response?.data?.detail) || err.message); } finally { setBusy(false); }
  };
  const confirmEmailOtp = async (event) => {
    event.preventDefault(); setError(""); setBusy(true);
    try { await verifyOtp(otp.identifier, otp.code); navigate("/"); }
    catch (err) { setError(formatApiError(err.response?.data?.detail) || err.message); } finally { setBusy(false); }
  };
  const sendPhoneOtp = async (event) => {
    event.preventDefault(); setError(""); setBusy(true);
    try { const data = await requestPhoneOtp(phoneOtp.phone, phoneOtp.intent, phoneOtp.name, phoneOtp.consent); setPhoneOtp({ ...phoneOtp, sent: true }); toast.success(`Code sent to ${data.sent_to}.`); }
    catch (err) { setError(formatApiError(err.response?.data?.detail) || err.message); } finally { setBusy(false); }
  };
  const confirmPhoneOtp = async (event) => {
    event.preventDefault(); setError(""); setBusy(true);
    try { await verifyPhoneOtp(phoneOtp.phone, phoneOtp.code, phoneOtp.intent); navigate("/"); }
    catch (err) { setError(formatApiError(err.response?.data?.detail) || err.message); } finally { setBusy(false); }
  };
  const title = mode === "login" ? "Sign in" : mode === "register" ? "Create account" : "Reset password";
  const googleReady = Boolean(providers?.google?.available);
  const phoneReady = Boolean(providers?.phone_otp?.available);

  return <div className="noise-bg min-h-screen bg-background flex">
    <aside className="hidden lg:flex w-1/2 flex-col justify-between p-12 border-r border-border"><div className="flex items-center gap-2"><div className="w-8 h-8 bg-[#2563EB] flex items-center justify-center"><Lightning weight="fill" className="text-white" size={18} /></div><span className="font-display font-bold tracking-tight">NEXUS</span></div><div><div className="text-xs font-bold uppercase tracking-[0.2em] text-[#2563EB] mb-4">Autonomous Marketing OS</div><h1 className="font-display text-5xl font-light leading-[1.05] tracking-tight max-w-lg">Marketing intelligence, with you in control.</h1><p className="text-zinc-500 mt-6 max-w-md text-sm leading-relaxed">A knowledge-first, policy-governed marketing workspace for each tenant.</p></div><p className="text-xs uppercase tracking-[0.15em] text-zinc-500">Secure access · Human-approved execution</p></aside>
    <main className="flex-1 flex items-center justify-center p-6"><div className="w-full max-w-sm"><div className="lg:hidden flex items-center gap-2 mb-8"><div className="w-8 h-8 bg-[#2563EB] flex items-center justify-center"><Lightning weight="fill" className="text-white" size={18} /></div><span className="font-display font-bold tracking-tight">NEXUS</span></div>
      <div className="grid grid-cols-2 border border-border mb-8">{[["password", "Password"], ["google", "Google"], ["phone", "Phone OTP"], ["email-otp", "Email OTP"]].map(([id, label]) => <button key={id} onClick={() => chooseMethod(id)} className={`py-2 text-xs uppercase tracking-wider border-b border-r border-border last:border-r-0 ${method === id ? "bg-[#2563EB] text-white" : "text-zinc-500 hover:text-zinc-950"}`}>{label}</button>)}</div>
      {method === "password" && <><h2 className="font-display text-2xl font-medium tracking-tight mb-1">{title}</h2><p className="text-sm text-zinc-500 mb-7">{mode === "login" ? "Access your tenant-scoped marketing workspace." : mode === "register" ? "Choose an email-delivered temporary password or set your own." : "Send a single-use reset link or a temporary password to your email."}</p><form onSubmit={submitPassword} className="space-y-4">{mode === "register" && <><Field label="Full name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} /><Field label="Phone (optional)" type="tel" value={form.phone} required={false} onChange={(value) => setForm({ ...form, phone: value })} /></>}<Field label="Work email" type="email" value={form.email} onChange={(value) => setForm({ ...form, email: value })} />{mode !== "login" && <button type="button" onClick={() => setGenerated(!generated)} className="w-full flex justify-between text-left border border-zinc-200 p-3 text-xs"><span className="font-medium text-zinc-900">{generated ? "Email a generated temporary password" : "Set my own password now"}</span><span className="text-[#2563EB]">Change</span></button>}{(mode === "login" || (mode === "register" && !generated)) && <Field label="Password" type="password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} />}{error && <Notice tone="error">{error}</Notice>}<Submit busy={busy} label={mode === "login" ? "Sign in" : mode === "register" ? "Create account" : "Send instructions"} /></form><div className="mt-6 flex flex-wrap gap-x-4 gap-y-2 text-sm">{mode !== "login" && <button onClick={() => chooseMode("login")} className="text-zinc-500 hover:text-zinc-950">Sign in</button>}{mode !== "register" && <button onClick={() => chooseMode("register")} className="text-zinc-500 hover:text-zinc-950">Create account</button>}{mode !== "reset" && <button onClick={() => chooseMode("reset")} className="text-zinc-500 hover:text-zinc-950">Forgot password?</button>}</div></>}
      {method === "google" && <><h2 className="font-display text-2xl font-medium tracking-tight mb-1">Continue with Google</h2><p className="text-sm text-zinc-500 mb-7">Google verifies your identity. NEXUS then creates the same tenant-scoped secure session used by password sign-in.</p>{!providers ? <Notice>Checking Google sign-in availability…</Notice> : !googleReady ? <Notice>Google sign-in will appear here after the administrator completes the Google OAuth setup.</Notice> : <button onClick={() => startGoogleSignIn(`${window.location.origin}/login`)} disabled={busy} className="w-full border border-zinc-300 py-3 text-sm font-medium hover:border-[#2563EB] disabled:opacity-50"><span className="mr-2 text-[#2563EB] font-bold">G</span>{busy ? "Please wait" : "Continue with Google"}</button>}{error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}</>}
      {method === "phone" && <><h2 className="font-display text-2xl font-medium tracking-tight mb-1 flex items-center gap-2"><DeviceMobile size={22} /> Phone OTP</h2><p className="text-sm text-zinc-500 mb-7">Use your verified mobile number. Your secure session stays active on this device.</p>{!providers ? <Notice>Checking SMS availability…</Notice> : !phoneReady ? <Notice>Phone OTP will appear here after the administrator completes the SMS provider setup.</Notice> : !phoneOtp.sent ? <form onSubmit={sendPhoneOtp} className="space-y-4"><div className="grid grid-cols-2 border border-zinc-200"><button type="button" onClick={() => setPhoneOtp({ ...phoneOtp, intent: "login" })} className={`py-2 text-xs uppercase tracking-wider ${phoneOtp.intent === "login" ? "bg-[#2563EB] text-white" : "text-zinc-500"}`}>Sign in</button><button type="button" onClick={() => setPhoneOtp({ ...phoneOtp, intent: "signup" })} className={`py-2 text-xs uppercase tracking-wider ${phoneOtp.intent === "signup" ? "bg-[#2563EB] text-white" : "text-zinc-500"}`}>Create account</button></div>{phoneOtp.intent === "signup" && <Field label="Full name" value={phoneOtp.name} onChange={(value) => setPhoneOtp({ ...phoneOtp, name: value })} />}<Field label="Mobile number" type="tel" inputMode="tel" value={phoneOtp.phone} onChange={(value) => setPhoneOtp({ ...phoneOtp, phone: value })} /><p className="text-xs text-zinc-500">Use international format, for example +14155552671.</p><label className="flex gap-2 text-xs text-zinc-600 items-start"><input type="checkbox" checked={phoneOtp.consent} onChange={(event) => setPhoneOtp({ ...phoneOtp, consent: event.target.checked })} className="mt-0.5" />I agree to receive a one-time verification SMS for this sign-in attempt.</label>{error && <Notice tone="error">{error}</Notice>}<Submit busy={busy} label="Send code" /></form> : <form onSubmit={confirmPhoneOtp} className="space-y-4"><Notice>A code was sent by SMS. It expires soon.</Notice><Field label="Verification code" inputMode="numeric" value={phoneOtp.code} onChange={(value) => setPhoneOtp({ ...phoneOtp, code: value })} />{error && <Notice tone="error">{error}</Notice>}<Submit busy={busy} label="Verify and sign in" /><button type="button" onClick={() => setPhoneOtp({ ...phoneOtp, code: "", sent: false })} className="w-full text-xs text-zinc-500 hover:text-zinc-950">Use a different number</button></form>}</>}
      {method === "email-otp" && <><h2 className="font-display text-2xl font-medium tracking-tight mb-1 flex items-center gap-2"><EnvelopeSimple size={22} /> Email OTP</h2><p className="text-sm text-zinc-500 mb-8">Enter your registered email to receive a one-time sign-in code.</p>{!otp.sent ? <form onSubmit={sendEmailOtp} className="space-y-4"><Field label="Work email" type="email" value={otp.identifier} onChange={(value) => setOtp({ ...otp, identifier: value })} />{error && <Notice tone="error">{error}</Notice>}<Submit busy={busy} label="Send code" /></form> : <form onSubmit={confirmEmailOtp} className="space-y-4"><Notice>A 6-digit code was sent to your email.</Notice><Field label="6-digit code" inputMode="numeric" value={otp.code} onChange={(value) => setOtp({ ...otp, code: value })} />{error && <Notice tone="error">{error}</Notice>}<Submit busy={busy} label="Verify and sign in" /><button type="button" onClick={() => setOtp({ ...otp, sent: false, code: "", channel: "" })} className="w-full text-xs text-zinc-500 hover:text-zinc-950">Use a different email</button></form>}</>}
    </div></main>
  </div>;
}
