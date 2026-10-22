/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Deep Ink. Navigation, headings and high-priority text.
        navy: {
          50: "#f2f6f8",
          100: "#e2ebf0",
          200: "#c3d4dd",
          300: "#97b2c0",
          400: "#648a9c",
          500: "#45697c",
          600: "#33505f",
          700: "#1b3a48",
          800: "#162e3a",
          900: "#122a36",
          950: "#0c1c25",
        },
        // Jade. Primary actions, selected states, meaningful progress.
        teal: {
          50: "#effaf7",
          100: "#d6f2eb",
          200: "#ade4d8",
          300: "#74cebc",
          400: "#3fb19b",
          500: "#159181",
          600: "#087f70",
          700: "#0a6459",
          800: "#0c4f47",
          900: "#0b413b",
        },
        // Cobalt. Links, source navigation, evidence references.
        sky: {
          50: "#eff5fc",
          100: "#dbe8f9",
          200: "#bcd5f2",
          300: "#8eb8e8",
          400: "#5b95d9",
          500: "#3879c4",
          600: "#2878c8",
          700: "#215fa3",
          800: "#1f4f85",
          900: "#1e436e",
        },
        cobalt: {
          50: "#eff5fc",
          100: "#dbe8f9",
          200: "#bcd5f2",
          300: "#8eb8e8",
          400: "#5b95d9",
          500: "#3879c4",
          600: "#2878c8",
          700: "#215fa3",
          800: "#1f4f85",
          900: "#1e436e",
        },
        // Soft Canvas. The application background.
        mist: "#f5f7f4",
        // Mint. Verified evidence surfaces, only when justified.
        emerald: {
          50: "#f4fbf7",
          100: "#ddf3e8",
          200: "#b8e6d1",
          300: "#84d2b0",
          400: "#4fb88d",
          500: "#2e9b72",
          600: "#1f7e5c",
          700: "#1a644b",
          800: "#174f3d",
          900: "#144033",
        },
        // Amber. Warnings, attention, review-needed states.
        amber: {
          50: "#fdf6ec",
          100: "#f9e9d1",
          200: "#f2d0a4",
          300: "#e9b377",
          400: "#e09b55",
          500: "#d18b43",
          600: "#b4702f",
          700: "#8e5624",
          800: "#74451f",
          900: "#60391c",
        },
        // Red. Actual failures, errors and blockers.
        red: {
          50: "#fef3f2",
          100: "#fee4e2",
          200: "#fecdca",
          300: "#fda29b",
          400: "#f97066",
          500: "#f04438",
          600: "#d92d20",
          700: "#b42318",
          800: "#912018",
          900: "#7a271a",
        },
        // Neutral reading surfaces.
        stone: {
          50: "#fafaf9",
          100: "#f5f5f4",
          200: "#e7e5e4",
          300: "#d6d3d1",
          400: "#a8a29e",
          500: "#78716c",
          600: "#57534e",
          700: "#44403c",
          800: "#292524",
          900: "#1c1917",
        },
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "-apple-system", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      borderRadius: {
        xs: "0.25rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(18, 42, 54, 0.04), 0 8px 24px rgba(18, 42, 54, 0.05)",
        pop: "0 16px 48px rgba(18, 42, 54, 0.18)",
        dock: "-12px 0 40px rgba(18, 42, 54, 0.10)",
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
        "dock-in": {
          from: { opacity: "0", transform: "translateX(16px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        "dock-in-mobile": {
          from: { opacity: "0", transform: "translateY(24px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "highlight-in": {
          from: { opacity: "0.4", transform: "translateY(2px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(8, 127, 112, 0.35)" },
          "70%": { boxShadow: "0 0 0 8px rgba(8, 127, 112, 0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(8, 127, 112, 0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 180ms ease-out",
        "slide-up": "slide-up 220ms ease-out",
        "dock-in": "dock-in 220ms cubic-bezier(0.22, 1, 0.36, 1)",
        "dock-in-mobile": "dock-in-mobile 220ms cubic-bezier(0.22, 1, 0.36, 1)",
        "highlight-in": "highlight-in 240ms ease-out",
        "pulse-ring": "pulse-ring 1.6s ease-out 2",
      },
      transitionTimingFunction: {
        calm: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};
