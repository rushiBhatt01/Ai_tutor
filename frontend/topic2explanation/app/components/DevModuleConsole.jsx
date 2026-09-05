"use client";
import React, { useState } from "react";

export default function DevModuleConsole() {
  const [activeModule, setActiveModule] = useState("script");
  const [loading, setLoading] = useState(false);
  const [output, setOutput] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  // Input states
  const [scriptInput, setScriptInput] = useState({ topic: "Quantum Computing Basics", level: "Beginner" });
  const [speechInput, setSpeechInput] = useState({ text: "Welcome to this interactive video tutorial.", character: "Benjamin" });
  const [scrapingInput, setScrapingInput] = useState({ query: "Python Code Example" });
  const [sadtalkerInput, setSadtalkerInput] = useState({ character: "Benjamin", forceCpu: false });

  const backendUrl = "http://localhost:8000";

  const runModuleTest = async (modulePath, payload) => {
    setLoading(true);
    setErrorMsg("");
    setOutput(null);
    try {
      const res = await fetch(`${backendUrl}/api/dev/modules/${modulePath}/test`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Dev-Token": "dev-secret-token"
        },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Module execution failed");
      }
      const data = await res.json();
      setOutput(data);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto bg-slate-900 text-white rounded-xl shadow-2xl space-y-6">
      <div className="flex items-center justify-between border-b border-slate-700 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-emerald-400">🛠️ Developer Module Sandbox Console</h2>
          <p className="text-sm text-slate-400">Execute, test, and debug pipeline modules in isolation using custom or sample inputs.</p>
        </div>
      </div>

      {/* Module Selector Navigation Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
        {[
          { id: "script", label: "1. Script Generator (Cohere)" },
          { id: "speech", label: "2. Speech Synthesis (Edge-TTS)" },
          { id: "scrapling", label: "3. Image Scraper (Scrapling)" },
          { id: "wav2lip", label: "4. Avatar Lip-Sync (Wav2Lip)" }
        ].map((mod) => (
          <button
            key={mod.id}
            onClick={() => { setActiveModule(mod.id); setOutput(null); setErrorMsg(""); }}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition ${
              activeModule === mod.id
                ? "bg-emerald-600 text-white shadow-lg"
                : "bg-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            {mod.label}
          </button>
        ))}
      </div>

      {/* Module Input Configuration Cards */}
      <div className="p-5 bg-slate-800/80 rounded-lg border border-slate-700 space-y-4">
        {activeModule === "script" && (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-emerald-300">Script Generation Test Config</h3>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Topic</label>
              <input
                type="text"
                value={scriptInput.topic}
                onChange={(e) => setScriptInput({ ...scriptInput, topic: e.target.value })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white"
              />
            </div>
            <button
              onClick={() => runModuleTest("script", scriptInput)}
              disabled={loading}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg text-sm transition"
            >
              {loading ? "Running LLM..." : "▶ Test Script Module"}
            </button>
          </div>
        )}

        {activeModule === "speech" && (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-emerald-300">Edge-TTS Speech Synthesis Test Config</h3>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Text Prompt</label>
              <textarea
                value={speechInput.text}
                onChange={(e) => setSpeechInput({ ...speechInput, text: e.target.value })}
                rows={2}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white"
              />
            </div>
            <button
              onClick={() => runModuleTest("speech", speechInput)}
              disabled={loading}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg text-sm transition"
            >
              {loading ? "Synthesizing Speech..." : "▶ Test Speech Module"}
            </button>
          </div>
        )}

        {activeModule === "scrapling" && (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-emerald-300">Scrapling Image Scraping Test Config</h3>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Visual Search Query</label>
              <input
                type="text"
                value={scrapingInput.query}
                onChange={(e) => setScrapingInput({ query: e.target.value })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white"
              />
            </div>
            <button
              onClick={() => runModuleTest("scrapling", scrapingInput)}
              disabled={loading}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg text-sm transition"
            >
              {loading ? "Scrapling Scraping..." : "▶ Test Scrapling Module"}
            </button>
          </div>
        )}

        {(activeModule === "wav2lip" || activeModule === "sadtalker") && (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-emerald-300">Wav2Lip Avatar Lip Sync Test Config</h3>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={sadtalkerInput.forceCpu}
                  onChange={(e) => setSadtalkerInput({ ...sadtalkerInput, forceCpu: e.target.checked })}
                  className="rounded border-slate-700 text-emerald-500 focus:ring-emerald-500"
                />
                Force PyTorch CPU Mode
              </label>
            </div>
            <button
              onClick={() => runModuleTest("wav2lip", sadtalkerInput)}
              disabled={loading}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg text-sm transition"
            >
              {loading ? "Rendering Lip Sync..." : "▶ Test Wav2Lip Module"}
            </button>
          </div>
        )}
      </div>

      {errorMsg && (
        <div className="p-4 bg-red-950 border border-red-800 rounded-lg text-red-300 text-sm">
          ⚠️ {errorMsg}
        </div>
      )}

      {/* Module Output Result Inspector */}
      {output && (
        <div className="p-4 bg-slate-800/90 rounded-lg border border-slate-700 space-y-3">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Module Execution Output</h3>
          <pre className="p-3 bg-black/70 rounded-lg text-xs font-mono text-emerald-400 overflow-x-auto max-h-60">
            {JSON.stringify(output, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
