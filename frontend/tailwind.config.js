/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cream: '#FAF9F6',
        charcoal: '#1A1A1A',
        'charcoal-light': '#3A3A3A',
        'charcoal-muted': '#6B6B6B',
        slate: {
          accent: '#5B7B9A',
          'accent-light': '#7A9BB5',
        },
        bronze: {
          accent: '#8B7355',
          'accent-light': '#A89070',
        },
        terminal: {
          bg: '#0D1117',
          border: '#21262D',
          cyan: '#58D5E3',
          yellow: '#E3B341',
          green: '#3FB950',
          red: '#F85149',
          muted: '#8B949E',
        },
      },
      fontFamily: {
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
    },
  },
  plugins: [],
}
