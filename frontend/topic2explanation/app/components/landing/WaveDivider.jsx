export default function WaveDivider({ flip = false }) {
  return (
    <div
      className={`wave-divider ${flip ? "wave-divider-flip" : ""}`}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 1440 80"
        preserveAspectRatio="none"
        className="wave-divider-svg"
      >
        <defs>
          <linearGradient id="waveGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgba(110, 242, 255, 0.12)" />
            <stop offset="50%" stopColor="rgba(128, 88, 255, 0.10)" />
            <stop offset="100%" stopColor="rgba(110, 242, 255, 0.08)" />
          </linearGradient>
        </defs>
        <path
          d="M0,40 C360,80 720,0 1080,40 C1260,60 1380,20 1440,40 L1440,80 L0,80 Z"
          fill="url(#waveGrad)"
          className="wave-path-1"
        />
        <path
          d="M0,50 C240,20 480,70 720,40 C960,10 1200,60 1440,30 L1440,80 L0,80 Z"
          fill="rgba(110, 242, 255, 0.04)"
          className="wave-path-2"
        />
      </svg>
    </div>
  );
}
