"use client";

import SectionShell from "./SectionShell";
import { metrics, proofCards } from "./landingContent";

function SlotDigit({ digit, delay }) {
  return (
    <span
      className="slot-digit-col"
      style={{ "--target-digit": digit, "--slot-delay": `${delay}s` }}
      data-slot-digit
    >
      <span className="slot-digit-strip">
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
          <span key={n} className="slot-digit-num">
            {n}
          </span>
        ))}
      </span>
    </span>
  );
}

function SlotCounter({ value, suffix }) {
  const digits = String(value).split("");

  return (
    <span className="slot-counter" data-slot-counter>
      {digits.map((d, i) => (
        <SlotDigit key={i} digit={Number(d)} delay={i * 0.15} />
      ))}
      <span className="slot-suffix">{suffix}</span>
    </span>
  );
}

export default function ProofSection() {
  return (
    <SectionShell
      id="proof"
      eyebrow="Impact & Use Cases"
      title="Built for educators, developers, and teams who need tutorial content at scale."
      description="Whether you're onboarding employees, teaching students, or documenting APIs — the generator delivers consistent, high-quality video tutorials on demand."
    >
      <div className="grid gap-10 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
          {metrics.map((metric) => (
            <article
              key={metric.label}
              className="glass-panel rounded-[1.75rem] p-6"
              data-reveal
            >
              <p className="display-font text-4xl font-semibold text-white sm:text-5xl">
                <SlotCounter value={metric.value} suffix={metric.suffix} />
              </p>
              <p className="mt-3 text-base text-white/90">{metric.label}</p>
            </article>
          ))}
        </div>

        <div className="grid gap-5">
          {proofCards.map((card) => (
            <article
              key={card.label}
              className="glass-panel rounded-[1.9rem] p-7"
              data-reveal
            >
              <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/80">
                {card.label}
              </p>
              <p className="mt-5 text-2xl font-medium leading-relaxed text-white">
                {card.quote}
              </p>
              <p className="mt-6 text-sm text-slate-300">{card.author}</p>
            </article>
          ))}
        </div>
      </div>
    </SectionShell>
  );
}
