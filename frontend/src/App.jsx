/**
 * App.jsx — AgentSOC main shell
 *
 * Layout:
 *   ┌─ Header: logo + WatcherStatus ─────────────────────────────┐
 *   ├─ StatsBar ──────────────────────────────────────────────────┤
 *   ├─ Tab nav: Alerts | Attack Chains | Upload | Chat ───────────┤
 *   └─ Tab content + optional AlertPanel slide-in ───────────────┘
 */

import { useState } from "react";
import { useAlerts } from "./api/useAlerts";

import StatsBar       from "./components/StatsBar";
import LogFeed        from "./components/LogFeed";
import AlertPanel     from "./components/AlertPanel";
import AttackChains   from "./components/AttackChains";
import UploadPanel    from "./components/UploadPanel";
import ChatPanel      from "./components/ChatPanel";
import WatcherStatus  from "./components/WatcherStatus";

import { Shield } from "lucide-react";

const TABS = ["Alerts", "Attack Chains", "Upload Logs", "Chat"];

export default function App() {
  const { alerts, stats, refreshTick, wsStatus } = useAlerts();
  const [tab, setTab]               = useState("Alerts");
  const [selectedAlert, setSelected] = useState(null);

  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--bg)",
      color: "var(--text)",
      fontFamily: "'Inter', system-ui, sans-serif",
      display: "flex",
      flexDirection: "column",
    }}>

      {/* ── Header ── */}
      <header style={{
        padding: "0 24px",
        height: 56,
        display: "flex",
        alignItems: "center",
        borderBottom: "0.5px solid var(--border)",
        background: "var(--card)",
        flexShrink: 0,
        gap: 12,
      }}>
        <Shield size={20} color="var(--accent)" />
        <span style={{ fontWeight: 600, fontSize: 16, letterSpacing: "-0.02em" }}>
          AgentSOC
        </span>
        <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: 2 }}>
          Autonomous Cybersecurity Analyst
        </span>
        <div style={{ flex: 1 }} />
        <WatcherStatus wsStatus={wsStatus} />
      </header>

      {/* ── Stats bar ── */}
      <div style={{ padding: "16px 24px 0", flexShrink: 0 }}>
        <StatsBar stats={stats} refreshTick={refreshTick} />
      </div>

      {/* ── Tab nav ── */}
      <div style={{
        padding: "12px 24px 0",
        display: "flex",
        gap: 4,
        borderBottom: "0.5px solid var(--border)",
        flexShrink: 0,
      }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "8px 18px",
              borderRadius: "8px 8px 0 0",
              border: "0.5px solid var(--border)",
              borderBottom: tab === t ? "none" : "0.5px solid var(--border)",
              background: tab === t ? "var(--card)" : "transparent",
              color: tab === t ? "var(--text)" : "var(--muted)",
              fontWeight: tab === t ? 500 : 400,
              fontSize: 13,
              cursor: "pointer",
              marginBottom: tab === t ? -1 : 0,
              transition: "all 0.15s",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Main content ── */}
      <div style={{
        flex: 1,
        display: "flex",
        gap: 0,
        overflow: "hidden",
        padding: "20px 24px",
        gap: 16,
      }}>

        {/* Tab panels */}
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>

          {tab === "Alerts" && (
            <LogFeed
              alerts={alerts}
              refreshTick={refreshTick}
              onSelectAlert={setSelected}
            />
          )}

          {tab === "Attack Chains" && (
            <div style={{ overflowY: "auto", flex: 1 }}>
              <AttackChains refreshTick={refreshTick} />
            </div>
          )}

          {tab === "Upload Logs" && (
            <div style={{
              maxWidth: 720,
              background: "var(--card)",
              border: "0.5px solid var(--border)",
              borderRadius: 12,
              padding: 24,
            }}>
              <UploadPanel onComplete={() => {/* refreshTick auto-updates via WS */}} />
            </div>
          )}

          {tab === "Chat" && (
            <div style={{
              flex: 1,
              background: "var(--card)",
              border: "0.5px solid var(--border)",
              borderRadius: 12,
              padding: 20,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}>
              <ChatPanel />
            </div>
          )}
        </div>

        {/* Alert detail slide-in panel */}
        {selectedAlert && (
          <AlertPanel
            alert={selectedAlert}
            onClose={() => setSelected(null)}
          />
        )}
      </div>
    </div>
  );
}