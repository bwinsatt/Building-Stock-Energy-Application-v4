// Export all components
// Example:
// export { default as PButton } from './components/PButton.vue'
export { default as PLayout } from './components/PLayout/PLayout.vue'
export { default as PLayoutGrid } from './components/PLayout/PLayoutGrid.vue'
export { default as PLayoutGridItem } from './components/PLayout/PLayoutGridItem.vue'
export { default as PIcon } from './components/PIcon/PIcon.vue'
export { default as PLogo } from './components/PLogo/PLogo.vue'
export { default as PTypography } from './components/PTypography/PTypography.vue'
export { default as PButton } from './components/PButton/PButton.vue'
export { PLabel } from './components/PLabel'
export { PCheckbox, PCheckboxGroup } from './components/PCheckbox'
export { PTable, PTableHead, PTableHeader, PTableRow, PTableCell, PTableBody, PTableEmpty, PTableFooter, PTableCaption } from './components/PTable'
export { PChip } from './components/PChip'
export { PPagination } from './components/PPagination'
export { PTooltip } from './components/PTooltip'
export { PBadge } from './components/PBadge'
export { PAvatar, PAvatarGroup } from './components/PAvatar'
export { PTextInput } from './components/PTextInput'
export { PTextArea } from './components/PTextArea'
export { PSearchBar } from './components/PSearchBar'
export { PPopover } from './components/PPopover'
export { PNumericInput } from './components/PNumericInput'

// Export types
// Example:
// export type { PButtonProps } from './types/button'
export type { PButtonProps, PButtonEmits } from './components/PButton'
export type { PIconProps, IconSize } from './components/PIcon/types'
export type { TypographyVariant, TypographyComponent, TypographyAlign } from './components/PTypography/types'
export type { PLabelProps } from './components/PLabel'
export type { PCheckboxProps, PCheckboxEmits, PCheckboxGroupProps, PCheckboxGroupItemProps, PCheckboxGroupEmits } from './components/PCheckbox'
export type { PTableProps, PTableHeadProps, PTableHeadEmits, PTableHeaderProps, PTableRowProps, PTableCellProps, PTableCellEmits, PTableBodyProps, PTableEmptyProps, PTableFooterProps, PTableCaptionProps } from './components/PTable'
export type { PChipProps, PChipEmits } from './components/PChip'
export type { PPaginationProps, PPaginationEmits } from './components/PPagination'
export type { PTooltipProps, PTooltipEmits } from './components/PTooltip'
export type { PBadgeProps } from './components/PBadge'
export type { PAvatarProps, PAvatarGroupProps } from './components/PAvatar'
export type { PTextInputProps, PTextInputEmits } from './components/PTextInput'
export type { PTextAreaProps, PTextAreaEmits } from './components/PTextArea'
export type { PSearchBarProps, PSearchBarEmits } from './components/PSearchBar'
export type { PPopoverProps, PPopoverEmits } from './components/PPopover'
export type { PNumericInputProps, PNumericInputEmits } from './components/PNumericInput'

// Export utilities
export * from './utils/validation'

// Export styles
import './styles/global.css'
