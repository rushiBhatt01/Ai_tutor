"use client";
import React, { useState, useEffect, useRef } from "react";

const STORAGE_KEY = "studio-video-history";
const MAX_HISTORY = 10;

function getHistory() {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveHistory(items) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_HISTORY)));
  } catch {
    // localStorage full — silently fail
  }
}

export default function VideoHistory({ currentVideoUrl, currentTopic, onSelect }) {
  const [history, setHistory] = useState([]);
  const scrollRef = useRef(null);

  // Load history on mount
  useEffect(() => {
    setHistory(getHistory());
  }, []);

  // Save new video to history when currentVideoUrl changes
  useEffect(() => {
    if (!currentVideoUrl) return;

    setHistory((prev) => {
      // Don't duplicate
      if (prev.some((item) => item.url === currentVideoUrl)) return prev;

      const newItem = {
        id: Date.now().toString(),
        url: currentVideoUrl,
        topic: currentTopic || "Untitled",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      const updated = [newItem, ...prev].slice(0, MAX_HISTORY);
      saveHistory(updated);
      return updated;
    });
  }, [currentVideoUrl, currentTopic]);

  const handleClear = () => {
    setHistory([]);
    saveHistory([]);
  };

  if (history.length === 0) return null;

  return (
    <div className="video-history">
      <div className="video-history-header">
        <span className="video-history-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          Recent Generations
        </span>
        <button className="video-history-clear" onClick={handleClear} title="Clear history">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
          Clear
        </button>
      </div>
      <div className="video-history-scroll" ref={scrollRef}>
        {history.map((item) => (
          <button
            key={item.id}
            className={`video-history-card ${item.url === currentVideoUrl ? "active" : ""}`}
            onClick={() => onSelect(item.url)}
            title={item.topic}
          >
            <div className="video-history-thumb">
              <video src={item.url} muted preload="metadata" className="video-history-thumb-video" />
              <div className="video-history-thumb-overlay">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
              </div>
            </div>
            <div className="video-history-meta">
              <span className="video-history-topic">{item.topic}</span>
              <span className="video-history-time">{item.timestamp}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
