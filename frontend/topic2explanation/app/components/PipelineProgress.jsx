"use client";

import { useEffect, useState } from "react";

export const PIPELINE_STEPS = [
  { id: "script", label: "Generating script", icon: "📜", duration: 1000 },
  { id: "voice", label: "Synthesizing voice", icon: "🎙️", duration: 4000 },
  { id: "visuals", label: "Fetching visuals", icon: "🖼️", duration: 2000 },
  { id: "animation", label: "Animating instructor", icon: "🎭", duration: 2000 },
  { id: "render", label: "Composing final video", icon: "🎬", duration: 1000 },
];

export default function PipelineProgress({ active }) {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    if (!active) {
      setCurrentStep(0);
      return;
    }

    let step = 0;
    setCurrentStep(0);

    const advance = () => {
      step += 1;
      if (step < PIPELINE_STEPS.length) {
        setCurrentStep(step);
        timer = setTimeout(advance, PIPELINE_STEPS[step].duration);
      }
    };

    let timer = setTimeout(advance, PIPELINE_STEPS[0].duration);

    return () => clearTimeout(timer);
  }, [active]);

  if (!active) return null;

  return (
    <div className="pipeline-progress">
      <div className="pipeline-track">
        {PIPELINE_STEPS.map((step, i) => {
          const status =
            i < currentStep ? "done" : i === currentStep ? "active" : "pending";

          return (
            <div key={step.id} className={`pipeline-node ${status}`}>
              <div className="pipeline-dot">
                {status === "done" ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : status === "active" ? (
                  <div className="pipeline-pulse" />
                ) : null}
              </div>
              {i < PIPELINE_STEPS.length - 1 && (
                <div className={`pipeline-connector ${i < currentStep ? "filled" : ""}`} />
              )}
              <span className="pipeline-label">{step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
