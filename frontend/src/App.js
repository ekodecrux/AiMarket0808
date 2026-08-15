import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ClientProvider } from "@/context/ClientContext";
import { CurrencyProvider } from "@/context/CurrencyContext";
import { Layout } from "@/components/Layout";
import Login from "@/pages/Login";
import Flow from "@/pages/Flow";
import Approvals from "@/pages/Approvals";
import Dashboard from "@/pages/Dashboard";
import Strategy from "@/pages/Strategy";
import ContentStudio from "@/pages/ContentStudio";
import Social from "@/pages/Social";
import Campaigns from "@/pages/Campaigns";
import BudgetPlanner from "@/pages/BudgetPlanner";
import Leads from "@/pages/Leads";
import SalesAssistant from "@/pages/SalesAssistant";
import CompetitorRadar from "@/pages/CompetitorRadar";
import Analytics from "@/pages/Analytics";
import Agents from "@/pages/Agents";
import Clients from "@/pages/Clients";
import Integrations from "@/pages/Integrations";
import MissionPlanner from "@/pages/MissionPlanner";
import Brain from "@/pages/Brain";
import Intelligence from "@/pages/Intelligence";
import Learning from "@/pages/Learning";
function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading || user === null)
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-600 animate-pulse">Initializing Engine</div>
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function LoginGate() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return <Login />;
}

const routes = [
  ["/", Dashboard], ["/flow", Flow], ["/approvals", Approvals],
  ["/strategy", Strategy], ["/content", ContentStudio],
  ["/social", Social], ["/campaigns", Campaigns], ["/budget", BudgetPlanner], ["/leads", Leads],
  ["/sales", SalesAssistant], ["/radar", CompetitorRadar], ["/analytics", Analytics],
  ["/missions", MissionPlanner], ["/brain", Brain], ["/intel", Intelligence], ["/learning", Learning],
  ["/clients", Clients], ["/settings", Integrations], ["/integrations", Integrations], ["/agents", Agents],
];

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <ClientProvider>
            <CurrencyProvider>
              <Toaster theme="dark" position="top-right" toastOptions={{ style: { background: "#0A0A0A", border: "1px solid #27272A", borderRadius: 0, color: "#fff" } }} />
              <Routes>
                <Route path="/login" element={<LoginGate />} />
                {routes.map(([path, Comp]) => (
                  <Route key={path} path={path} element={<Protected><Comp /></Protected>} />
                ))}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </CurrencyProvider>
          </ClientProvider>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
