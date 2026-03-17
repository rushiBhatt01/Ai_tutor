"use client";

import SectionShell from "./SectionShell";
import { features } from "./landingContent";

function FeatureCard({ feature, index }) {
  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty(
      "--mouse-x",
      `${e.clientX - rect.left}px`
    );
    e.currentTarget.style.setProperty(
      "--mouse-y",
      `${e.clientY - rect.top}px`
    );
  };

  return (
    <article
      className="feature-card glass-panel rounded-[1.75rem] p-7"
      data-reveal
      onMouseMove={handleMouseMove}
    >
      <div className="feature-card-glow" />
      <div className="relative z-10">
        <p className="display-font text-sm text-cyan-200/80">
          {String(index + 1).padStart(2, "0")}
        </p>
        <h3 className="mt-5 text-2xl font-semibold text-white">
          {feature.title}
        </h3>
        <p className="section-copy mt-4">{feature.text}</p>
      </div>
    </article>
  );
}

export default function FeaturesSection() {
  return (
    <SectionShell
      id="features"
      eyebrow="Core Capabilities"
      title="Every stage of video creation — automated, intelligent, and API-driven."
      description="From script generation to final render, each capability is built as a modular, scalable service that works independently or as part of the full pipeline."
      align="center"
    >
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {features.map((feature, index) => (
          <FeatureCard key={feature.title} feature={feature} index={index} />
        ))}
      </div>
    </SectionShell>
  );
}
