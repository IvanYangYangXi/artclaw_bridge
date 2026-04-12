/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#1E1E1E',
        'bg-secondary': '#2D2D2D',
        'bg-tertiary': '#3C3C3C',
        'bg-quaternary': '#4A4A4A',
        'text-primary': '#E0E0E0',
        'text-secondary': '#B0B0B0',
        'text-dim': '#888888',
        'border-default': '#555555',
        'border-hover': '#666666',
        'accent': '#5285A6',
        'accent-hover': '#6295B6',
        'accent-pressed': '#4275A6',
        'success': '#4CAF50',
        'warning': '#FF9800',
        'error': '#F44336',
        'info': '#2196F3',
        'msg-user': '#2A3530',
        'msg-assistant': '#282C38',
        'msg-thinking': '#2A283A',
        'msg-system': '#2A2A2A',
        'msg-tool': '#262218',
        'msg-tool-result': '#1E2E24',
        'msg-tool-error': '#2E1E1E',
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['Consolas', 'Monaco', 'Courier New', 'monospace'],
      },
      fontSize: {
        'title': ['18px', { lineHeight: '1.4', fontWeight: '600' }],
        'body': ['14px', { lineHeight: '1.6', fontWeight: '400' }],
        'small': ['12px', { lineHeight: '1.5', fontWeight: '400' }],
        'code': ['13px', { lineHeight: '1.5', fontWeight: '400' }],
      },
    },
  },
  plugins: [],
}
