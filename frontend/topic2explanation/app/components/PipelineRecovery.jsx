"use client";
import React, { useState, useEffect } from "react";

export default function PipelineRecovery() {
  const [runId, setRunId] = useState("");
  const [runStatus, setRunStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [forceCpu, setForceCpu] = useState(false);
  const [logs, setLogs] = useState([]);
  const [errorMsg, setErrorMsg] = useState("");

  const backendUrl = "http://localhost:8000";

  const fetchStatus = async () => {
    if (!runId.trim()) return;
    setLoading(true);
    setErrorMsg("");
    try {
      const res = await fetch(`${backendUrl}/api/pipeline/runs/${runId}/status`);
      if (!res.ok) throw new Error(`Run ${runId} not found`);
      const data = await res.json();
      setRunStatus(data);
    } catch (err) {
      setErrorMsg(err.message);
      setRunStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const handleResume = async () => {
    if (!runId.trim()) return;
    setResuming(true);
    setErrorMsg("");
    try {
      const res = await fetch(`${backendUrl}/api/pipeline/runs/${runId}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force_cpu: forceCpu })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Resume failed");
      }
      // Re-fetch status & attach event stream
      await fetchStatus();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setResuming(false);
    }
  };

  // SSE Stream Listener
  useEffect(() => {
    if (!runId || !runStatus) return;
    const eventSource = new EventSource(`${backendUrl}/api/pipeline/runs/${runId}/events`);
    
    eventSource.addEventListener("pipeline_event", (e) => {
      try {
        const data = JSON.parse(e.data);
        setLogs((prev) => [...prev, data]);
      } catch (err) {
        console.error("Error parsing event data", err);
      }
    });

    return () => {
      eventSource.close();
    };
  }, [runId, runStatus]);

  const stages = [
    { id: "script", name: "Script Generation" },
    { id: "audio_tts", name: "Audio TTS Synthesis" },
    { id: "scrapling_images", name: "Scrapling Image Scraping" },
    { id: "sadtalker", name: "SadTalker Face Animation" },
    { id: "stitching", name: "Video Stitching" },
    { id: "validation", name: "Final Validation" }
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto bg-slate-900 text-white rounded-xl shadow-2xl space-y-6">
      <div className="flex items-center justify-between border-b border-slate-700 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-cyan-400">⚡ Universal Pipeline Recovery Engine</h2>
          <p className="text-sm text-slate-400">Inspect run checkpoints, diagnose artifact failures, and resume execution from exact failure points.</p>
        </div>
      </div>

      {/* Run ID Input Search Bar */}
      <div className="flex gap-3">
        <input
          type="text"
          value={runId}
          onChange={(e) => setRunId(e.target.value)}
          placeholder="Enter Run ID (e.g. run_9f8b7c6a...)"
          className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg focus:outline-none focus:border-cyan-500"
        />
        <button
          onClick={fetchStatus}
          disabled={loading}
          className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-medium rounded-lg transition disabled:opacity-50"
        >
          {loading ? "Checking..." : "Inspect Run"}
        </button>
      </div>

      {errorMsg && (
        <div className="p-4 bg-red-950 border border-red-800 rounded-lg text-red-300 text-sm">
          ⚠️ {errorMsg}
        </div>
      )}

      {runStatus && (
        <div className="space-y-6">
          {/* Header Info */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-slate-800/60 rounded-lg border border-slate-700">
            <div>
              <span className="text-xs text-slate-400 block">Topic</span>
              <span className="font-semibold text-slate-200">{runStatus.checkpoint.topic}</span>
            </div>
            <div>
              <span className="text-xs text-slate-400 block">Overall Status</span>
              <span className={`inline-block px-2 py-0.5 text-xs font-bold rounded ${
                runStatus.checkpoint.overall_status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                runStatus.checkpoint.overall_status === 'FAILED' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
                'bg-amber-500/20 text-amber-400 border border-amber-500/30'
              }`}>
                {runStatus.checkpoint.overall_status}
              </span>
            </div>
            <div>
              <span className="text-xs text-slate-400 block">Earliest Recovery Node</span>
              <span className="font-mono text-cyan-300 font-bold">{runStatus.earliest_recovery_stage}</span>
            </div>
            <div>
              <span className="text-xs text-slate-400 block">Execution Lock</span>
              <span className="text-slate-300">{runStatus.checkpoint.execution_lock ? "🔒 Locked (Running)" : "🔓 Unlocked"}</span>
            </div>
          </div>

          {/* DAG Timeline */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Pipeline DAG Stage Status</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {stages.map((stg) => {
                const info = runStatus.checkpoint.stages[stg.id] || {};
                const check = runStatus.integrity_report?.stage_checks?.[stg.id] || {};
                return (
                  <div key={stg.id} className="p-3 bg-slate-800 rounded-lg border border-slate-700 space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium text-slate-200">{stg.name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded font-mono font-semibold ${
                        info.status === 'COMPLETED' ? 'bg-emerald-900/60 text-emerald-300' :
                        info.status === 'FAILED' ? 'bg-rose-900/60 text-rose-300' :
                        info.status === 'INVALID' ? 'bg-purple-900/60 text-purple-300' : 'bg-slate-700 text-slate-400'
                      }`}>
                        {info.status || 'PENDING'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 truncate">{check.reason || 'Not evaluated'}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Actions & Resumption Control */}
          <div className="p-4 bg-slate-800/80 rounded-lg border border-cyan-500/30 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={forceCpu}
                  onChange={(e) => setForceCpu(e.target.checked)}
                  className="rounded border-slate-700 text-cyan-500 focus:ring-cyan-500"
                />
                Force PyTorch CPU Mode (SadTalker Fallback)
              </label>
            </div>
            <button
              onClick={handleResume}
              disabled={resuming || runStatus.checkpoint.execution_lock}
              className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg transition shadow-lg disabled:opacity-50"
            >
              {resuming ? "Resuming Pipeline..." : `🔄 Resume Pipeline from '${runStatus.earliest_recovery_stage}'`}
            </button>
          </div>

          {/* Live Telemetry Log View */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-2">Live SSE Event Logs</h3>
            <div className="h-48 overflow-y-auto bg-black/80 rounded-lg p-3 font-mono text-xs text-slate-300 space-y-1 border border-slate-800">
              {logs.length === 0 ? (
                <span className="text-slate-600 italic">Waiting for pipeline events...</span>
              ) : (
                logs.map((log, idx) => (
                  <div key={idx} className="flex gap-2">
                    <span className="text-slate-500">[{log.timestamp?.split("T")[1]?.split(".")[0]}]</span>
                    <span className={log.level === "ERROR" ? "text-rose-400" : "text-cyan-400"}>[{log.stage}]</span>
                    <span className="text-slate-200">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
