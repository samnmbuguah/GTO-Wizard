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
          canvas: '#00140f',
          dark: '#00140f',
          surface: '#182628',
          card: '#182628',
          subsurface: '#2d393b',
          accent: '#7aa6da',
          teal: '#64ffda',
          border: 'rgba(204, 219, 220, 0.18)',
          red: '#f43f5e',
          green: '#10b981',
          blue: '#457B9D',
          gray: '#2d393b',
          light: '#ccdbdc',
          muted: '#8b9ea0',
        },
        background: 'var(--background)',
        card: 'var(--card)',
        muted: 'var(--muted)',
        border: 'var(--border)',
      },
      backgroundImage: {
        'glass': 'linear-gradient(135deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.02))',
      }
    },
  },
  plugins: [],
}
