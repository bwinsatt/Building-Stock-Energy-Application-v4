import type { Meta, StoryObj } from '@storybook/vue3-vite'

const spacingTokens = [
  { token: 'spacing-0', rem: '0', px: '0', tailwind: 'p-0' },
  { token: 'partner-spacing-half', rem: '0.125', px: '2', tailwind: 'p-(--spacing-half), p-[0.125rem]' },
]

for (let i = 1; i <= 16; i++) {
  spacingTokens.push({ token: `spacing-${i}`, rem: `${i * 0.25}`, px: `${i * 4}`, tailwind: `p-${i}` })
}

const meta: Meta = {
  title: 'Design System/Spacing',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'The spacing scale defines consistent spacing values used throughout the Partner Design System.',
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof meta>

export const Spacing: Story = {
  render: () => ({
    setup() {
      return { spacingTokens }
    },
    template: `
      <div class="min-h-screen p-12">
        <div class="border-b border-charcoal-5 pb-12 mb-12">
          <p class="text-base text-partner-blue-7 mb-2">Partner Design System</p>
          <h1 class="text-6xl font-light leading-tight tracking-tight mb-4">Spacing</h1>
        </div>
        
        <div class="border border-border rounded-lg overflow-hidden bg-card">
          <table class="w-full">
            <thead class="bg-muted/50 border-b border-charcoal-2">
              <tr>
                <th class="text-left p-4 font-semibold text-base w-[200px] border-r border-charcoal-2">Token</th>
                <th class="text-left p-4 font-semibold text-base w-[160px] border-r border-charcoal-2">rem</th>
                <th class="text-left p-4 font-semibold text-base w-[160px] border-r border-charcoal-2">px</th>
                <th class="text-left p-4 font-semibold text-base w-[160px]">Tailwind Padding</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in spacingTokens" :key="item.token" class="border-b border-border hover:bg-muted/50 transition-colors">
                <td class="p-4 h-20 border-r border-charcoal-2">
                    {{ item.token }}
                </td>
                <td class="p-4 h-20 border-r border-charcoal-2 text-sm text-muted-foreground">
                  {{ item.rem }}
                </td>
                <td class="p-4 h-20 border-r border-charcoal-2 text-sm text-muted-foreground">
                  {{ item.px }}
                </td>
                <td class="p-4 h-20 text-sm text-muted-foreground">
                 <template v-for="tailwind in item.tailwind.split(',')">
                    <code class="text-xs bg-muted p-1 rounded w-fit mr-1">
                      {{ tailwind.trim() }}
                    </code>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    `,
  }),
}

