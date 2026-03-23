import { useState, useRef, useEffect } from "react";
import { sendChat } from "../api/client";
import { Send, Bot, User } from "lucide-react";

const SUGGESTED = [
  "What is the most critical threat right now?",
  "Summarize today's security incidents.",
  "Are there any attack chains in progress?",
  "Which source IP has the most alerts?",
];

export default function ChatPanel() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hello! I'm AgentSOC, your AI security analyst. Ask me anything about the current alerts." }
  ]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    const msg = (text || input).trim();
    if (!msg || loading) return;
    setInput("");

    const userMsg = { role: "user", content: msg };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const history = messages.slice(-8);  // last 4 turns
      const { data } = await sendChat(msg, history);
      setMessages(prev => [...prev, { role: "assistant", content: data.reply }]);
    } catch (_) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "Sorry, I couldn't connect to the LLM service. Make sure Ollama is running."
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 400 }}>

      {/* Suggested questions */}
      {messages.length <= 1 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
          {SUGGESTED.map(q => (
            <button key={q} onClick={() => send(q)} style={{
              fontSize: 12, padding: "5px 12px", borderRadius: 99,
              border: "0.5px solid var(--border)", background: "var(--card)",
              color: "var(--muted)", cursor: "pointer",
              transition: "all 0.15s",
            }}
            onMouseEnter={e => { e.target.style.background = "var(--hover)"; e.target.style.color = "var(--text)"; }}
            onMouseLeave={e => { e.target.style.background = "var(--card)"; e.target.style.color = "var(--muted)"; }}
            >{q}</button>
          ))}
        </div>
      )}

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", display: "flex",
        flexDirection: "column", gap: 12, paddingBottom: 8 }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            display: "flex", gap: 10,
            flexDirection: m.role === "user" ? "row-reverse" : "row",
            alignItems: "flex-start",
          }}>
            {/* Avatar */}
            <div style={{
              width: 30, height: 30, borderRadius: "50%", flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: m.role === "assistant" ? "var(--accent)" : "var(--surface)",
              border: "0.5px solid var(--border)",
            }}>
              {m.role === "assistant"
                ? <Bot size={16} color="#fff" />
                : <User size={16} color="var(--muted)" />}
            </div>

            {/* Bubble */}
            <div style={{
              maxWidth: "80%", padding: "10px 14px", borderRadius: 12,
              fontSize: 13, lineHeight: 1.65, whiteSpace: "pre-wrap",
              background: m.role === "user" ? "var(--accent)" : "var(--surface)",
              color: m.role === "user" ? "#fff" : "var(--text)",
              border: "0.5px solid var(--border)",
              borderTopRightRadius: m.role === "user" ? 4 : 12,
              borderTopLeftRadius: m.role === "assistant" ? 4 : 12,
            }}>
              {m.content}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <div style={{ width: 30, height: 30, borderRadius: "50%",
              background: "var(--accent)", display: "flex",
              alignItems: "center", justifyContent: "center" }}>
              <Bot size={16} color="#fff" />
            </div>
            <div style={{ padding: "12px 16px", background: "var(--surface)",
              borderRadius: 12, borderTopLeftRadius: 4,
              border: "0.5px solid var(--border)", display: "flex", gap: 5 }}>
              {[0, 1, 2].map(i => (
                <span key={i} style={{
                  width: 6, height: 6, borderRadius: "50%",
                  background: "var(--muted)", display: "inline-block",
                  animation: `bounce 1.2s ${i * 0.2}s infinite`,
                }} />
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: 8, marginTop: 10,
        borderTop: "0.5px solid var(--border)", paddingTop: 10 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
          placeholder="Ask about current threats..."
          style={{
            flex: 1, padding: "9px 14px", borderRadius: 10, fontSize: 13,
            border: "0.5px solid var(--border)", background: "var(--surface)",
            color: "var(--text)", outline: "none",
          }}
        />
        <button onClick={() => send()} disabled={!input.trim() || loading} style={{
          padding: "9px 16px", borderRadius: 10, border: "none",
          background: "var(--accent)", color: "#fff", cursor: "pointer",
          display: "flex", alignItems: "center", gap: 6,
          opacity: !input.trim() || loading ? 0.5 : 1,
          transition: "opacity 0.15s",
        }}>
          <Send size={15} />
        </button>
      </div>

      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}