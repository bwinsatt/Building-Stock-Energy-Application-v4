// For more info, see https://github.com/storybookjs/eslint-plugin-storybook#configuration-flat-config-format
import storybook from "eslint-plugin-storybook";

import js from '@eslint/js'
import typescript from '@typescript-eslint/eslint-plugin'
import typescriptParser from '@typescript-eslint/parser'
import vue from 'eslint-plugin-vue'
import globals from 'globals'

export default [{
  ignores: ['**/node_modules/**', '**/dist/**', '**/storybook-static/**'],
}, js.configs.recommended, ...vue.configs['flat/recommended'], {
  files: ['**/*.{js,jsx,ts,tsx,cjs,mjs,cts,mts}'],
  ignores: ['**/node_modules/**', '**/dist/**', '**/storybook-static/**'],
  languageOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    globals: {
      ...globals.browser,
      ...globals.node,
      __dirname: 'readonly'
    },
    parser: typescriptParser,
    parserOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module'
    }
  },
  plugins: {
    '@typescript-eslint': typescript
  },
  rules: {
    '@typescript-eslint/no-unused-vars': 'error',
    '@typescript-eslint/no-explicit-any': 'warn',
    'no-unused-vars': 'off',
    'no-undef': 'error'
  }
}, {
  files: ['**/*.vue'],
  languageOptions: {
    parserOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parser: typescriptParser,
      extraFileExtensions: ['.vue']
    },
    globals: {
      ...globals.browser
    }
  },
  plugins: {
    '@typescript-eslint': typescript
  },
  rules: {
    'vue/multi-word-component-names': 'off',
    'vue/require-default-prop': 'off',
    'vue/require-prop-types': 'off',
    '@typescript-eslint/no-unused-vars': 'error',
    '@typescript-eslint/no-explicit-any': 'warn',
    'no-unused-vars': 'off',
    'no-undef': 'error'
  }
}, ...storybook.configs["flat/recommended"]];
