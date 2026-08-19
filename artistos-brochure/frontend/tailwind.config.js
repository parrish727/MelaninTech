/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#14110F", muted: "#A99C89" },
        paper: { DEFAULT: "#F3EDE0", muted: "#6B6255" },
        amber: { DEFAULT: "#E3963E" },
        red: { DEFAULT: "#D14B3E" },
        teal: { DEFAULT: "#1F4A44" },
        hair: { dark: "#332E27", light: "#DDD3C2" },
      },
      fontFamily: {
        display: ["Oswald", "sans-serif"],
        body: ["Work Sans", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
