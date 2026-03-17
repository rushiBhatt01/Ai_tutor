"use client";

import { useRef } from "react";
import HumanoidModelCanvas from "./HumanoidModelCanvas";

const glowNodes = [
  {
    style: { top: "14%", left: "8%", "--orb-size": "14px" },
  },
  {
    style: { top: "26%", right: "11%", "--orb-size": "9px" },
  },
  {
    style: { bottom: "18%", left: "10%", "--orb-size": "12px" },
  },
  {
    style: { bottom: "22%", right: "9%", "--orb-size": "10px" },
  },
];

export default function CharacterShowcase({ compact = false }) {
  const stageRef = useRef(null);

  const handleMove = (event) => {
    if (!stageRef.current || window.matchMedia("(pointer: coarse)").matches) {
      return;
    }

    const bounds = stageRef.current.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width;
    const y = (event.clientY - bounds.top) / bounds.height;
    const rotateY = (x - 0.5) * 14;
    const rotateX = (0.5 - y) * 10;

    stageRef.current.style.setProperty("--rotate-x", `${rotateX}deg`);
    stageRef.current.style.setProperty("--rotate-y", `${rotateY}deg`);
    stageRef.current.style.setProperty("--spot-x", `${x * 100}%`);
    stageRef.current.style.setProperty("--spot-y", `${y * 100}%`);
  };

  const handleLeave = () => {
    if (!stageRef.current) {
      return;
    }

    stageRef.current.style.setProperty("--rotate-x", "0deg");
    stageRef.current.style.setProperty("--rotate-y", "0deg");
    stageRef.current.style.setProperty("--spot-x", "50%");
    stageRef.current.style.setProperty("--spot-y", "28%");
  };

  return (
    <div
      className={`character-scene ${compact ? "character-scene-compact" : ""}`}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
    >
      <div className="character-aura character-aura-left" />
      <div className="character-aura character-aura-right" />

      <div
        ref={stageRef}
        className={`character-stage ${compact ? "character-stage-compact" : ""}`}
      >
        <div className="character-ring character-ring-one" data-character-ring />
        <div className="character-ring character-ring-two" data-character-ring />

        <div className="character-stage-inner glass-panel">
          <div className="character-grid" />
          <div className="character-spotlight" />
          <div className="character-model-wrap">
            <HumanoidModelCanvas compact={compact} />
          </div>
        </div>

        {glowNodes.map((node, index) => (
          <span
            key={index}
            className="character-orb"
            style={node.style}
            data-float-chip
            data-chip-index={index}
          />
        ))}
      </div>
    </div>
  );
}
