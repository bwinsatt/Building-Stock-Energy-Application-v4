import { sizeOptions } from "@/types/size";

export const chipVariants = [
  'primary',
  'secondary',
  'error',
  'warning',
  'success',
  'neutral',
]

export const chipAppearances = [
  'contained',
  'outlined',
]

export const chipSizes = sizeOptions;

export const allVariantsTemplate = `
  <div class="grid grid-cols-2 gap-4 w-full">
    <div v-for="disabled in [false, true]" :key="disabled" class="grid-item">
      <h2 class="text-center text-xl font-semibold capitalize">{{ disabled ? 'Disabled' : 'Enabled' }}</h2>
      <div class="flex flex-col gap-4">
        <!-- Group by Appearance -->
        <div v-for="appearance in chipAppearances" :key="appearance" class="flex flex-col gap-2">
          <h3 class="text-lg font-semibold capitalize">{{ appearance }}</h3>
          
          <!-- Group by Size within each Appearance -->
          <div v-for="size in chipSizes" :key="size" class="flex flex-col gap-1">
            <p class="text-sm text-gray-600 capitalize">{{ size }}</p>
            
            <!-- All Variants for this Appearance + Size combination -->
            <div class="flex flex-wrap gap-1">
              <PChip 
                v-bind="args"
                v-for="variant in chipVariants" 
                :key="variant"
                :variant="variant" 
                :appearance="appearance" 
                :size="size"
                :disabled="disabled"
              >
                {{ variant }}
              </PChip>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  `