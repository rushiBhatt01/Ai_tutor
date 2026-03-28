"use client";
import React, { useState, useCallback } from "react";
import PipelineProgress from "./PipelineProgress";

const SUGGESTIONS = [
  "Explain OAuth 2.0",
  "How does DNS work?",
  "Intro to Machine Learning",
  "What is Blockchain?",
];

export default function Box1(props) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  const handleMessageChange = (e) => {
    props.setMessage(e.target.value);
  };

  const handleClick = () => {
    if (props.message.trim()) {
      props.setLoading(true);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && props.message.trim()) {
      props.setLoading(true);
    }
  };

  const handleSuggestion = (text) => {
    props.setMessage(text);
  };

  const openFullscreen = useCallback(() => setIsFullscreen(true), []);
  const closeFullscreen = useCallback((e) => {
    if (e.target === e.currentTarget || e.key === "Escape") setIsFullscreen(false);
  }, []);

  // Close on Escape key
  React.useEffect(() => {
    if (!isFullscreen) return;
    const handler = (e) => { if (e.key === "Escape") setIsFullscreen(false); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isFullscreen]);

  return (
    <div className="studio-prompt-area">
      {/* ─── Prompt input bar ─── */}
      <div className="studio-input-bar glass-panel rounded-[1.5rem]">
        <div className="studio-input-glow" />
        <input
          className="studio-input"
          type="text"
          placeholder="Enter a topic — e.g. 'Explain OAuth 2.0 for beginners'"
          value={props.message}
          onChange={handleMessageChange}
          onKeyDown={handleKeyDown}
          disabled={props.loading}
        />
        {!props.loading ? (
          <button
            className="studio-generate-btn neon-button"
            onClick={handleClick}
            disabled={!props.message.trim()}
            aria-label="Generate video"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            <span>Generate</span>
          </button>
        ) : (
          <div className="studio-loading-indicator">
            <div className="studio-spinner" />
            <span>Creating video…</span>
          </div>
        )}
      </div>

      {/* ─── Prompt suggestions ─── */}
      {!props.loading && !props.videoUrl && !props.message && (
        <div className="studio-suggestions">
          <span className="studio-suggestions-label">Try a topic:</span>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              className="studio-suggestion-chip"
              onClick={() => handleSuggestion(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}



      {/* ─── Pipeline progress ─── */}
      <PipelineProgress active={props.loading} />

      {/* ─── Video output or empty state ─── */}
      <div className={`studio-output-area glass-panel rounded-[2rem] ${props.loading ? "studio-output-loading" : ""} ${props.videoUrl ? "studio-output-ready" : ""}`}>
        {/* Ambient glow - pulses while loading, shines when video ready */}
        <div className="studio-ambient-glow" />

        {props.videoUrl ? (
          <div className="studio-video-wrap">
            <video
              src={props.videoUrl}
              controls
              className="studio-video"
            >
              <track
                src="/captions/tutorial-en.vtt"
                kind="subtitles"
                srcLang="en"
                label="English"
                default
              />
            </video>
            <button
              className="studio-fullscreen-btn"
              onClick={openFullscreen}
              aria-label="View fullscreen"
              title="Fullscreen"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3" />
              </svg>
            </button>
          </div>
        ) : (
          <div className="studio-empty-state">
            {!props.loading && (
              <>
                <div className="studio-empty-icon">
                  <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" opacity="0.5">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                </div>
                <h3 className="display-font text-xl text-white/60 mt-4">
                  Your tutorial video will appear here
                </h3>
                <p className="text-sm text-white/30 mt-2 max-w-md text-center">
                  Enter a topic above and click Generate. The AI will create a script, synthesize narration, retrieve visuals, and animate your AI instructor.
                </p>
                <div className="studio-empty-steps">
                  <span className="studio-step-chip">
                    <span className="studio-step-dot" />
                    Topic → Script
                  </span>
                  <span className="studio-step-chip">
                    <span className="studio-step-dot" style={{ background: "#4d7cff" }} />
                    Voice synthesis
                  </span>
                  <span className="studio-step-chip">
                    <span className="studio-step-dot" style={{ background: "#8058ff" }} />
                    Character animation
                  </span>
                  <span className="studio-step-chip">
                    <span className="studio-step-dot" style={{ background: "#b0a7ff" }} />
                    Final render
                  </span>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* ─── Fullscreen overlay ─── */}
      {isFullscreen && props.videoUrl && (
        <div className="studio-fullscreen-overlay" onClick={closeFullscreen}>
          <button className="studio-fullscreen-close" onClick={() => setIsFullscreen(false)} aria-label="Close fullscreen">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
          <video
            src={props.videoUrl}
            controls
            autoPlay
            className="studio-fullscreen-video"
            onClick={(e) => e.stopPropagation()}
          >
            <track src="/captions/tutorial-en.vtt" kind="subtitles" srcLang="en" label="English" default />
          </video>
        </div>
      )}
    </div>
  );
}
