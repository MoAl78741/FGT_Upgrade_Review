/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Outfit", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        brand: {
          500: "rgb(var(--accent) / <alpha-value>)",
          600: "rgb(var(--accent-dark) / <alpha-value>)",
        },
        navy: {
          700: "rgb(var(--surface-border) / <alpha-value>)",
          800: "rgb(var(--surface) / <alpha-value>)",
          900: "rgb(var(--surface-deep) / <alpha-value>)",
        },
      },
    },
  },
  plugins: [],
};
