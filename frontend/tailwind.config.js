/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Sidebar brand: deep navy-slate
        brand: {
          50:  '#f0f4ff',
          100: '#dce4f5',
          300: '#93aad4',
          500: '#4a6fa5',
          600: '#35548a',
          700: '#243d6b',
          800: '#172d52',
          900: '#0f1e38',
        },
        gray: {
          950: '#060b12',
        },
      },
      fontFamily: {
        sans: ['IBM Plex Sans', 'DM Sans', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'JetBrains Mono', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
