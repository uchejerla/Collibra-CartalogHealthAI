/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./src/**/*.{ts,tsx,js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#eeecfb",
          100: "#d6d2f6",
          200: "#ada5ed",
          300: "#8479e4",
          400: "#5b4cdb",
          500: "#3c3489",   // primary brand purple
          600: "#312b72",
          700: "#26225b",
          800: "#1b1844",
          900: "#10102d",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [
    require("@tailwindcss/typography"),
  ],
}
