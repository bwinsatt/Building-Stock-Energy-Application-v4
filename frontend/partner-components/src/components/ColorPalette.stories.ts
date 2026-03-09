import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { ref, onMounted, defineComponent, computed, type PropType } from 'vue'

/**
 * Color Palette for the Partner Design System
 * Colors are read dynamically from CSS custom properties defined in partner-colors.css
 */

const getCssVar = (v: string) => typeof document !== 'undefined' ? getComputedStyle(document.documentElement).getPropertyValue(v).trim() : ''

const shouldUseDarkText = (hex: string) => {
  if (!hex || hex.length < 6) return true
  const [r, g, b] = [0, 2, 4].map(i => parseInt(hex.replace('#', '').substr(i, 2), 16))
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5
}

interface ColorInfo {
  name: string
  hex: string
  cssVar: string
  textDark: boolean
  isMain: boolean
  isDefined: boolean
}

interface ColorFamily {
  key: string
  name: string
  description: string
  colors: ColorInfo[]
}

const colorFamilyDefs = [
  { key: 'partner-gray', name: 'Partner Gray', description: 'Used for text, borders, and neutral elements', cssPrefix: '--partner-gray', mainShade: 7 },
  { key: 'partner-blue', name: 'Partner Blue', description: 'Main brand color for primary actions', cssPrefix: '--partner-blue', mainShade: 7 },
  { key: 'partner-orange', name: 'Partner Orange', description: 'Secondary brand color for accents', cssPrefix: '--partner-orange', mainShade: 7 },
  { key: 'partner-red', name: 'Partner Red', description: 'Used for error states and destructive actions', cssPrefix: '--partner-red', mainShade: 7 },
  { key: 'partner-yellow', name: 'Partner Yellow', description: 'Used for warning states and alerts', cssPrefix: '--partner-yellow', mainShade: 7 },
  { key: 'partner-green', name: 'Partner Green', description: 'Used for success states and positive actions', cssPrefix: '--partner-green', mainShade: 7 },
]

const buildColor = (cssVar: string, name: string, isMain = false): ColorInfo => {
  const hex = getCssVar(cssVar)
  const isDefined = hex.length > 0
  return { name, hex: isDefined ? hex.toUpperCase() : 'Not defined', cssVar, textDark: isDefined ? shouldUseDarkText(hex) : true, isMain, isDefined }
}

const buildColorFamily = ({ key, name, description, cssPrefix, mainShade }: typeof colorFamilyDefs[0]): ColorFamily => ({
  key, name, description,
  colors: Array.from({ length: 10 }, (_, i) => {
    const shade = i + 1
    return buildColor(`${cssPrefix}-${shade}`, `${cssPrefix.replace(/^--/g, '')}-${shade}`, shade === mainShade)
  }),
})

const baseColorClass = (isDefined: boolean, textDark: boolean, lightClass: string, darkClass: string) => 
  isDefined ? (textDark ? lightClass : darkClass) : ''

const ColorSwatch = defineComponent({
  props: {
    color: { type: Object as PropType<ColorInfo>, required: true },
    showBorder: { type: Boolean, default: false },
  },
  setup({ color, showBorder }) {
    return {
      style: computed(() => color.isDefined ? { backgroundColor: color.hex } : {}),
      containerClass: computed(() => [
        'w-35 h-20 flex flex-col items-center justify-center gap-1.5 p-2 overflow-hidden',
        color.isDefined ? (showBorder ? 'border border-border' : '') : 'bg-muted border border-dashed border-destructive'
      ]),
      nameClass: computed(() => [
        'text-xs leading-tight px-1 text-center w-full overflow-hidden text-ellipsis whitespace-nowrap',
        baseColorClass(color.isDefined, color.textDark, 'text-gray-700', 'text-white') || 'text-foreground'
      ]),
      hexClass: computed(() => [
        'text-[11px] leading-tight',
        color.isDefined ? baseColorClass(color.isDefined, color.textDark, 'text-gray-500', 'text-white/80') : 'text-destructive font-medium'
      ]),
    }
  },
  template: `
    <div :style="style" :class="containerClass" :title="color.name + ' - ' + color.hex">
      <span v-if="color.isMain && color.isDefined" class="text-white text-xs leading-none">★</span>
      <span :class="nameClass">{{ color.name }}</span>
      <span :class="hexClass">{{ color.hex }}</span>
    </div>
  `,
})

const ColorFamilySection = defineComponent({
  components: { ColorSwatch },
  props: {
    family: { type: Object as PropType<ColorFamily>, required: true },
    showDescription: Boolean,
    showCssVarHint: Boolean,
  },
  template: `
    <div>
      <h2 class="text-2xl font-light text-foreground mb-2">{{ family.name }}</h2>
      <p v-if="showDescription" class="text-sm text-muted-foreground mb-4">{{ family.description }}</p>
      <div class="flex flex-wrap" :class="{ 'mt-4': !showDescription }">
        <ColorSwatch v-for="color in family.colors" :key="color.name" :color="color" />
      </div>
      <div v-if="showCssVarHint" class="mt-4 text-xs text-muted-foreground">
        <p>CSS Variable: <code class="bg-muted px-1 rounded">var({{ family.colors[0]?.cssVar }})</code> through <code class="bg-muted px-1 rounded">var({{ family.colors[family.colors.length - 1]?.cssVar }})</code></p>
      </div>
    </div>
  `,
})

