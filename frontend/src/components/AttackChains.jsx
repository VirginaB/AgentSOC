import { useEffect, useState } from "react";
import { getChains } from "../api/client";
import { AlertOctagon, ChevronDown, ChevronUp } from "lucide-react";

const SEV_COLOR = {
  CRITICAL: { bg: "#fef2f2", border: "#fca5a5", text: "#991b1b", dot: "#dc2626" },
  HIGH:     { bg: "#fff7ed", border: "#fdba74", text: "#9a3412", dot: "#ea580c" },
};

export default function AttackChains({ refreshTick }) {
  const [chains, setChains]     = useState([]);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    getChains()
      .then(r => setChains(r.data))
      .catch(() => {});
  }, [refreshTick]);

  if (chains.length === 0) return (
    <div style={{ padding: "20px 0", textAlign: "center", color: "var(--muted)",
      fontSize: 13 }}>
      No attack chains detected yet. Run the attack simulator to trigger one.
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {chains.map(chain => {
        const c = SEV_COLOR[chain.severity] || SEV_COLOR["HIGH"];
        const open = expanded[chain.id];
        return (
          <div key={chain.id} style={{
            border: `1px solid ${c.border}`, borderRadius: 10,
            background: c.bg, overflow: "hidden",
          }}>
            {/* Chain header */}
            <div style={{ padding: "12px 16px", display: "flex",
              alignItems: "flex-start", gap: 10, cursor: "pointer" }}
              onClick={() => setExpanded(e => ({ ...e, [chain.id]: !e[chain.id] }))}>
              <AlertOctagon size={18} color={c.dot} style={{ flexShrink: 0, marginTop: 1 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: c.text }}>
                  {chain.chain_name}
                </div>
                <div style={{ fontSize: 12, color: c.text, opacity: 0.75, marginTop: 2 }}>
                  {chain.source_ip} &nbsp;·&nbsp;{" "}
                  {new Date(chain.detected_at).toLocaleString()}
                </div>
              </div>
              <span style={{ fontSize: 11, fontWeight: 600, padding: "2px 10px",
                borderRadius: 99, background: c.dot, color: "#fff", flexShrink: 0 }}>
                {chain.severity}
              </span>
              {open
                ? <ChevronUp size={16} color={c.dot} />
                : <ChevronDown size={16} color={c.dot} />}
            </div>

            {/* Expanded detail */}
            {open && (
              <div style={{ borderTop: `0.5px solid ${c.border}`,
                padding: "12px 16px", background: "rgba(255,255,255,0.6)" }}>
                <p style={{ fontSize: 13, color: c.text, margin: "0 0 12px",
                  lineHeight: 1.6 }}>
                  {chain.description}
                </p>

                {/* Event timeline */}
                {chain.alert_ids?.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 500, color: c.text,
                      opacity: 0.6, textTransform: "uppercase",
                      letterSpacing: "0.06em", marginBottom: 8 }}>
                      Event sequence
                    </div>
                    <div style={{ display: "flex", alignItems: "center",
                      flexWrap: "wrap", gap: 0 }}>
                      {chain.alert_ids.map((aid, i) => (
                        <div key={aid} style={{ display: "flex", alignItems: "center" }}>
                          <div style={{ padding: "4px 12px", borderRadius: 99,
                            background: c.dot, color: "#fff",
                            fontSize: 12, fontWeight: 500 }}>
                            Alert #{aid}
                          </div>
                          {i < chain.alert_ids.length - 1 && (
                            <div style={{ width: 24, height: 2,
                              background: c.dot, opacity: 0.4 }} />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}