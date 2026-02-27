/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,jsx}',
    './components/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['DM Serif Display', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
        sans: ['Sora', 'sans-serif'],
      },
      colors: {
        ink: '#080c10',
        surface: '#0f1419',
        panel: '#161d26',
        border: '#1e2938',
        gold: '#e8b44a',
        'gold-dim': '#a07a28',
        muted: '#4a5a6e',
        ghost: '#8899a6',
        light: '#c8d8e8',
        bright: '#e8f0f8',
        danger: '#e05252',
        success: '#4caf82',
        info: '#5b9bd5',
      },
      animation: {
        'fade-up': 'fadeUp 0.5s ease forwards',
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: 0, transform: 'translateY(16px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
}
