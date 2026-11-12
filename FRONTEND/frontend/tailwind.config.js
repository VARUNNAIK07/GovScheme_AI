/** @type {import('tailwindcss').Config} */
export default {
  content: {
    relative: true, // paths below are relative to this file, not the working directory
    files: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  },
  theme: {
    extend: {
      colors: {
        gov: {
          50: '#f0f5fa',
          100: '#e1ecf4',
          200: '#c3d9ea',
          300: '#94bcda',
          400: '#5e9bc5',
          500: '#387eb0',
          600: '#276493',
          700: '#1e4f76',
          800: '#1b4363',
          900: '#1a3852',
          950: '#0e2336',
        },
        civic: {
          green: '#137333',
          'green-bg': '#e6f4ea',
          amber: '#b06000',
          'amber-bg': '#fef7e0',
          red: '#c5221f',
          'red-bg': '#fce8e6',
          blue: '#1a73e8',
          'blue-bg': '#e8f0fe',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
