/** Tailwind config for DashboardMcLaren (merge into your app's config). */
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./ui/react/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Orbitron", "ui-sans-serif", "system-ui", "sans-serif"],
        body: ["Rajdhani", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        ice: "#eafcff",
        neon: "#38f8ff",
      },
    },
  },
  plugins: [],
};
