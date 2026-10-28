/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"SF Mono"', 'Menlo', 'ui-monospace', 'monospace'],
      },
      colors: {
        terminal: {
          bg:       '#080c14',
          panel:    '#0d1117',
          border:   '#1c2333',
          hover:    '#161b27',
          orange:   '#f59e0b',
          'orange-dim': '#92400e',
          green:    '#10b981',
          red:      '#ef4444',
          blue:     '#3b82f6',
          cyan:     '#06b6d4',
          muted:    '#4b5563',
          text:     '#e2e8f0',
          'text-dim': '#6b7280',
          header:   '#0a0f1e',
        },
      },
      animation: {
        'blink': 'blink 1s step-end infinite',
        'ticker': 'ticker 30s linear infinite',
        'fade-in': 'fadeIn 0.2s ease-in',
      },
      keyframes: {
        blink: { '0%, 100%': { opacity: 1 }, '50%': { opacity: 0 } },
        ticker: { '0%': { transform: 'translateX(0)' }, '100%': { transform: 'translateX(-50%)' } },
        fadeIn: { from: { opacity: 0, transform: 'translateY(4px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
