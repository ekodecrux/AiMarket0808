import { createContext, useContext, useEffect, useState } from "react";
import api, { API } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = anon, obj = user
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/auth/me");
        setUser(data);
      } catch {
        setUser(false);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setUser(data.user);
    return data;
  };

  const register = async (name, email, password, phone, useGeneratedPassword = false) => {
    const { data } = await api.post("/auth/register", { name, email, password, phone, use_generated_password: useGeneratedPassword });
    setUser(data.user);
    return data;
  };

  const requestPasswordReset = async (email, delivery = "link") => {
    const { data } = await api.post("/auth/password/reset/request", { email, delivery });
    return data;
  };

  const confirmPasswordReset = async (token, password) => {
    const { data } = await api.post("/auth/password/reset/confirm", { token, password });
    return data;
  };

  const changePassword = async (currentPassword, newPassword) => {
    const { data } = await api.post("/auth/password/change", { current_password: currentPassword, new_password: newPassword });
    setUser(false);
    return data;
  };

  const requestOtp = async (identifier) => {
    const { data } = await api.post("/auth/otp/request", { identifier });
    return data;
  };

  const verifyOtp = async (identifier, code) => {
    const { data } = await api.post("/auth/otp/verify", { identifier, code });
    setUser(data.user);
    return data;
  };

  const getProviderReadiness = async () => {
    const { data } = await api.get("/auth/providers");
    return data;
  };

  const startGoogleSignIn = (returnTo) => {
    window.location.assign(`${API}/auth/google/authorize?return_to=${encodeURIComponent(returnTo)}`);
  };

  const exchangeGoogleCode = async (code) => {
    const { data } = await api.post("/auth/google/exchange", { code });
    setUser(data.user);
    return data;
  };

  const requestPhoneOtp = async (phone, intent, name, consent) => {
    const { data } = await api.post("/auth/otp/phone/request", { phone, intent, name, consent });
    return data;
  };

  const verifyPhoneOtp = async (phone, code, intent) => {
    const { data } = await api.post("/auth/otp/phone/verify", { phone, code, intent });
    setUser(data.user);
    return data;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {}
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, requestOtp, verifyOtp, requestPasswordReset, confirmPasswordReset, changePassword, getProviderReadiness, startGoogleSignIn, exchangeGoogleCode, requestPhoneOtp, verifyPhoneOtp }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
