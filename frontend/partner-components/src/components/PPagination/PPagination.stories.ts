import type { Meta, StoryObj } from '@storybook/vue3-vite'
import PPagination from './PPagination.vue'

const meta: Meta<typeof PPagination> = {
  component: PPagination,
  title: 'Components/PPagination',
  parameters: {
    layout: 'centered',
  },
  args: {
    itemsPerPage: 1,
    totalPages: 12,
    currentPage: 1,
    size: 'medium',
  },
  argTypes: {
    itemsPerPage: {
      control: 'number',
      description: 'Number of items per page',
    },
    totalPages: {
      control: 'number',
      description: 'Total number of pages',
    },
    currentPage: {
      control: 'number',
      description: 'Currently selected page',
    },
    size: {
      control: 'select',
      options: ['small', 'medium'],
      description: 'Button size',
    },
    'onUpdate:page': {
      type: 'function',
      args: 'page: number',
      description: 'Fired when page changes'
    }
  },
}

export default meta

export const Default: StoryObj<typeof PPagination> = {
  render: (args) => ({
    components: { PPagination },
    setup: () => ({ args }),
    template: `
      <PPagination v-bind="args" />
    `,
  }),
}