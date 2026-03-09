/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Open Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"Google Sans Code"', 'ui-monospace', 'monospace'],
        copilot: ['"Open Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        accent: '#171717',
        brand: {
          50: '#fafafa',
          100: '#f4f4f5',
          200: '#e4e4e7',
          300: '#d4d4d8',
          400: '#a1a1aa',
          500: '#71717a',
          600: '#52525b',
          700: '#3f3f46',
          800: '#27272a',
          900: '#18181b',
          950: '#09090b',
        },
        magenta: {
          50: '#fafafa',
          100: '#f4f4f5',
          200: '#e4e4e7',
          300: '#d4d4d8',
          400: '#a1a1aa',
          500: '#71717a',
          600: '#52525b',
          700: '#3f3f46',
          800: '#27272a',
          900: '#18181b',
        },
      },
      backgroundImage: {
        'gradient-app': 'linear-gradient(180deg, #ffffff 0%, #fafafa 100%)',
        'gradient-sidebar': 'linear-gradient(180deg, #18181b 0%, #27272a 100%)',
        'gradient-card': 'linear-gradient(145deg, #ffffff 0%, #fafafa 100%)',
        'gradient-brand': 'linear-gradient(180deg, #27272a 0%, #171717 100%)',
      },
      backdropBlur: {
        xs: '2px',
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.06)',
        'glass-hover': '0 12px 40px 0 rgba(0, 0, 0, 0.08)',
        'card': '0 4px 24px -1px rgba(0, 0, 0, 0.06), 0 2px 8px -2px rgba(0, 0, 0, 0.04)',
      },
    },
  },
  plugins: [],
}
