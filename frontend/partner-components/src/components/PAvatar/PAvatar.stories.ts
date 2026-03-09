import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PAvatar } from './index'
import avatarExamplePhoto from '@/assets/images/avatar_example_photo.jpg'
import { PTypography } from '../PTypography'
import { avatarOptions } from './index'
import { tooltipDirections } from '../PTooltip'

const noExistImage = '/src/assets/images/does_not_exist.jpg'

const subcomponents = { PTypography }

const meta: Meta<typeof PAvatar> = {
  title: 'Components/PAvatar',
  component: PAvatar,
  subcomponents,
  argTypes: {
    size: {
      control: 'select',
      options: avatarOptions.sizes,
    },
    shape: {
      control: 'select',
      options: avatarOptions.shapes,
    },
    badge: {
      control: 'select',
      options: avatarOptions.badges,
    },
    badgePosition: {
      control: 'select',
      options: avatarOptions.badgePositions,
    },
    image: {
      control: 'select',
      options: [avatarExamplePhoto, "/src/assets/images/does_not_exist.jpg", undefined],
      description: 'Image URL',
    },
    name: {
      control: 'text',
      description: 'Name to display, will be used to generate initials',
    },
    initials: {
      control: 'text',
      description: 'Manually set the initials to display',
    },
    tooltipDirection: {
      control: 'select',
      options: tooltipDirections,
    },
  },
}

export default meta
type Story = StoryObj<typeof meta>

const withDescription = (template: string, description: string) => `
  <div class="flex flex-col items-center gap-2">
    ${template}
    <PTypography :variant="body1">${description}</PTypography>
  </div>
`

const templates = {
  size: `
    <div class="grid grid-cols-2 gap-4 w-fit">
      <div v-for="avatarSize in avatarOptions.sizes" :key="avatarSize" class="flex flex-col items-center gap-2">
        <PTypography :variant="body1">{{ avatarSize }}</PTypography>
        <PAvatar v-bind="args" :size="avatarSize" />
      </div>
    </div>
  `,
}

export const Default: Story = {
  args: {
    size: 'medium',
    shape: 'circle',
  },
}

export const IconOnly: Story = {
  args: {
    size: 'medium',
    shape: 'circle',
  },
  render: (args) => {
    return {
      components: { PAvatar, subcomponents },
      setup() {
        return { args, avatarOptions }
      },
      template: withDescription(templates.size, 'An icon is displayed when no image, name, or initials are provided.'),
    }
  },
}

export const WithImage: Story = {
  args: {
    size: 'medium',
    shape: 'circle',
    image: avatarExamplePhoto,
    name: 'Jane Doe',
  },
  render: (args) => {
    return {
      components: { PAvatar, subcomponents },
      setup() {
        return { args, avatarOptions }
      },
      template: templates.size,
    }
  },
}

export const WithMissingImage: Story = {
  args: {
    size: 'medium',
    shape: 'circle',
    image: noExistImage,
    name: 'Jane Doe',
  },
  render: (args) => {
    return {
      components: { PAvatar, subcomponents },
      setup() {
        return { args, avatarOptions }
      },
      template: templates.size,
    }
  },
}

export const WithName: Story = {
  args: {
    size: 'medium',
    shape: 'circle',
    name: 'Jane Doe',
  },
  render: (args) => {
    return {
      components: { PAvatar, subcomponents },
      setup() {
        return { args, avatarOptions }
      },
      template: withDescription(templates.size, 'A name generates initials to display and provides a hover tooltip with the full name.'),
    }
  },
}

export const WithInitials: Story = {
  args: {
    size: 'medium',
    shape: 'circle',
    initials: 'JD',
    name: 'Different Name',
  },
  render: (args) => {
    return {
      components: { PAvatar, subcomponents },
      setup() {
        return { args, avatarOptions }
      },
      template: withDescription(templates.size, 'Manually set the initials to display, with or without a name.'),
    }
  },
}

export const WithBadge: Story = {
  args: {
    size: 'medium',
    shape: 'circle',
    badge: 'online',
    name: 'Jane Doe',
  },
  render: (args) => {
    return {
      components: { PAvatar, subcomponents },
      setup() {
        return { args, avatarOptions }
      },
      template: `
      <div class="flex flex-col items-center gap-4 w-fit">
        <div class="grid grid-cols-2 gap-4 w-fit">
          <div v-for="badge in avatarOptions.badges" :key="badge" class="flex flex-col items-center gap-2">
            <PTypography :variant="body1">{{ badge }}</PTypography>
            <PAvatar v-bind="args" :badge="badge" />
          </div>
        </div>
        ${templates.size}
        <div class="grid grid-cols-2 gap-4 w-fit">
          <div v-for="badgePosition in avatarOptions.badgePositions" :key="badgePosition" class="flex flex-col items-center gap-2">
            <PTypography :variant="body1">{{ badgePosition }}</PTypography>
            <PAvatar v-bind="args" :badgePosition="badgePosition" />
          </div>
        </div>
      </div>
      `,
    }
  },
}

export const StressTest: Story = {
  args: {
    size: 'medium',
    shape: 'circle',
    image: avatarExamplePhoto,
    name: 'Jane Doe',
  },
  render: (args) => {
    return {
      components: { PAvatar, subcomponents },
      setup() {
        return { args, avatarOptions, avatarExamplePhoto, noExistImage }
      },
      template: `
      <div class="flex flex-col items-center gap-4 w-fit">
        <div class="grid grid-cols-40 gap-4 w-fit">
          <div v-for="i in 1000" :key="i" class="flex flex-col items-center gap-2">
            <PAvatar v-bind="args" :image="Math.random() > 0.5 ? avatarExamplePhoto : noExistImage" />
          </div>
        </div>
      </div>
      `,
    }
  },
}