import { computed, getCurrentInstance, type ComputedRef } from 'vue'
import { generateTestId } from '@/utils/testId'

type GetterFn = () => string | undefined

/**
 * Composable for generating consistent test IDs for components
 * Automatically detects component name and props.name if available
 * 
 * @param args - Optional: component name override (string) or additional getter functions
 * @returns Object with testId (string) and testIdAttrs (object for v-bind)
 * 
 * @example
 * // Auto-detect everything (component name + props.name if exists)
 * const { testIdAttrs } = useTestId()
 * 
 * @example
 * // Add additional parts
 * const { testIdAttrs } = useTestId(() => fileName.value)
 * 
 * @example
 * // Override component name
 * const { testIdAttrs } = useTestId('custom-name', () => additionalPart.value)
 */
export function useTestId(
  ...args: [GetterFn?, ...GetterFn[]] | [string, GetterFn?, ...GetterFn[]]
): {
  testId: ComputedRef<string>
  testIdAttrs: ComputedRef<{ 'data-testid': string }>
} {
  const instance = getCurrentInstance()
  
  // Parse arguments: first arg might be component name override or a getter
  const [firstArg, ...restArgs] = args
  const isNameOverride = typeof firstArg === 'string'
  
  const componentName: string = isNameOverride 
    ? firstArg 
    : getAutoDetectedComponentName(instance)
  
  const additionalGetters: GetterFn[] = isNameOverride 
    ? restArgs as GetterFn[]
    : [firstArg, ...restArgs].filter((fn): fn is GetterFn => typeof fn === 'function')

  const testId = computed(() => {
    const parts: (string | undefined)[] = [componentName]
    
    // Auto-detect props.name if it exists and wasn't explicitly provided
    const propsName = (instance?.props as any)?.name
    const additionalParts = additionalGetters.map(getter => getter())
    
    // Only add auto-detected props.name if it's not already in additionalParts
    if (propsName && typeof propsName === 'string' && !additionalParts.includes(propsName)) {
      parts.push(propsName)
    }
    
    // Add any additional parts from getters
    parts.push(...additionalParts)
    
    return generateTestId(...parts)
  })

  const testIdAttrs = computed(() => ({
    'data-testid': testId.value
  }))

  return { testId, testIdAttrs }
}

/**
 * Auto-detects component name from Vue instance
 */
function getAutoDetectedComponentName(instance: ReturnType<typeof getCurrentInstance>): string {
  const detectedName = instance?.type.__name || instance?.type.name || 'pcomponent'
  return detectedName.toLowerCase()
}
