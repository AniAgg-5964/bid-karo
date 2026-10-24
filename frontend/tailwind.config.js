/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Ink and neutral surfaces. A slate-leaning navy reads cleaner on white
        // than the previous blue-grey, and keeps body copy legible at 12-13px.
        navy: {
          50: "#f7f9fc",
          100: "#eef2f7",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f2137",
          950: "#081525",
        },
        // The product accent: the green used for actions and verified states.
        teal: {
          50: "#ecfdf6",
          100: "#d1fae8",
          200: "#a7f3d3",
          300: "#6ee7b7",
          400: "#34d399",
          500: "#10b981",
          600: "#0f9d76",
          700: "#0b7f60",
          800: "#09654e",
          900: "#075241",
        },
        mist: "#f6f8fb",
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "-apple-system", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 33, 55, 0.04)",
        pop: "0 12px 40px rgba(15, 33, 55, 0.14)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(16px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 180ms ease-out",
        "slide-up": "slide-up 220ms ease-out",
      },
    },
  },
  plugins: [],
};
