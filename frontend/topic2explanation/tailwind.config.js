/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    // Note: pages/ dir doesn't exist in this App Router project — removed to
    // avoid wasting time scanning a non-existent directory on every CSS rebuild.
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic':
          'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [],
}
