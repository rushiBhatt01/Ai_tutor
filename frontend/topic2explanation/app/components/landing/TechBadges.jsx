"use client";

const techBadges = [
  { label: "Cohere", color: "#6ef2ff", delay: 0, position: { top: "12%", left: "6%" } },
  { label: "Langchain", color: "#8058ff", delay: 0.8, position: { top: "28%", right: "4%" } },
  { label: "Edge TTS", color: "#4d7cff", delay: 1.6, position: { bottom: "32%", left: "3%" } },
  { label: "SadTalker", color: "#b0a7ff", delay: 2.4, position: { bottom: "18%", right: "6%" } },
  { label: "FastAPI", color: "#6ef2ff", delay: 3.2, position: { top: "52%", left: "1%" } },
];

export default function TechBadges() {
  return (
    <div className="tech-badges-container" aria-hidden="true">
      {techBadges.map((badge, index) => (
        <span
          key={badge.label}
          className="tech-badge"
          style={{
            ...badge.position,
            "--badge-color": badge.color,
            "--badge-delay": `${badge.delay}s`,
            "--badge-index": index,
          }}
          data-float-chip
          data-chip-index={index + 10}
        >
          {badge.label}
        </span>
      ))}
    </div>
  );
}
