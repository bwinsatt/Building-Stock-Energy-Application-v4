import { describe, expect, it } from 'vitest'
import { formatReplacementNotice, resolveMeasureToggle } from './useMeasureSelections'

describe('resolveMeasureToggle', () => {
  it('replaces overlapping individual measures when selecting a package', () => {
    const result = resolveMeasureToggle({
      selectedUpgradeIds: new Set([49]),
      packageConstituentMap: new Map([[54, [48, 49, 52]]]),
      disabledByPackage: new Map(),
      upgradeId: 54,
    })

    expect(result.action).toBe('replaced')
    expect(Array.from(result.nextSelectedUpgradeIds)).toEqual([54])
    expect(result.replacedIds).toEqual([49])
  })

  it('returns null when attempting to toggle a disabled individual measure', () => {
    const result = resolveMeasureToggle({
      selectedUpgradeIds: new Set([54]),
      packageConstituentMap: new Map([[54, [48, 49, 52]]]),
      disabledByPackage: new Map([[49, 'Package 1, Wall + Roof Insulation + New Windows']]),
      upgradeId: 49,
    })

    expect(result).toBeNull()
  })
})

describe('formatReplacementNotice', () => {
  it('formats singular replacement copy', () => {
    expect(formatReplacementNotice({
      packageName: 'Package 1, Wall + Roof Insulation + New Windows',
      replacedNames: ['Roof Insulation'],
    })).toBe('Roof Insulation was deselected because it is included in Package 1, Wall + Roof Insulation + New Windows.')
  })

  it('formats plural replacement copy', () => {
    expect(formatReplacementNotice({
      packageName: 'Package 1, Wall + Roof Insulation + New Windows',
      replacedNames: ['Wall Insulation', 'Roof Insulation', 'New Windows'],
    })).toBe('Wall Insulation, Roof Insulation, and New Windows were deselected because they are included in Package 1, Wall + Roof Insulation + New Windows.')
  })
})
