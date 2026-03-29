/**
 * UploadPanel.jsx — Redesigned file upload UI
 *
 * Features:
 *  - Drag-and-drop zone with animated feedback
 *  - File type + size validation before upload
 *  - Upload progress indication
 *  - Structured results table with tier breakdown
 *  - Clear error display
 */

import { useState, useRef, useCallback } from "react";
import { uploadFile } from "../api/client";
import SeverityBadge from "./SeverityBadge";
import { Upload, FileText, X, CheckCircle, AlertCircle, Loader } from "lucide-react";

const ACCEPTED_EXTENSIONS = [".txt", ".log", ".csv", ".tsv", ".jsonl", ".out"];
const MAX_SIZE_MB = 10;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

const TIER_COLORS = {
  CRITICAL: "#dc2626",
  HIGH:     "#ea580c",
  MEDIUM:   "#ca8a04",
  LOW:      "#16a34a",
};

export default function UploadPanel({ onComplete }) {
  const [dragOver, setDragOver]   = useState(false);
  const [file, setFile]           = useState(null);
  const [error, setError]         = useState(null);
  const [status, setStatus]       = useState("idle"); // idle | uploading | done | error
  const [result, setResult]       = useState(null);
  const [progress, setProgress]   = useState(0);
  const fileInputRef = useRef(null);
  const progressTimer = useRef(null);

  const validateFile = (f) => {
    if (!f) return "No file selected.";
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext))
      return `Unsupported format. Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}`;
    if (f.size > MAX_SIZE_BYTES)
      return `File too large (${(f.size / 1024 / 1024).toFixed(1)} MB). Max: ${MAX_SIZE_MB} MB`;
    return null;
  };

  const selectFile = (f) => {
    setError(null);
    setResult(null);
    setStatus("idle");
    const err = validateFile(f);
    if (err) { setError(err); return; }
    setFile(f);
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) selectFile(f);
  }, []);

  const onDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = () => setDragOver(false);

  const simulateProgress = () => {
    setProgress(0);
    let p = 0;
    progressTimer.current = setInterval(() => {
      p += Math.random() * 12;
      if (p >= 90) { clearInterval(progressTimer.current); p = 90; }
      setProgress(Math.min(p, 90));
    }, 300);
  };

  const finishProgress = () => {
    clearInterval(progressTimer.current);
    setProgress(100);
  };

  const handleUpload = async () => {
    if (!file || status === "uploading") return;
    setStatus("uploading");
    setError(null);
    simulateProgress();

    try {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await uploadFile(formData);
      finishProgress();
      setTimeout(() => {
        setStatus("done");
        setResult(data);
        if (onComplete) onComplete();
      }, 400);
    } catch (err) {
      clearInterval(progressTimer.current);
      setStatus("error");
      setError(
        err?.response?.data?.detail ||
        "Upload failed. Please check the file and try again."
      );
    }
  };

  const reset = () => {
    setFile(null);
    setError(null);
    setResult(null);
    setStatus("idle");
    setProgress(0);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Compute tier summary from results
  const tierSummary = result
    ? result.results.reduce((acc, r) => {
        acc[r.risk_tier] = (acc[r.risk_tier] || 0) + 1;
        return acc;
      }, {})
    : {};

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Drop zone */}
      {status !== "done" && (
        <div
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => !file && fileInputRef.current?.click()}
          style={{
            border: `2px dashed ${dragOver ? "var(--accent)" : file ? "var(--accent)" : "var(--border)"}`,
            borderRadius: 12,
            padding: "32px 24px",
            textAlign: "center",
            cursor: file ? "default" : "pointer",
            background: dragOver
              ? "color-mix(in srgb, var(--accent) 6%, transparent)"
              : "var(--surface)",
            transition: "all 0.2s ease",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Progress bar overlay */}
          {status === "uploading" && (
            <div style={{
              position: "absolute", bottom: 0, left: 0, height: 3,
              width: `${progress}%`, background: "var(--accent)",
              transition: "width 0.3s ease", borderRadius: "0 2px 0 0",
            }} />
          )}

          {!file ? (
            /* Empty state */
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
              <div style={{
                width: 52, height: 52, borderRadius: 12,
                background: "color-mix(in srgb, var(--accent) 10%, transparent)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Upload size={24} color="var(--accent)" />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text)", marginBottom: 4 }}>
                  Drop a log file here, or{" "}
                  <span style={{ color: "var(--accent)", textDecoration: "underline", cursor: "pointer" }}>
                    browse
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>
                  {ACCEPTED_EXTENSIONS.join("  ·  ")} &nbsp;·&nbsp; max {MAX_SIZE_MB} MB
                </div>
              </div>
            </div>
          ) : (
            /* File selected state */
            <div style={{
              display: "flex", alignItems: "center", gap: 12,
              justifyContent: "space-between",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: 8,
                  background: "color-mix(in srgb, var(--accent) 10%, transparent)",
                  display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                }}>
                  <FileText size={20} color="var(--accent)" />
                </div>
                <div style={{ textAlign: "left" }}>
                  <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text)" }}>
                    {file.name}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>
                    {(file.size / 1024).toFixed(1)} KB
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {status === "uploading" ? (
                  <div style={{ display: "flex", alignItems: "center", gap: 8,
                    fontSize: 13, color: "var(--muted)" }}>
                    <Loader size={15} style={{ animation: "spin 1s linear infinite" }} />
                    Analyzing {progress.toFixed(0)}%
                  </div>
                ) : (
                  <>
                    <button
                      onClick={handleUpload}
                      style={{
                        padding: "7px 18px", borderRadius: 8, border: "none",
                        background: "var(--accent)", color: "#fff", cursor: "pointer",
                        fontSize: 13, fontWeight: 500,
                      }}
                    >
                      Analyze
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); reset(); }}
                      style={{
                        padding: 6, borderRadius: 8, border: "0.5px solid var(--border)",
                        background: "transparent", cursor: "pointer",
                        display: "flex", alignItems: "center", color: "var(--muted)",
                      }}
                    >
                      <X size={15} />
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Hidden input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(",")}
        style={{ display: "none" }}
        onChange={(e) => selectFile(e.target.files?.[0])}
      />

      {/* Error */}
      {error && (
        <div style={{
          display: "flex", alignItems: "flex-start", gap: 10,
          padding: "12px 14px", borderRadius: 10,
          background: "#fef2f2", border: "0.5px solid #fca5a5",
        }}>
          <AlertCircle size={16} color="#dc2626" style={{ flexShrink: 0, marginTop: 1 }} />
          <div style={{ fontSize: 13, color: "#991b1b" }}>{error}</div>
        </div>
      )}

      {/* Results */}
      {status === "done" && result && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

          {/* Summary header */}
          <div style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "12px 16px", borderRadius: 10,
            background: "#f0fdf4", border: "0.5px solid #86efac",
          }}>
            <CheckCircle size={18} color="#16a34a" style={{ flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 500, color: "#166534" }}>
                {result.processed} logs analyzed from{" "}
                <code style={{ fontSize: 13 }}>{result.filename}</code>
              </div>
              {result.skipped > 0 && (
                <div style={{ fontSize: 12, color: "#16a34a", marginTop: 2 }}>
                  {result.skipped} logs skipped (limit reached)
                </div>
              )}
            </div>
            <button onClick={reset} style={{
              fontSize: 12, padding: "4px 12px", borderRadius: 99,
              border: "0.5px solid #86efac", background: "transparent",
              color: "#166534", cursor: "pointer",
            }}>
              Upload another
            </button>
          </div>

          {/* Tier breakdown pills */}
          {Object.keys(tierSummary).length > 0 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map(tier =>
                tierSummary[tier] ? (
                  <div key={tier} style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "5px 14px", borderRadius: 99,
                    border: `0.5px solid ${TIER_COLORS[tier]}22`,
                    background: `${TIER_COLORS[tier]}11`,
                  }}>
                    <span style={{
                      width: 7, height: 7, borderRadius: "50%",
                      background: TIER_COLORS[tier], flexShrink: 0,
                    }} />
                    <span style={{ fontSize: 13, fontWeight: 500, color: TIER_COLORS[tier] }}>
                      {tierSummary[tier]} {tier}
                    </span>
                  </div>
                ) : null
              )}
              {result.chains_detected > 0 && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "5px 14px", borderRadius: 99,
                  border: "0.5px solid #7c3aed33",
                  background: "#7c3aed11",
                }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: "50%",
                    background: "#7c3aed", flexShrink: 0,
                  }} />
                  <span style={{ fontSize: 13, fontWeight: 500, color: "#7c3aed" }}>
                    {result.chains_detected} attack chain{result.chains_detected !== 1 ? "s" : ""}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Results table */}
          <div style={{
            borderRadius: 10, border: "0.5px solid var(--border)",
            overflow: "hidden", maxHeight: 320, overflowY: "auto",
          }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "var(--surface)", position: "sticky", top: 0 }}>
                  {["#", "Log (truncated)", "Category", "Tier"].map(h => (
                    <th key={h} style={{
                      padding: "8px 12px", textAlign: "left",
                      fontWeight: 500, fontSize: 11, color: "var(--muted)",
                      textTransform: "uppercase", letterSpacing: "0.05em",
                      borderBottom: "0.5px solid var(--border)",
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.results.map((r, i) => (
                  <tr key={r.id} style={{
                    background: i % 2 === 0 ? "var(--card)" : "var(--surface)",
                    borderBottom: "0.5px solid var(--border)",
                  }}>
                    <td style={{ padding: "7px 12px", color: "var(--muted)", fontFamily: "monospace" }}>
                      {r.id}
                    </td>
                    <td style={{ padding: "7px 12px", maxWidth: 260 }}>
                      <span style={{
                        display: "block", overflow: "hidden",
                        textOverflow: "ellipsis", whiteSpace: "nowrap",
                        color: "var(--text)",
                      }}>{r.log_text}</span>
                    </td>
                    <td style={{ padding: "7px 12px", fontFamily: "monospace",
                      color: "var(--muted)", whiteSpace: "nowrap" }}>
                      {r.label}
                    </td>
                    <td style={{ padding: "7px 12px" }}>
                      <SeverityBadge tier={r.risk_tier} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}