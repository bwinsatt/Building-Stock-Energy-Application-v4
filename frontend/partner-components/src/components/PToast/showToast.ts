import { toast } from 'vue-sonner'
import { markRaw, h, defineComponent } from 'vue'
import { PAlert, type PAlertProps } from '@/components/PAlert'

export interface ShowToastOptions extends PAlertProps {
  duration?: number
  dismissible?: boolean
  onClose?: (event: MouseEvent) => void
  onAction?: (event: MouseEvent) => void
}

export function showToast(options?: ShowToastOptions) {
  const { onClose, onAction, duration = 4000, dismissible = false, ...alertProps } = options ?? {}

  const toastId = toast.custom(
    markRaw(
      defineComponent({
        setup() {
          return () => h(PAlert, {
            ...alertProps,
            hideCloseButton: !dismissible,
            onClose: (event: MouseEvent) => {
              toast.dismiss(toastId)
              onClose?.(event)
            },
            onAction: (event: MouseEvent) => {
              toast.dismiss(toastId)
              onAction?.(event)
            },
          })
        },
      })
    ),
    { duration, dismissible },
  )
  return toastId
}