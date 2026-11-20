/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], serif: ['"Source Serif 4"', "Georgia", "serif"] },
      colors: {
        paper: "#FFFFFF",
        ink: "#0F172A",
        maritime: { DEFAULT: "#1D4ED8", dk: "#1E40AF" },
        terra: { DEFAULT: "#DC2626", dk: "#B91C1C" },
      },
    },
  },
  plugins: [],
};
