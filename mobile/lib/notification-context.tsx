import { createContext, PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { approvalAlertsEnabled, cachedPushToken, disableApprovalAlerts, enableApprovalAlerts } from "@/lib/notifications";

type NoticeContextValue = { enabled: boolean; registering: boolean; remoteReady: boolean; enable: () => Promise<boolean>; disable: () => Promise<void> };
const NoticeContext = createContext<NoticeContextValue | null>(null);
export function NotificationProvider({ children }: PropsWithChildren) {
  const [enabled, setEnabled] = useState(false); const [registering, setRegistering] = useState(false); const [remoteReady, setRemoteReady] = useState(false);
  useEffect(() => { void (async () => { setEnabled(await approvalAlertsEnabled()); setRemoteReady(Boolean(await cachedPushToken())); })(); }, []);
  const enable = useCallback(async () => { setRegistering(true); try { const result = await enableApprovalAlerts(); setEnabled(result.enabled); if (result.token) { try { await api.notifications.register(result.token); setRemoteReady(true); } catch { setRemoteReady(false); } } return result.enabled; } finally { setRegistering(false); } }, []);
  const disable = useCallback(async () => { await disableApprovalAlerts(); setEnabled(false); setRemoteReady(false); }, []);
  const value = useMemo(() => ({ enabled, registering, remoteReady, enable, disable }), [enabled, registering, remoteReady, enable, disable]); return <NoticeContext.Provider value={value}>{children}</NoticeContext.Provider>;
}
export function useNotifications() { const context = useContext(NoticeContext); if (!context) throw new Error("useNotifications must be used inside NotificationProvider."); return context; }
