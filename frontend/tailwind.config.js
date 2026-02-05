/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#22c55e', // green-500
          hover: '#4ade80',   // green-400
          dark: '#166534',    // green-800
        },
        surface: {
          DEFAULT: '#18181b', // zinc-900
          light: '#27272a',   // zinc-800
          dark: '#09090b',    // zinc-950
        }
      },
      animation: {
        'spin-slow': 'spin 3s linear infinite',
        'bounce-slow': 'bounce 3s infinite',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}