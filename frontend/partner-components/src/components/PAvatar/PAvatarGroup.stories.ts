import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PAvatarGroup, avatarOptions } from './index'
import avatarExamplePhoto from '@/assets/images/avatar_example_photo.jpg'
import { tooltipDirections } from '../PTooltip'

const meta: Meta<typeof PAvatarGroup> = {
  component: PAvatarGroup,
  title: 'Components/PAvatarGroup',
  argTypes: {
    size: {
      control: 'select',
      options: avatarOptions.sizes,
    },
    shape: {
      control: 'select',
      options: avatarOptions.shapes,
    },
    maxVisible: {
      control: 'select',
      options: [0, 1, 2, 3, 4],
    },
    spacing: {
      control: 'select',
      options: avatarOptions.spacing,
    },
    tooltipDirection: {
      control: 'select',
      options: tooltipDirections,
    },
  },
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    size: 'medium',
    shape: 'circle',
    maxVisible: 4,
    avatars: [
      {
        size: 'medium',
        shape: 'circle',
        image: avatarExamplePhoto,
        badge: 'online',
        name: 'Jane Doe',
      },
      {
        size: 'medium',
        shape: 'circle',
        badge: 'busy',
        name: 'John Doe',
      },
      {
        size: 'medium',
        shape: 'circle',
        badge: 'away',
        name: 'Bob Doe',
      },
      {
        size: 'medium',
        shape: 'circle',
        badge: 'offline',
        name: 'Alice Doe',
      },
      {
        size: 'medium',
        shape: 'circle',
        name: 'Charlie Doe',
      },
    ],
  },
}