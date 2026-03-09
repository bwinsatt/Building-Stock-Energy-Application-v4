import { expect, test } from 'vitest'
import { getInitials } from '@/utils/strings'
import { generateTestId } from '@/utils/testId'

test('getInitials', () => {
  expect(getInitials('John Doe')).toBe('JD')
  expect(getInitials('Jane Smith')).toBe('JS')
  expect(getInitials('John')).toBe('J')
  expect(getInitials('')).toBe('')
  expect(getInitials(' ')).toBe('')
  expect(getInitials('123')).toBe('1')
  expect(getInitials('John Jacob Jingleheimer Schmidt')).toBe('JS')
  expect(getInitials('John Doe 123')).toBe('J1')
})

test('generateTestId', () => {
  expect(generateTestId('PButton', 'submit')).toBe('pbutton-submit')
  expect(generateTestId('PLogo', undefined, 'sitelynx')).toBe('plogo-sitelynx')
  expect(generateTestId('PTable', 'User List', 'row-1')).toBe('ptable-user-list-row-1')
})