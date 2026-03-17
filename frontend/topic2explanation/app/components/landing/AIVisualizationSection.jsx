"use client";

import SectionShell from "./SectionShell";
import { agentModes } from "./landingContent";
import BeforeAfterSlider from "./BeforeAfterSlider";

export default function AIVisualizationSection() {
  return (
    <SectionShell
      id="visuals"
      eyebrow="AI Instructor"
      title="A realistic character that teaches — not just narrates."
      description="Every tutorial is presented by an animated AI instructor powered by SadTalker, giving your content a human presence that keeps learners engaged."
    >
      <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
        <div className="space-y-6">
          <div
            className="glass-panel rounded-[2rem] overflow-hidden p-1"
            data-reveal
            data-visual-panel
          >
            <div className="relative rounded-[1.75rem] overflow-hidden">
              <img
                src="/images/benjamin-character.png"
                alt="Benjamin — AI instructor character"
                className="w-full h-auto object-cover"
                style={{ filter: "saturate(1.1) contrast(1.05)" }}
              />
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background:
                    "linear-gradient(180deg, transparent 60%, rgba(4,8,22,0.8) 100%)",
                  pointerEvents: "none",
                }}
              />
            </div>
          </div>

          {/* Before/After slider */}
          <div data-reveal>
            <BeforeAfterSlider />
          </div>
        </div>

        <div className="space-y-5">
          <div className="glass-panel rounded-[1.75rem] p-7" data-reveal>
            <h3 className="text-2xl font-semibold text-white">
              Why an AI instructor matters
            </h3>
            <p className="section-copy mt-4">
              Learners retain more when taught by a recognizable face. Our AI
              instructor lip-syncs to the narration, matches the tone to the
              audience level, and brings every tutorial to life — no recording
              studio required.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
            {agentModes.map((mode) => (
              <article
                key={mode.title}
                className="feature-card glass-panel rounded-[1.5rem] p-5"
                data-reveal
              >
                <h4 className="text-lg font-semibold text-white">{mode.title}</h4>
                <p className="section-copy mt-3 text-sm">{mode.text}</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </SectionShell>
  );
}
