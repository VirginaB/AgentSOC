import { useState, useEffect, useCallback } from "react";
import StatsBar from "./components/StatsBar";
import LogFeed from "./components/LogFeed";
import AlertPanel from "./components/AlertPanel";
import AttackChains from "./components/AttackChains";
import ChatPanel from "./components/ChatPanel";
import { startStream, stopStream, streamStatus, analyzeLog } from "./api/client";
import { Shield, Play, Square, MessageCircle, GitBranch, Send } from "lucide-react";

const TABS = ["Alerts", "Attack Chains", "Chat"];

const ATTACK_SCENARIOS = {
  "Brute Force": [
    { log: "Failed password for root from 192.168.10.5 port 22 ssh2", ip: "192.168.10.5" },
    { log: "Failed password for root from 192.168.10.5 port 22 ssh2", ip: "192.168.10.5" },
    { log: "Failed password for root from 192.168.10.5 port 22 ssh2", ip: "192.168.10.5" },
    { log: "Failed password for root from 192.168.10.5 port 22 ssh2", ip: "192.168.10.5" },
    { log: "Failed password for root from 192.168.10.5 port 22 ssh2", ip: "192.168.10.5" },
    { log: "Accepted password for root from 192.168.10.5 port 22 ssh2", ip: "192.168.10.5" },
  ],
  "Privilege Escalation": [
    { log: "Accepted password for admin from 10.0.0.20 port 22", ip: "10.0.0.20" },
    { log: "sudo: admin ran /usr/bin/su as root on server01", ip: "10.0.0.20" },
    { log: "File /etc/sudoers accessed by process bash uid=0", ip: "10.0.0.20" },
  ],
  "Data Exfiltration": [
    ...Array(10).fill(null).map((_, i) => ({
      log: `File /var/sensitive/record_${i}.csv read by process python3`,
      ip: "172.16.0.50",
    })),
    { log: "Outbound TCP connection established to 185.220.101.45:443 from 172.16.0.50", ip: "172.16.0.50" },
  ],
};

