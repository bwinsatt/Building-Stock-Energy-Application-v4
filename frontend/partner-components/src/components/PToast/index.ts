export { default as PToast, type PToastProps } from "./PToast.vue"
export { showToast, type ShowToastOptions } from "./showToast"

export const toastPositions = [
  'top-left',
  'top-center',
  'top-right',
  'bottom-left',
  'bottom-center',
  'bottom-right'] as const