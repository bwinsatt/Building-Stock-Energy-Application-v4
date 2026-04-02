<script setup lang="ts">
import '@/styles/global.css'
import { type HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/shadcn/ui/card'
import { PTypography } from '@/components/PTypography'

export interface PCardProps {
  class?: HTMLAttributes["class"]
  title?: string
  description?: string
  footer?: string
}

const props = defineProps<PCardProps>()
</script>

<template>
  <Card
    :class="cn(
      'partner-preflight',
      'p-2 border-1 border-(--partner-border-light) shadow-none rounded-md bg-(--partner-background-white)',
      props.class)"
  >
    <CardHeader class="p-2 partner-headline1">
      <CardTitle>
        <slot name="title">
          <PTypography variant="headline1">
            {{ title }}
          </PTypography>
        </slot>
      </CardTitle>
      <CardDescription class="partner-body2 text-(--partner-text-secondary)">
        <slot name="description">
          <PTypography
            variant="body2"
            component="span"
          >
            {{ description }}
          </PTypography>
        </slot>
      </CardDescription>
    </CardHeader>
    <CardContent class="p-2">
      <slot name="content">
        <slot />
      </slot>
    </CardContent>
    <CardFooter class="p-2 partner-body2 text-(--partner-text-secondary)">
      <slot name="footer">
        <PTypography variant="body2">
          {{ footer }}
        </PTypography>
      </slot>
    </CardFooter>
  </Card>
</template>