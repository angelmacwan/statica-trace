/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#f8f9f9',
          bright: '#f8f9f9',
          container: {
            lowest: '#ffffff',
            low: '#f3f4f4',
            DEFAULT: '#edeeee',
            high: '#e7e8e8',
            highest: '#e1e3e3',
          },
          dim: '#d9dada',
        },
        primary: {
          DEFAULT: '#12283c',
          container: '#293e53',
          fixed: '#cfe5ff',
          'fixed-dim': '#b3c9e2',
        },
        secondary: {
          DEFAULT: '#506071',
          container: '#d3e4f8',
        },
        tertiary: {
          fixed: '#ffdcc5',
          'fixed-dim': '#ffb783',
        },
        'on-primary': '#ffffff',
        'on-secondary': '#ffffff',
        'on-secondary-container': '#566677',
        'on-surface': '#191c1c',
        'on-surface-variant': '#43474c',
        'on-tertiary-fixed': '#301400',
        outline: {
          DEFAULT: '#74777d',
          variant: '#c4c6cd',
        },
        error: {
          DEFAULT: '#ba1a1a',
          container: '#ffdad6',
        },
        'on-error': '#ffffff',
        success: '#2d6a4f',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'system-ui', 'sans-serif'],
        headline: ['Manrope', 'sans-serif'],
      },
      borderRadius: {
        '2.5xl': '1.75rem',
        '3.5xl': '2rem',
      },
      boxShadow: {
        'ambient-sm': '0 2px 12px rgba(25, 28, 28, 0.04)',
        'ambient-lg': '0 40px 40px -10px rgba(25, 28, 28, 0.06)',
        'brand': '0 2px 16px rgba(18, 40, 60, 0.18)',
        'hero': '0 30px 70px rgba(10, 25, 38, 0.16)',
      },
      screens: {
        tablet: '860px',
        wide: '1180px',
      },
    },
  },
  plugins: [],
}
