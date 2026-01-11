/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'jumia-orange': '#F68B1E',
        'jumia-dark': '#282828',
        'jumia-green': '#22C55E',
        'jumia-yellow': '#EAB308',
        'jumia-red': '#EF4444',
      },
      fontFamily: {
        'sans': ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
