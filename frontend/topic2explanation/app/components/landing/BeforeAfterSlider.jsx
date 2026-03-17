"use client";

import { useRef, useState, useCallback } from "react";

export default function BeforeAfterSlider() {
  const containerRef = useRef(null);
  const [position, setPosition] = useState(50);
  const isDragging = useRef(false);

  const updatePosition = useCallback((clientX) => {
    if (!containerRef.current) return;
    const bounds = containerRef.current.getBoundingClientRect();
    const x = clientX - bounds.left;
    const pct = Math.min(Math.max((x / bounds.width) * 100, 5), 95);
    setPosition(pct);
  }, []);

  const onPointerDown = (e) => {
    isDragging.current = true;
    updatePosition(e.clientX);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e) => {
    if (!isDragging.current) return;
    updatePosition(e.clientX);
  };

  const onPointerUp = () => {
    isDragging.current = false;
  };

  return (
    <div
      className="ba-slider"
      ref={containerRef}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      {/* Before side — raw text */}
      <div className="ba-before">
        <div className="ba-content ba-content-before">
          <span className="ba-label">BEFORE</span>
          <div className="ba-text-block">
            <p className="ba-raw-topic">Topic: &quot;Explain OAuth 2.0 for beginners&quot;</p>
            <div className="ba-raw-params">
              <span>Level: Beginner</span>
              <span>Creativity: 8/10</span>
              <span>Humour: 6/10</span>
            </div>
            <p className="ba-raw-note">Just a text prompt. No video, no visuals, no instructor.</p>
          </div>
        </div>
      </div>

      {/* After side — finished output */}
      <div className="ba-after" style={{ clipPath: `inset(0 0 0 ${position}%)` }}>
        <div className="ba-content ba-content-after">
          <span className="ba-label ba-label-after">AFTER</span>
          <div className="ba-result-block">
            <div className="ba-result-header">
              <span className="ba-result-badge">✅ Generated</span>
              <span className="ba-result-time">~3 min</span>
            </div>
            <div className="ba-result-preview">
              <div className="ba-result-video-placeholder">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
              </div>
              <div className="ba-result-details">
                <p>📝 Structured script with 5 chapters</p>
                <p>🎙️ Natural voice narration</p>
                <p>🖼️ Auto-retrieved visuals</p>
                <p>🎭 Lip-synced AI instructor</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Slider handle */}
      <div className="ba-handle" style={{ left: `${position}%` }}>
        <div className="ba-handle-line" />
        <div className="ba-handle-grip">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </div>
      </div>
    </div>
  );
}
