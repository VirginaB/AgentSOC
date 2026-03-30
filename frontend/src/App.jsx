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
import { analyzeLog } from "./api/client";

import StatsBar       from "./components/StatsBar";
import LogFeed        from "./components/LogFeed";
import AlertPanel     from "./components/AlertPanel";
import AttackChains   from "./components/AttackChains";
import UploadPanel    from "./components/UploadPanel";
import ChatPanel      from "./components/ChatPanel";
import WatcherStatus  from "./components/WatcherStatus";

import { Loader2, Send, Shield } from "lucide-react";

const TABS = ["Alerts", "Attack Chains", "Upload Logs", "Chat"];

export default function App() {
  const { alerts, stats, refreshTick, wsStatus } = useAlerts();
  const [tab, setTab]               = useState("Alerts");
  const [selectedAlert, setSelected] = useState(null);
  const [singleLog, setSingleLog] = useState("");
  const [singleSourceIp, setSingleSourceIp] = useState("");
  const [submittingLog, setSubmittingLog] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const submitSingleLog = async () => {
    const trimmedLog = singleLog.trim();
    const trimmedIp = singleSourceIp.trim();

    if (!trimmedLog || submittingLog) return;

    setSubmittingLog(true);
    setSubmitError("");
    try {
      const { data } = await analyzeLog(trimmedLog, trimmedIp || undefined);
      setSingleLog("");
      setSingleSourceIp("");
      setSelected(data);
    } catch (err) {
      setSubmitError(
        err?.response?.data?.detail || "Unable to analyze this log right now."
      );
    } finally {
      setSubmittingLog(false);
    }
  };

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
            <div style={{ display: "flex", flexDirection: "column", gap: 16, minHeight: 0, flex: 1 }}>
              <div style={{
                background: "var(--card)",
                border: "0.5px solid var(--border)",
                borderRadius: 12,
                padding: 18,
                display: "flex",
                flexDirection: "column",
                gap: 12,
                flexShrink: 0,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}>
                      Analyze a single log
                    </div>
                    <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
                      Paste one raw log line and it will be classified, scored, and pushed into Alerts automatically.
                    </div>
                  </div>
                </div>

                <textarea
                  value={singleLog}
                  onChange={(e) => setSingleLog(e.target.value)}
                  placeholder="Paste a log entry here..."
                  rows={3}
                  style={{
                    width: "100%",
                    resize: "vertical",
                    borderRadius: 10,
                    border: "0.5px solid var(--border)",
                    background: "var(--surface)",
                    color: "var(--text)",
                    padding: "12px 14px",
                    fontSize: 13,
                    lineHeight: 1.5,
                    outline: "none",
                  }}
                />

                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  <input
                    value={singleSourceIp}
                    onChange={(e) => setSingleSourceIp(e.target.value)}
                    placeholder="Optional source IP"
                    style={{
                      width: 220,
                      maxWidth: "100%",
                      borderRadius: 10,
                      border: "0.5px solid var(--border)",
                      background: "var(--surface)",
                      color: "var(--text)",
                      padding: "10px 12px",
                      fontSize: 13,
                      outline: "none",
                    }}
                  />
                  <button
                    onClick={submitSingleLog}
                    disabled={!singleLog.trim() || submittingLog}
                    style={{
                      padding: "10px 16px",
                      borderRadius: 10,
                      border: "none",
                      background: "var(--accent)",
                      color: "#fff",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: !singleLog.trim() || submittingLog ? "not-allowed" : "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      opacity: !singleLog.trim() || submittingLog ? 0.6 : 1,
                    }}
                  >
                    {submittingLog ? <Loader2 size={15} style={{ animation: "spin 1s linear infinite" }} /> : <Send size={15} />}
                    {submittingLog ? "Analyzing..." : "Analyze log"}
                  </button>
                </div>

                {submitError && (
                  <div style={{
                    fontSize: 12,
                    color: "#fca5a5",
                    background: "rgba(127, 29, 29, 0.18)",
                    border: "0.5px solid rgba(252, 165, 165, 0.35)",
                    borderRadius: 10,
                    padding: "10px 12px",
                  }}>
                    {submitError}
                  </div>
                )}
              </div>

              <div style={{ minHeight: 0, flex: 1 }}>
                <LogFeed
                  alerts={alerts}
                  refreshTick={refreshTick}
                  onSelectAlert={setSelected}
                />
              </div>
            </div>
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

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
