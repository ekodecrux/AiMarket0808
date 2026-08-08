import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useClient } from "@/context/ClientContext";

const CurrencyContext = createContext(null);

export function CurrencyProvider({ children }) {
  const { user } = useAuth();
  const { activeClientId } = useClient();
  const [currency, setCurrency] = useState("USD");
  const [country, setCountry] = useState("United States");

  const refresh = useCallback(() => {
    if (!user) return;
    const q = activeClientId ? `?client_id=${activeClientId}` : "";
    api.get(`/profile${q}`).then((r) => {
      setCurrency(r.data.currency || "USD");
      setCountry(r.data.country || "United States");
    }).catch(() => {});
  }, [user, activeClientId]);

  useEffect(() => { refresh(); }, [refresh]);

  const format = useCallback((amount, opts = {}) => {
    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency", currency, maximumFractionDigits: opts.decimals ?? 0,
      }).format(Number(amount) || 0);
    } catch {
      return `${currency} ${Math.round(Number(amount) || 0).toLocaleString()}`;
    }
  }, [currency]);

  return (
    <CurrencyContext.Provider value={{ currency, country, format, refresh, setCurrency }}>
      {children}
    </CurrencyContext.Provider>
  );
}

export const useCurrency = () => useContext(CurrencyContext);
