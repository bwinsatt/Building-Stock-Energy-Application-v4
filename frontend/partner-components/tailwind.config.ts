import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,vue}',
    './.storybook/**/*.{js,ts,jsx,tsx}',
  ],
  plugins: [],
}

export default config
