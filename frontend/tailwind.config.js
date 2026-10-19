/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          50: "#f3f6fb",
          100: "#e4ebf5",
          200: "#c7d5e8",
          300: "#9eb5d4",
          400: "#6e8dbb",
          500: "#4c6fa3",
          600: "#3a5788",
          700: "#30466e",
          800: "#1f3355",
          900: "#0b1f3a",
          950: "#071528",
        },
        teal: {
          50: "#effcf9",
          100: "#d7f7ef",
          200: "#b0eee2",
          300: "#7adfd1",
          400: "#3fc8b8",
          500: "#1cad9f",
          600: "#0f8c82",
          700: "#0f706a",
          800: "#105a56",
          900: "#114b48",
        },
        mist: "#f6f8fb",
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "-apple-system", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(11, 31, 58, 0.04), 0 8px 24px rgba(11, 31, 58, 0.04)",
        pop: "0 12px 40px rgba(11, 31, 58, 0.16)",
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
