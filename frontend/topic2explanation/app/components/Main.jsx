// main.jsx
"use client";
import React from "react";
import { useState, useEffect } from "react";
import Box1 from "./box1";
import Box2 from "./box2";
import VideoHistory from "./VideoHistory";
import { generateOutput } from "./generateoutput";
import { DEMO_TOPICS } from "../utils/demoTopics";

import PipelineRecovery from "./PipelineRecovery";
import DevModuleConsole from "./DevModuleConsole";

export default function Main() {
  const [activeTab, setActiveTab] = useState("studio"); // "studio" | "recovery" | "sandbox"
  const [message, setMessage] = useState("");
  const [level, setLevel] = useState("beginner");
  const [age, setAge] = useState(18);
  const [creative, setCreative] = useState(8);
  const [humour, setHumour] = useState(6);
  const [characterName, setCharacterName] = useState("Benjamin");
  const [enableSubtitles, setEnableSubtitles] = useState(false);
  const [loading, setLoading] = useState(false);
  const [videoUrl, setVideoUrl] = useState("");

  useEffect(() => {
    if (loading) {
      try {
        generateOutput(
          message,
          level,
          age,
          creative,
          humour,
          characterName,
          setLoading,
          setVideoUrl,
          enableSubtitles
        );
      } catch (error) {
        console.error("Error in generateOutput:", error);
        setLoading(false);
      }
    }
  }, [age, characterName, creative, enableSubtitles, humour, level, loading, message]);

  // Show info tooltip on page load
  useEffect(() => {
    const timer = setTimeout(() => {
      const infoIcon = document.querySelector('.studio-main-backend-status-icon');
      if (infoIcon) {
        infoIcon.setAttribute('data-show-tooltip', 'true');
        setTimeout(() => {
          infoIcon.removeAttribute('data-show-tooltip');
        }, 8000);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  const handleHistorySelect = (url) => {
    setVideoUrl(url);
  };

  const handleQuickDemo = (e) => {
    console.log("Quick Demo clicked");
    e.preventDefault();
    e.stopPropagation();
    if (!DEMO_TOPICS || DEMO_TOPICS.length === 0) {
      console.error("No demo topics available");
      return;
    }
    const randomTopic = DEMO_TOPICS[Math.floor(Math.random() * DEMO_TOPICS.length)];
    console.log("Selected random topic:", randomTopic);
    if (randomTopic && randomTopic.trim()) {
      setMessage(randomTopic);
      setLoading(true);
      console.log("Loading set to true, message set to:", randomTopic);
    }
  };

  return (
    <div className="space-y-6">
      {/* View Switcher Navigation Bar */}
      <div className="flex justify-center gap-3 px-4">
        <button
          onClick={() => setActiveTab("studio")}
          className={`px-5 py-2.5 rounded-full font-semibold text-sm transition ${
            activeTab === "studio"
              ? "bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/25"
              : "bg-slate-800/80 text-slate-300 hover:text-white"
          }`}
        >
          🎨 Studio Workspace
        </button>
        <button
          onClick={() => setActiveTab("recovery")}
          className={`px-5 py-2.5 rounded-full font-semibold text-sm transition ${
            activeTab === "recovery"
              ? "bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/25"
              : "bg-slate-800/80 text-slate-300 hover:text-white"
          }`}
        >
          ⚡ Pipeline Recovery
        </button>
        <button
          onClick={() => setActiveTab("sandbox")}
          className={`px-5 py-2.5 rounded-full font-semibold text-sm transition ${
            activeTab === "sandbox"
              ? "bg-emerald-500 text-slate-950 shadow-lg shadow-emerald-500/25"
              : "bg-slate-800/80 text-slate-300 hover:text-white"
          }`}
        >
          🛠️ Dev Module Sandbox
        </button>
      </div>

      {activeTab === "recovery" && <PipelineRecovery />}
      {activeTab === "sandbox" && <DevModuleConsole />}

      {activeTab === "studio" && (
        <div className="studio-layout">
      <div className="studio-main">
        <div className="studio-input-header">
          <Box1
            message={message}
            setMessage={setMessage}
            level={level}
            age={age}
            creative={creative}
            humour={humour}
            characterName={characterName}
            loading={loading}
            setLoading={setLoading}
            videoUrl={videoUrl}
          />
          <div className="studio-main-backend-status-icon" title="Backend service is currently offline (requires higher system specs). Only demo videos available." data-tooltip-hint="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4" />
              <path d="M12 8h.01" />
            </svg>
            <span className="studio-main-backend-tooltip">
              <div className="studio-tooltip-content">
                <p>Backend service is currently offline (requires higher system specs) So New Generation won&apos;t be working. Only demo Generated videos available.</p>
                <button type="button" className="studio-quick-demo-btn" onClick={handleQuickDemo}>
                  🎲 Quick Demo
                </button>
              </div>
            </span>
          </div>
        </div>
        <VideoHistory
          currentVideoUrl={videoUrl}
          currentTopic={message}
          onSelect={handleHistorySelect}
        />
      </div>
      <aside className="studio-sidebar">
        <Box2
          level={level}
          setLevel={setLevel}
          age={age}
          setAge={setAge}
          creative={creative}
          setCreative={setCreative}
          humour={humour}
          setHumour={setHumour}
          characterName={characterName}
          setCharacterName={setCharacterName}
          enableSubtitles={enableSubtitles}
          setEnableSubtitles={setEnableSubtitles}
        />
      </aside>
    </div>
      )}
    </div>
  );
}
