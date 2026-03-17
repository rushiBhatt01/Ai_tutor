"use client";

import AIVisualizationSection from "./AIVisualizationSection";
// Eager import required: useLandingMotion's GSAP ScrollTrigger looks for
// [data-bg-model] on mount — dynamic/lazy loading causes it to miss the element.
import BackgroundModel from "./BackgroundModel";
import CTASection from "./CTASection";
import FeaturesSection from "./FeaturesSection";
import FloatingParticles from "./FloatingParticles";
import GlowCursor from "./GlowCursor";
import HeroSection from "./HeroSection";
import Navigation from "./Navigation";
import ProofSection from "./ProofSection";
import ScrollProgress from "./ScrollProgress";
import ScrollStorySection from "./ScrollStorySection";
import WaveDivider from "./WaveDivider";
import useLandingMotion from "./useLandingMotion";

export default function LandingPage() {
  useLandingMotion();

  return (
    <div className="landing-shell">
      <ScrollProgress />
      <BackgroundModel />
      <FloatingParticles />
      <GlowCursor />
      <div className="relative z-10">
        <Navigation />
        <main>
          <HeroSection />
          <WaveDivider />
          <ScrollStorySection />
          <WaveDivider flip />
          <FeaturesSection />
          <WaveDivider />
          <AIVisualizationSection />
          <WaveDivider flip />
          <ProofSection />
          <WaveDivider />
          <CTASection />
        </main>
      </div>
    </div>
  );
}
