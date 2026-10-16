/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#070b16",
          900: "#0b1224",
          800: "#121a31",
          700: "#1a2545",
        },
        accent: {
          blue: "#3b82f6",
          violet: "#8b5cf6",
          cyan: "#22d3ee",
          green: "#22c55e",
          amber: "#f59e0b",
          red: "#ef4444",
        },
      },
      fontFamily: {
        sans: ["\"IBM Plex Sans\"", "Segoe UI", "sans-serif"],
        display: ["\"Space Grotesk\"", "Segoe UI", "sans-serif"],
        mono: ["\"IBM Plex Mono\"", "Consolas", "monospace"],
      },
      boxShadow: {
        glow: "0 0 24px rgba(59, 130, 246, 0.35)",
        "glow-green": "0 0 24px rgba(34, 197, 94, 0.35)",
        "glow-violet": "0 0 24px rgba(139, 92, 246, 0.4)",
      },
    },
  },
  plugins: [],
};
