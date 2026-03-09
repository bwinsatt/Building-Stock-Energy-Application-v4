# Partner Components - Sample App

This is a comprehensive sample application that demonstrates and tests all components from the Partner Components library, with a focus on the new dynamic theme system.

## Features

- **Complete Component Testing**: Tests all 5 components (PButton, PCard, PInput, PTable, PModal)
- **Dynamic Theme System**: Live demonstration of the new theme system with real-time theme switching
- **Interactive Examples**: Live demonstrations of component functionality
- **Theme Controls**: Buttons to switch between different color themes (Blue, Purple, Green)
- **Dark Mode Support**: Toggle between light and dark modes
- **Build Testing**: Uses the built library to verify the build process works correctly

## Theme System Demo

The sample app showcases the new theme system with:

- **PThemeProvider**: Wraps the entire application to provide theme context
- **Dynamic Theme Switching**: Real-time theme changes without page reload
- **Color Palette Display**: Visual representation of current theme colors
- **Component Adaptation**: All components automatically adapt to theme changes
- **Tailwind Integration**: Seamless integration with Tailwind CSS classes

### Theme Controls

- **Set Blue Theme**: Applies a blue color palette
- **Set Purple Theme**: Applies a purple color palette
- **Set Green Theme**: Applies a green color palette
- **Reset Theme**: Returns to default theme
- **Toggle Mode**: Switches between light and dark modes

## Components Tested

### PButton

- All variants (solid, outline, ghost, soft)
- All colors (primary, secondary, success, warning, danger, info)
- All sizes (xs, sm, md, lg, xl)
- Loading and disabled states
- Interactive click handling
- Theme-aware styling

### PCard

- Basic cards with headers
- Theme-aware styling
- Cards with footer actions
- Nested component usage

### PInput

- All input types (text, email, password, number)
- Different colors (primary, secondary, success)
- Different states (disabled, readonly, error)
- Form integration with v-model
- Theme-aware styling

### PTable

- Data display with pagination
- Sortable columns
- Loading states
- Row click handling
- Theme-aware styling

### PModal

- Different modal sizes (md, lg, xl)
- Form integration
- Complex content with nested components
- Proper event handling
- Theme-aware styling

## Getting Started

### Prerequisites

Make sure you have the Partner Components library built:

```bash
# From the root directory
npm run build
```

### Installation

```bash
cd examples/sample-app
npm install
```

### Development

```bash
npm run dev
```

This will start the development server at `http://localhost:3001`

### Building for Production

```bash
npm run build
```

This will create a production build in the `dist` directory.

### Preview Production Build

```bash
npm run preview
```

## Theme System Usage

The sample app demonstrates how to use the new theme system:

### 1. Wrap your app with PThemeProvider

```vue
<template>
  <PThemeProvider :theme="customTheme">
    <App />
  </PThemeProvider>
</template>
```

### 2. Define theme configurations

```vue
<script setup lang="ts">
  import type { ThemeConfig } from '@partnerdevops/partner-components'

  const customTheme: Partial<ThemeConfig> = {
    colors: {
      primary: {
        50: '#eff6ff',
        100: '#dbeafe',
        // ... full color scale
        950: '#172554',
      },
    },
  }
</script>
```

### 3. Update themes dynamically

```vue
<script setup lang="ts">
  const updateTheme = (newTheme: Partial<ThemeConfig>) => {
    customTheme.value = newTheme
  }
</script>
```

## What This Tests

### Build Process

- ✅ Library builds successfully
- ✅ Components are properly exported
- ✅ Theme system is bundled correctly
- ✅ TypeScript types are available

### Component Functionality

- ✅ All components render correctly
- ✅ Props are properly typed and validated
- ✅ Events are emitted correctly
- ✅ v-model integration works
- ✅ Theme-aware styling works

### Theme System

- ✅ PThemeProvider provides theme context
- ✅ Dynamic theme updates work
- ✅ CSS variables are applied correctly
- ✅ Components adapt to theme changes
- ✅ Dark mode switching works
- ✅ Tailwind integration works

### Styling

- ✅ Tailwind CSS is properly loaded
- ✅ Component styles are applied
- ✅ Theme colors are used correctly
- ✅ Responsive design works
- ✅ Theme consistency across components

### Integration

- ✅ Components work together
- ✅ Nested component usage
- ✅ Form handling
- ✅ State management
- ✅ Theme context sharing

## Troubleshooting

### Theme Not Working

If themes aren't working, make sure:

1. The app is wrapped with `PThemeProvider`
2. Theme configuration is properly structured
3. CSS variables are being applied to the document root
4. Tailwind config includes the theme color scales

### Styles Not Loading

If styles aren't loading, make sure:

1. The library has been built (`npm run build` from root)
2. Tailwind CSS is properly imported
3. The theme system is initialized

### Components Not Found

If components aren't found, check:

1. The library build was successful
2. The package.json dependency path is correct (`"partner-components": "file:../.."`)
3. TypeScript types are properly exported

### Build Errors

If you get build errors:

1. Make sure all dependencies are installed
2. Check that the library is built before running the sample app
3. Verify TypeScript configuration is correct
4. Ensure Tailwind config is properly set up

## Development Notes

This sample app serves as both a testing environment and documentation for the Partner Components library and its new theme system. It demonstrates:

- How to import and use components
- How to implement the theme system
- Proper TypeScript integration
- Dynamic theme switching
- Component interaction patterns
- Best practices for implementation

The app is designed to be comprehensive while remaining simple enough to quickly identify any issues with the component library or theme system.
