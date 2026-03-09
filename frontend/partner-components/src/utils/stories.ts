export const withWarning = (template: string, warning: string) => `
  <div class="flex flex-col items-center gap-2">
    <div class="rounded-lg flex items-center justify-center p-2 bg-linear-to-t from-(--partner-yellow-7) to-(--partner-yellow-4)">
      <PIcon name="warning-alt-filled" color="var(--partner-orange-7)" size="large" />
      <PTypography :variant="body1">${warning}</PTypography>
    </div>
    ${template}
  </div>
`

export const withZoomWarning = (template: string, name: string = 'component') => `
  ${withWarning(template, `Please note that there is a known issue with the ${name} positioning when Storybook zoomed.`)}
`