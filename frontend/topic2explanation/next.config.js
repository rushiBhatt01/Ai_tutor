/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",         // ✅ Enables static export
  images: {
    unoptimized: true,      // ✅ Ensures images are compatible with static export
  },

  // ─── Compile-time optimisations ───────────────────────────────────
  swcMinify: true,          // Use Rust-based SWC minifier instead of slower Terser

  experimental: {
    // Re-write barrel imports to direct file imports so the bundler
    // only parses what is actually used – dramatically cuts incremental
    // compile time for Three.js, R3F, GSAP, and Lenis.
    optimizePackageImports: [
      "three",
      "@react-three/fiber",
      "@react-three/drei",
      "gsap",
      "lenis",
    ],
  },
};

module.exports = nextConfig;