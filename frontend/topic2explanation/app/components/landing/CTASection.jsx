import Link from "next/link";

export default function CTASection() {
  return (
    <section id="cta" className="px-6 pb-24 pt-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div
          className="glass-panel relative overflow-hidden rounded-[2.2rem] px-6 py-14 text-center sm:px-10 sm:py-16"
          data-reveal
        >
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/80 to-transparent" />
          <div className="absolute left-1/2 top-1/2 h-48 w-48 -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-400/10 blur-3xl" />

          <span className="eyebrow">Get Started</span>
          <h2 className="display-font mx-auto mt-8 max-w-4xl text-4xl font-semibold leading-tight text-white sm:text-5xl lg:text-6xl">
            Your next tutorial video is one prompt away.
          </h2>
          <p className="section-copy mx-auto mt-6 max-w-2xl">
            Enter a topic, choose your audience, and let the AI handle script
            writing, narration, visuals, and character animation. Your finished
            video is ready in minutes.
          </p>

          <div className="mt-10 flex flex-col justify-center gap-4 sm:flex-row">
            <Link
              href="/studio"
              className="neon-button rounded-full px-8 py-4 text-base font-semibold text-slate-950"
            >
              Generate your first video
            </Link>
            <a
              href="#features"
              className="secondary-button rounded-full px-8 py-4 text-base font-semibold text-white"
            >
              Explore capabilities
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
