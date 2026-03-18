/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        poker: {
          dark: '#1a2f3b',
          card: '#2c3e50',
          accent: '#1abc9c',
          red: '#e74c3c',
          green: '#2ecc71',
          blue: '#3498db',
          gray: '#34495e',
          light: '#ecf0f1',
          darkgray: '#2c3e50'
        },
        background: '#1a2f3b',
        muted: '#7f8c8d',
        border: '#34495e'
      },
      backgroundImage: {
        'glass': 'linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.05))',
      }
    },
  },
  plugins: [],
}
