import type { Meta, StoryObj } from '@storybook/vue3-vite'
import PIcon from './PIcon.vue'
import { ref, watch, nextTick, computed } from 'vue'
import { customIcons, iconOptions, isCustomIcon, normalizeIconName } from './iconNames'
import { sizeOptions } from '@/types/size'

const meta: Meta<typeof PIcon> = {
  component: PIcon,
  title: 'Components/PIcon',
  parameters: {
    layout: 'centered',
  },
  argTypes: {
    name: {
      control: {
        type: 'select',
      },
      options: iconOptions,
      description: 'Icon name. Partner Components icons are listed first, followed by Carbon icons (fallback). Type to search or scroll to find icons.',
    },
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'Icon size',
    },
    width: {
      control: 'number',
      description: 'Icon width',
    },
    height: {
      control: 'number',
      description: 'Icon height',
    },
    color: {
      control: 'color',
      description: 'Icon color',
    },
    notes: {
      table: { disable: true },
    },
  } as any,
}

export default meta
type Story = StoryObj<typeof meta>

const renderWithDescription = (args: any) => ({
  components: { PIcon },
  setup() {
    const iconRef = ref<any>(null)
    const isCustom = ref(false)
    
    // Normalize icon name (handle dividers)
    const normalizedArgs = computed(() => {
      const normalizedName = normalizeIconName(args.name)
      return {
        ...args,
        name: normalizedName,
      }
    })
    
    watch(() => normalizedArgs.value.name, async () => {
      await nextTick()
      const iconName = normalizedArgs.value.name
      // Check if it's a custom icon by checking the registry
      isCustom.value = iconName ? isCustomIcon(iconName) : false
    }, { immediate: true })
    
    return { args: normalizedArgs, iconRef, isCustom }
  },
  template: `
    <div class="flex flex-col items-center">
      <PIcon v-bind="args" ref="iconRef" />
      <p class="mt-4 text-xs text-center text-muted-foreground max-w-[300px]">
        <template v-if="isCustom">
          Icon <code class="text-xs bg-muted px-2 py-1 rounded w-fit">{{ args.name }}</code> was found in the Partner Components icon registry.
        </template>
        <template v-else>
          Icon <code class="text-xs bg-muted px-2 py-1 rounded w-fit">{{ args.name }}</code> doesn't exist in the Partner Components icon registry, so it automatically falls back to the Iconify Carbon icon library.
        </template>
        <template v-for="note in args.notes">
          <p class="text-xs text-muted-foreground mt-2" v-html="note"></p>
        </template>
      </p>
    </div>
  `,
})

export const CustomIcons: Story = {
  render: () => ({
    components: { PIcon },
    setup() {
      return { customIcons }
    },
    template: `
      <div class="p-8">
        <h2 class="text-lg font-semibold mb-4">Partner Components Custom Icons</h2>
        <p class="text-sm text-muted-foreground mb-6">
          All custom icons available in the Partner Components icon registry.
        </p>
        <div class="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-4">
          <div
            v-for="iconName in customIcons"
            :key="iconName"
            class="flex flex-col items-center gap-2 p-3 rounded border hover:bg-muted/50 transition-colors"
          >
            <PIcon :name="iconName" size="large" />
            <span class="text-xs text-center text-muted-foreground break-all">{{ iconName }}</span>
          </div>
        </div>
      </div>
    `,
  }),
  parameters: {
    layout: 'fullscreen',
    controls: { disable: true },
  },
}

export const Default: Story = {
  args: {
    name: 'r-drive',
    size: 'medium',
    notes: ['Default icon size is medium (24px), do not resize icons above large (32px).',
      '<code class="text-xs bg-muted px-2 py-1 rounded w-fit whitespace-nowrap">data-customiconfound</code> attribute is set to "true" if the icon is a custom Partner Components icon, otherwise "false" and Carbon icon from Iconify is used as fallback.',
    ],
  } as any,
  render: renderWithDescription,
}

export const IconifyCarbonFallback: Story = {
  args: {
    name: 'bee',
    size: 'large',
  },
  render: renderWithDescription,
}

export const Color: Story = {
  args: {
    name: 'color-palette',
    size: 'large',
    color: 'var(--partner-blue-7)',
    notes: ['Do not recolor icons with random hex values, use the color palette instead. IE: Use <code class="text-xs bg-muted px-2 py-1 rounded w-fit whitespace-nowrap">var(--partner-blue-7)</code> instead of <code class="text-xs bg-muted px-2 py-1 rounded w-fit whitespace-nowrap">#005199</code>.'],
  } as any,
  render: renderWithDescription,
}