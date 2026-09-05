"use client";
import React from "react";
import { useState, useRef, useEffect } from "react";

const LEVELS = ["beginner", "intermediate", "advanced"];
const CHARACTERS = [
  { name: "Benjamin", image: "/images/benjamin-character.png" },
  { name: "Sophia", image: "/images/sophia-character.png" },
];

/* ── Accordion section ──────────────────────────────────── */
function AccordionSection({ title, icon, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  const contentRef = useRef(null);
  const [height, setHeight] = useState("auto");
  const [isAnimating, setIsAnimating] = useState(false);

  const toggle = () => {
    setIsAnimating(true);
    setOpen(!open);
  };

  useEffect(() => {
    if (contentRef.current) {
      setHeight(open ? `${contentRef.current.scrollHeight}px` : "0px");
    }
  }, [open]);

  // Re-measure on content change
  useEffect(() => {
    if (open && contentRef.current && !isAnimating) {
      setHeight(`${contentRef.current.scrollHeight}px`);
    }
  }, [open, isAnimating]);

  return (
    <div className={`accordion-section ${open ? "open" : ""}`}>
      <button
        className="accordion-header"
        onClick={toggle}
        type="button"
      >
        <span className="accordion-header-left">
          <span className="accordion-icon">{icon}</span>
          <span className="accordion-title">{title}</span>
        </span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`accordion-chevron ${open ? "open" : ""}`}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      <div
        className="accordion-content"
        ref={contentRef}
        style={{
          maxHeight: height,
          overflow: open && !isAnimating ? "visible" : "hidden"
        }}
        onTransitionEnd={() => setIsAnimating(false)}
      >
        <div className="accordion-content-inner">{children}</div>
      </div>
    </div>
  );
}

/* ── Custom select ──────────────────────────────────────── */
function StudioSelect({ label, icon, value, options, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className="studio-control-group" ref={ref}>
      <label className="studio-control-label">
        <span>{icon}</span>
        <span>{label}</span>
      </label>
      <button
        className="studio-select"
        onClick={() => setOpen(!open)}
        type="button"
      >
        <span className="studio-select-value">{value}</span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`studio-select-chevron ${open ? "open" : ""}`}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="studio-dropdown">
          {options.map((opt) => (
            <button
              key={opt}
              className={`studio-dropdown-item ${opt === value ? "active" : ""}`}
              onClick={() => {
                onChange(opt);
                setOpen(false);
              }}
            >
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Custom slider ──────────────────────────────────────── */
function StudioSlider({ label, icon, value, min, max, onChange }) {
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div className="studio-control-group">
      <label className="studio-control-label">
        <span>{icon}</span>
        <span>{label}</span>
        <span className="studio-slider-value">{value}</span>
      </label>
      <div className="studio-slider-wrap">
        <input
          type="range"
          className="studio-slider"
          min={min}
          max={max}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          style={{ "--slider-pct": `${pct}%` }}
        />
      </div>
    </div>
  );
}

/* ── Custom toggle switch ────────────────────────────────── */
function StudioToggle({ label, icon, checked, onChange }) {
  return (
    <div className="studio-control-group flex items-center justify-between py-1">
      <label className="studio-control-label flex items-center gap-2 cursor-pointer">
        <span>{icon}</span>
        <span>{label}</span>
      </label>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
          checked ? "bg-cyan-500" : "bg-gray-700"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}

/* ── Character preview ──────────────────────────────────── */
function CharacterPreview({ characterName }) {
  const character = CHARACTERS.find((c) => c.name === characterName) || CHARACTERS[0];

  return (
    <div className="studio-character-preview">
      <div className="studio-character-preview-img-wrap">
        <img
          src={character.image}
          alt={character.name}
          className="studio-character-preview-img"
          draggable={false}
        />
        <div className="studio-character-preview-glow" />
      </div>
      <div className="studio-character-preview-info">
        <span className="studio-character-preview-name">{character.name}</span>
        <span className="studio-character-preview-role">AI Instructor</span>
      </div>
    </div>
  );
}

/* ── Main box2 ──────────────────────────────────────────── */
export default function Box2(props) {
  return (
    <div className="studio-controls glass-panel rounded-[1.75rem]">
      <div className="studio-controls-header">
        <h2 className="display-font text-sm uppercase tracking-[0.28em] text-cyan-200/80">
          Control Panel
        </h2>
      </div>

      <div className="studio-controls-body">
        {/* Character section */}
        <AccordionSection title="Instructor" icon="🎭" defaultOpen={true}>
          <CharacterPreview characterName={props.characterName} />
          <StudioSelect
            label="Character"
            icon="🎭"
            value={props.characterName}
            options={CHARACTERS.map((c) => c.name)}
            onChange={props.setCharacterName}
          />
        </AccordionSection>

        {/* Content section */}
        <AccordionSection title="Content" icon="📚" defaultOpen={true}>
          <StudioSelect
            label="Level"
            icon="🎓"
            value={props.level}
            options={LEVELS}
            onChange={props.setLevel}
          />
          <StudioToggle
            label="Subtitles Overlay"
            icon="💬"
            checked={Boolean(props.enableSubtitles)}
            onChange={props.setEnableSubtitles || (() => {})}
          />
        </AccordionSection>

        {/* Style section */}
        <AccordionSection title="Style" icon="🎨" defaultOpen={true}>
          <StudioSlider
            label="Creativity"
            icon="✨"
            value={props.creative}
            min={1}
            max={10}
            onChange={props.setCreative}
          />
          <StudioSlider
            label="Humour"
            icon="😄"
            value={props.humour}
            min={1}
            max={10}
            onChange={props.setHumour}
          />
          <StudioSlider
            label="Target Age"
            icon="👤"
            value={props.age}
            min={1}
            max={100}
            onChange={props.setAge}
          />
        </AccordionSection>
      </div>
    </div>
  );
}