/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        tg: {
          bg: "var(--tg-theme-bg-color, #0D1117)",
          text: "var(--tg-theme-text-color, #E6EDF3)",
          hint: "var(--tg-theme-hint-color, #8B949E)",
          link: "var(--tg-theme-link-color, #58A6FF)",
          button: "var(--tg-theme-button-color, #238636)",
          buttonText: "var(--tg-theme-button-text-color, #FFFFFF)",
          secondary: "var(--tg-theme-secondary-bg-color, #161B22)",
        },
      },
    },
  },
  plugins: [],
}
