"use client";

import { useEffect, useRef } from "react";

const PIPELINE_NODES = [
  { label: "Topic", icon: "💬" },
  { label: "Script", icon: "📝" },
  { label: "Voice", icon: "🎙️" },
  { label: "Visuals", icon: "🖼️" },
  { label: "Video", icon: "🎬" },
];

export default function PipelineFlowchart() {
  const containerRef = useRef(null);

  useEffect(() => {
    if (typeof window === "undefined" || !containerRef.current) return;

    const nodes = containerRef.current.querySelectorAll(".pipeline-flow-node");
    const connectors = containerRef.current.querySelectorAll(
      ".pipeline-flow-connector"
    );

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            // Stagger the node activations
            nodes.forEach((node, i) => {
              setTimeout(() => {
                node.classList.add("active");
              }, i * 400);
            });
            connectors.forEach((conn, i) => {
              setTimeout(() => {
                conn.classList.add("active");
              }, i * 400 + 200);
            });
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.4 }
    );

    observer.observe(containerRef.current);

    return () => observer.disconnect();
  }, []);

  return (
    <div className="pipeline-flowchart" ref={containerRef}>
      {PIPELINE_NODES.map((node, i) => (
        <div key={node.label} className="pipeline-flow-step">
          <div className="pipeline-flow-node">
            <div className="pipeline-flow-ring" />
            <span className="pipeline-flow-icon">{node.icon}</span>
            <div className="pipeline-flow-pulse" />
          </div>
          <span className="pipeline-flow-label">{node.label}</span>
          {i < PIPELINE_NODES.length - 1 && (
            <div className="pipeline-flow-connector">
              <div className="pipeline-flow-connector-fill" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
