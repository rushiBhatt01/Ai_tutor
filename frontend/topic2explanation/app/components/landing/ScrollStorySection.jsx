import SectionShell from "./SectionShell";
import { storySteps } from "./landingContent";
import PipelineFlowchart from "./PipelineFlowchart";

export default function ScrollStorySection() {
  return (
    <SectionShell
      id="story"
      eyebrow="How It Works"
      title="From a single topic prompt to a finished tutorial video in minutes."
      description="The pipeline uses five orchestrated APIs: Cohere for understanding, Langchain for script refinement, Edge TTS for voice, iCrawler for visuals, and SadTalker for character animation."
    >
      <div className="grid gap-10 lg:grid-cols-[0.95fr_1.05fr] lg:items-start">
        <div className="space-y-5">
          {storySteps.map((step) => (
            <article
              key={step.step}
              className="glass-panel rounded-[1.75rem] p-6 sm:p-7"
              data-reveal
            >
              <div className="flex items-center gap-4">
                <span className="display-font text-sm text-cyan-200/80">
                  {step.step}
                </span>
                <h3 className="text-xl font-semibold text-white">{step.title}</h3>
              </div>
              <p className="section-copy mt-4">{step.text}</p>
            </article>
          ))}
        </div>

        <div className="relative" data-parallax>
          <div className="absolute -left-10 top-8 h-32 w-32 rounded-full bg-cyan-400/10 blur-3xl" />
          <div className="absolute right-0 top-40 h-36 w-36 rounded-full bg-violet-500/10 blur-3xl" />

          <div
            className="glass-panel relative overflow-hidden rounded-[2rem] p-6 sm:p-8"
            data-reveal
          >
            <div className="grid gap-5">
              <div className="glass rounded-[1.5rem] p-5">
                <div className="flex items-center justify-between text-xs uppercase tracking-[0.28em] text-slate-300">
                  <span>Topic input</span>
                  <span>Audience: Configurable</span>
                </div>
                <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4">
                  <p className="text-sm text-cyan-100">POST /api/generate</p>
                  <p className="mt-2 text-base text-white/90">
                    &quot;Explain how OAuth 2.0 authentication works, targeted at
                    beginner web developers with a friendly, approachable tone.&quot;
                  </p>
                </div>
              </div>

              {/* Animated Pipeline Flowchart */}
              <div className="glass rounded-[1.5rem] p-5">
                <div className="flex items-center justify-between text-xs uppercase tracking-[0.28em] text-slate-300 mb-4">
                  <span>AI processing</span>
                  <span>Multi-stage pipeline</span>
                </div>
                <PipelineFlowchart />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="glass rounded-[1.5rem] p-5">
                  <p className="text-xs uppercase tracking-[0.28em] text-slate-300">
                    Voice synthesis
                  </p>
                  <p className="mt-3 text-base text-white/90">
                    Edge TTS generates natural narration synced to each script segment.
                  </p>
                </div>
                <div className="glass rounded-[1.5rem] p-5">
                  <p className="text-xs uppercase tracking-[0.28em] text-slate-300">
                    Character animation
                  </p>
                  <p className="mt-3 text-base text-white/90">
                    SadTalker animates the AI instructor with lip-synced facial movements.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </SectionShell>
  );
}