export default {
  title: 'Design System/Color Palette',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'The color palette defines the foundation of our visual system. Each color family is built on a structured scale, ranging from the lightest tint to the deepest shade.\n\n**Families:** Partner Gray, Partner Blue, Partner Orange, Partner Red, Partner Yellow, Partner Green, Base (Black & White), Purple (design notes only).'
      },
    },
  },
} as Meta

type Story = StoryObj

export const ColorPalette: Story = {
  render: () => ({
    components: { ColorSwatch, ColorFamilySection },
    setup() {
      const families = ref<ColorFamily[]>([])
      const base = ref({ black: buildColor('--partner-black', 'partner-black'), white: buildColor('--partner-white', 'partner-white'), purple: buildColor('--partner-purple', 'partner-purple') })
      onMounted(() => {
        families.value = colorFamilyDefs.map(buildColorFamily)
        base.value = { black: buildColor('--partner-black', 'partner-black'), white: buildColor('--partner-white', 'partner-white'), purple: buildColor('--partner-purple', 'partner-purple') }
      })
      return { families, base }
    },
    template: `
      <div class="min-h-screen font-sans p-8 transition-colors duration-300">
        <div class="border-b border-border pb-8 mb-8">
          <p class="text-base text-partner-blue-7 mb-2">Partner Design System</p>
          <h1 class="text-6xl font-light leading-tight tracking-tight mb-4">Color Palette</h1>
          <p class="text-sm text-muted-foreground leading-5">
            The color palette defines the foundation of our visual system. Each color family is built on a structured scale, ranging from the lightest tint to the deepest shade.
            <br>
            <b>Main</b> shades are denoted with a <b>★</b>.
          </p>
        </div>
        <div class="space-y-12">
          <ColorFamilySection v-for="family in families" :key="family.key" :family="family" />
          <div>
            <h2 class="text-2xl font-light text-foreground mb-4">Partner Base Colors</h2>
            <div class="flex flex-wrap gap-4">
              <div><h3 class="text-lg font-light text-foreground mb-2">Partner Black</h3><ColorSwatch :color="base.black" /></div>
              <div><h3 class="text-lg font-light text-foreground mb-2">Partner White</h3><ColorSwatch :color="base.white" show-border /></div>
            </div>
          </div>
          <div>
            <h2 class="text-2xl font-light text-foreground mb-4">Partner Purple</h2>
            <p class="text-sm text-muted-foreground mb-4">Used for design notes (for designers only; not part of the design system)</p>
            <ColorSwatch :color="base.purple" />
          </div>
        </div>
      </div>
    `,
  }),
}

const createStory = (i: number): Story => ({
  render: () => ({
    components: { ColorFamilySection },
    setup() {
      const family = ref(buildColorFamily(colorFamilyDefs[i]))
      onMounted(() => { family.value = buildColorFamily(colorFamilyDefs[i]) })
      return { family }
    },
    template: `<div class="p-8 bg-background text-foreground font-sans transition-colors duration-300">
      <ColorFamilySection v-if="family" :family="family" show-description show-css-var-hint />
    </div>`,
  }),
})

export const PartnerGray = createStory(0)
export const PartnerBlue = createStory(1)
export const PartnerOrange = createStory(2)
export const PartnerRed = createStory(3)
export const PartnerYellow = createStory(4)
export const PartnerGreen = createStory(5)

export const PartnerBaseColors: Story = {
  render: () => ({
    components: { ColorSwatch },
    setup() {
      const black = ref(buildColor('--partner-black', 'partner-black'))
      const white = ref(buildColor('--partner-white', 'partner-white'))
      onMounted(() => {
        black.value = buildColor('--partner-black', 'partner-black')
        white.value = buildColor('--partner-white', 'partner-white')
      })
      return { black, white }
    },
    template: `
      <div class="p-8 bg-background text-foreground font-sans transition-colors duration-300">
        <h2 class="text-2xl font-light mb-2">Partner Base Colors</h2>
        <div class="flex flex-wrap gap-4">
          <div>
            <h3 class="text-lg font-light text-foreground mb-2">Partner Black</h3>
            <ColorSwatch :color="black" />
            <div class="mt-2 text-xs text-muted-foreground">
              <p>CSS Variable: <code class="bg-muted px-1 rounded">var({{ black.cssVar }})</code></p>
            </div>
          </div>
          <div>
            <h3 class="text-lg font-light text-foreground mb-2">Partner White</h3>
            <ColorSwatch :color="white" show-border />
            <div class="mt-2 text-xs text-muted-foreground">
              <p>CSS Variable: <code class="bg-muted px-1 rounded">var({{ white.cssVar }})</code></p>
            </div>
          </div>
        </div>
      </div>
    `,
  }),
}

export const PartnerPurple: Story = {
  render: () => ({
    components: { ColorSwatch },
    setup() {
      const color = ref(buildColor('--partner-purple', 'partner-purple'))
      onMounted(() => { color.value = buildColor('--partner-purple', 'partner-purple') })
      return { color }
    },
    template: `
      <div class="p-8 bg-background text-foreground font-sans transition-colors duration-300">
        <h2 class="text-2xl font-light mb-2">Partner Purple</h2>
        <p class="text-sm text-muted-foreground mb-6">Used for design notes (for designers only; not part of the design system)</p>
        <ColorSwatch :color="color" />
        <div class="mt-4 text-xs text-muted-foreground">
          <p>CSS Variable: <code class="bg-muted px-1 rounded">var({{ color.cssVar }})</code></p>
        </div>
      </div>
    `,
  }),
}