export default function App() {
  const [activeTab, setActiveTab]       = useState("Alerts");
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [streaming, setStreaming]       = useState(false);
  const [refreshTick, setRefreshTick]   = useState(0);
  const [simulating, setSimulating]     = useState(false);
  const [customLog, setCustomLog]       = useState("");
  const [submitting, setSubmitting]     = useState(false);
  const [showLogInput, setShowLogInput] = useState(false);

  // Auto-refresh every 4 seconds
  useEffect(() => {
    const t = setInterval(() => setRefreshTick(n => n + 1), 4000);
    return () => clearInterval(t);
  }, []);

  // Check stream status on mount
  useEffect(() => {
    streamStatus().then(r => setStreaming(r.data.running)).catch(() => {});
  }, []);

  const toggleStream = async () => {
    if (streaming) {
      await stopStream();
      setStreaming(false);
    } else {
      await startStream();
      setStreaming(true);
    }
  };

  const runSimulation = async (scenarioName) => {
    if (simulating) return;
    setSimulating(true);
    setActiveTab("Alerts");
    const logs = ATTACK_SCENARIOS[scenarioName];
    for (const entry of logs) {
      try {
        await analyzeLog(entry.log, entry.ip);
        setRefreshTick(n => n + 1);
        await new Promise(r => setTimeout(r, 1500));
      } catch (_) {}
    }
    setRefreshTick(n => n + 1);
    setSimulating(false);
  };

  const submitCustomLog = async () => {
    if (!customLog.trim() || submitting) return;
    setSubmitting(true);
    try {
      await analyzeLog(customLog.trim());
      setCustomLog("");
      setShowLogInput(false);
      setRefreshTick(n => n + 1);
    } catch (_) {} finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--text)",
      fontFamily: "system-ui, -apple-system, sans-serif" }}>

      {/* Top nav */}
      <header style={{ background: "var(--card)", borderBottom: "0.5px solid var(--border)",
        padding: "0 24px", display: "flex", alignItems: "center",
        height: 56, gap: 16, position: "sticky", top: 0, zIndex: 100 }}>
        <Shield size={22} color="var(--accent)" />
        <span style={{ fontWeight: 700, fontSize: 18, letterSpacing: "-0.02em" }}>
          AgentSOC
        </span>
        <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: -4 }}>
          Autonomous Cybersecurity Analyst
        </span>

        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          {/* Custom log input */}
          {showLogInput && (
            <div style={{ display: "flex", gap: 6 }}>
              <input
                value={customLog}
                onChange={e => setCustomLog(e.target.value)}
                onKeyDown={e => e.key === "Enter" && submitCustomLog()}
                placeholder="Paste a log line..."
                autoFocus
                style={{ padding: "6px 12px", borderRadius: 8, fontSize: 13,
                  border: "0.5px solid var(--border)", background: "var(--surface)",
                  color: "var(--text)", width: 280, outline: "none" }}
              />
              <button onClick={submitCustomLog} disabled={submitting || !customLog.trim()}
                style={{ padding: "6px 12px", borderRadius: 8, border: "none",
                  background: "var(--accent)", color: "#fff", fontSize: 13,
                  cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
                <Send size={13} />{submitting ? "..." : "Analyze"}
              </button>
            </div>
          )}
          <button onClick={() => setShowLogInput(v => !v)} style={{
            padding: "6px 14px", borderRadius: 8, fontSize: 13, fontWeight: 500,
            border: "0.5px solid var(--border)", background: "var(--surface)",
            color: "var(--muted)", cursor: "pointer" }}>
            {showLogInput ? "Cancel" : "+ Analyze log"}
          </button>

          {/* Attack simulator */}
          {Object.keys(ATTACK_SCENARIOS).map(name => (
            <button key={name} onClick={() => runSimulation(name)}
              disabled={simulating}
              style={{ padding: "6px 14px", borderRadius: 8, fontSize: 13,
                fontWeight: 500, border: "0.5px solid #fca5a5",
                background: simulating ? "var(--surface)" : "#fef2f2",
                color: simulating ? "var(--muted)" : "#991b1b",
                cursor: simulating ? "not-allowed" : "pointer" }}>
              {simulating ? "Simulating..." : `Simulate: ${name}`}
            </button>
          ))}

          {/* Stream toggle */}
          <button onClick={toggleStream} style={{
            padding: "6px 14px", borderRadius: 8, fontSize: 13, fontWeight: 500,
            border: `0.5px solid ${streaming ? "#fca5a5" : "var(--border)"}`,
            background: streaming ? "#fef2f2" : "var(--surface)",
            color: streaming ? "#991b1b" : "var(--muted)",
            cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
            {streaming
              ? <><Square size={13} fill="#dc2626" color="#dc2626" /> Stop stream</>
              : <><Play size={13} /> Start stream</>}
          </button>
        </div>
      </header>

      <main style={{ padding: "20px 24px", maxWidth: 1600, margin: "0 auto" }}>

        {/* Stats bar */}
        <div style={{ marginBottom: 20 }}>
          <StatsBar refreshTick={refreshTick} />
        </div>

        {/* Tab bar */}
        <div style={{ display: "flex", gap: 2, marginBottom: 16,
          borderBottom: "0.5px solid var(--border)", paddingBottom: 0 }}>
          {TABS.map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{
              padding: "8px 18px", fontSize: 13, fontWeight: 500,
              border: "none", background: "none", cursor: "pointer",
              color: activeTab === tab ? "var(--accent)" : "var(--muted)",
              borderBottom: activeTab === tab
                ? "2px solid var(--accent)" : "2px solid transparent",
              marginBottom: -1, transition: "all 0.15s",
              display: "flex", alignItems: "center", gap: 6,
            }}>
              {tab === "Chat" && <MessageCircle size={14} />}
              {tab === "Attack Chains" && <GitBranch size={14} />}
              {tab}
            </button>
          ))}
        </div>

        {/* Main content area */}
        <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
          {/* Left: tab content */}
          <div style={{ flex: 1, minWidth: 0, minHeight: "70vh" }}>
            {activeTab === "Alerts" && (
              <LogFeed
                refreshTick={refreshTick}
                onSelectAlert={a => { setSelectedAlert(a); setActiveTab("Alerts"); }}
              />
            )}
            {activeTab === "Attack Chains" && (
              <AttackChains refreshTick={refreshTick} />
            )}
            {activeTab === "Chat" && <ChatPanel />}
          </div>

          {/* Right: alert detail panel (only on Alerts tab) */}
          {activeTab === "Alerts" && selectedAlert && (
            <AlertPanel
              alert={selectedAlert}
              onClose={() => setSelectedAlert(null)}
            />
          )}
        </div>
      </main>
    </div>
  );
}