"use client";

import Link from "next/link";
import { useRef } from "react";
import TechBadges from "./TechBadges";
import TypingEffect from "./TypingEffect";

export default function HeroSection() {
  const cardRef = useRef(null);

  const handleMove = (e) => {
    if (!cardRef.current || window.matchMedia("(pointer: coarse)").matches)
      return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    cardRef.current.style.setProperty("--rx", `${(0.5 - y) * 16}deg`);
    cardRef.current.style.setProperty("--ry", `${(x - 0.5) * 16}deg`);
    cardRef.current.style.setProperty("--glow-x", `${x * 100}%`);
    cardRef.current.style.setProperty("--glow-y", `${y * 100}%`);
  };

  const handleLeave = () => {
    if (!cardRef.current) return;
    cardRef.current.style.setProperty("--rx", "0deg");
    cardRef.current.style.setProperty("--ry", "0deg");
    cardRef.current.style.setProperty("--glow-x", "50%");
    cardRef.current.style.setProperty("--glow-y", "40%");
  };

  return (
    <section className="relative overflow-hidden px-6 pb-24 pt-36 sm:pt-40 lg:px-8">
      <TechBadges />
      <div className="mx-auto grid min-h-[88vh] max-w-7xl items-center gap-16 lg:grid-cols-[1.02fr_0.98fr]">
        <div className="relative z-10" data-hero-copy>
          <span className="eyebrow">AI Video Tutorial Generator</span>
          <h1 className="display-font mt-8 max-w-4xl text-5xl font-semibold leading-[0.95] sm:text-6xl lg:text-7xl">
            Turn any topic into a{" "}
            <TypingEffect />
            {" "}with a realistic AI instructor.
          </h1>

          <div className="mt-12 flex flex-col gap-4 sm:flex-row">
            <Link
              href="/studio"
              className="neon-button rounded-full px-7 py-4 text-center text-base font-semibold text-slate-950"
            >
              Start generating
            </Link>
            <a
              href="#story"
              className="secondary-button rounded-full px-7 py-4 text-center text-base font-semibold text-white"
            >
              See how it works
            </a>
          </div>
        </div>

        <div className="relative z-10" data-hero-orb data-float>
          <div
            ref={cardRef}
            className="hero-character-card"
            onMouseMove={handleMove}
            onMouseLeave={handleLeave}
          >
            <div className="hero-character-glow" />
            <img
              src="/images/benjamin-character.png"
              alt="Benjamin – AI instructor character"
              className="hero-character-img"
              draggable={false}
            />
            <div className="hero-character-shine" />
          </div>
        </div>
      </div>
    </section>
  );
}

