import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const ClientContext = createContext(null);

export function ClientProvider({ children }) {
  const { user } = useAuth();
  const [clients, setClients] = useState([]);
  const [activeClientId, setActiveClientId] = useState(() => localStorage.getItem("nexus_active_client") || "");

  const refresh = useCallback(() => {
    if (!user || user.role === "client") { setClients([]); return; }
    api.get("/clients").then((r) => setClients(r.data)).catch(() => {});
  }, [user]);

  useEffect(() => { refresh(); }, [refresh]);

  const setActive = (id) => {
    setActiveClientId(id);
    if (id) localStorage.setItem("nexus_active_client", id);
    else localStorage.removeItem("nexus_active_client");
  };

  const activeClient = clients.find((c) => c.id === activeClientId) || null;

  return (
    <ClientContext.Provider value={{ clients, activeClientId, activeClient, setActive, refresh }}>
      {children}
    </ClientContext.Provider>
  );
}

export const useClient = () => useContext(ClientContext);
