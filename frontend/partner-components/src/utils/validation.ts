// Validation utilities for Partner Components

export interface ValidationRule {
  required?: boolean
  minLength?: number
  maxLength?: number
  pattern?: RegExp
  email?: boolean
  url?: boolean
  custom?: (value: string | number) => boolean | string
}

export interface ValidationResult {
  isValid: boolean
  errors: string[]
}

// Email validation regex
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// URL validation regex
const URL_REGEX = /^https?:\/\/.+\..+/

// Validate a single value against rules
export const validateField = (
  value: string | number | null | undefined,
  rules: ValidationRule
): ValidationResult => {
  const errors: string[] = []

  // Required validation
  if (rules.required && (!value || value.toString().trim() === '')) {
    errors.push('This field is required')
  }

  // Skip other validations if value is empty and not required
  if (!value || value.toString().trim() === '') {
    return { isValid: errors.length === 0, errors }
  }

  const stringValue = value.toString()

  // Min length validation
  if (rules.minLength && stringValue.length < rules.minLength) {
    errors.push(`Minimum length is ${rules.minLength} characters`)
  }

  // Max length validation
  if (rules.maxLength && stringValue.length > rules.maxLength) {
    errors.push(`Maximum length is ${rules.maxLength} characters`)
  }

  // Pattern validation
  if (rules.pattern && !rules.pattern.test(stringValue)) {
    errors.push('Invalid format')
  }

  // Email validation
  if (rules.email && !EMAIL_REGEX.test(stringValue)) {
    errors.push('Please enter a valid email address')
  }

  // URL validation
  if (rules.url && !URL_REGEX.test(stringValue)) {
    errors.push('Please enter a valid URL')
  }

  // Custom validation
  if (rules.custom) {
    const customResult = rules.custom(value)
    if (typeof customResult === 'string') {
      errors.push(customResult)
    } else if (!customResult) {
      errors.push('Invalid value')
    }
  }

  return { isValid: errors.length === 0, errors }
}

// Validate multiple fields
export const validateForm = (
  data: Record<string, string | number | null | undefined>,
  rules: Record<string, ValidationRule>
): ValidationResult => {
  const errors: string[] = []
  let isValid = true

  Object.entries(rules).forEach(([field, fieldRules]) => {
    const fieldValue = data[field]
    const fieldValidation = validateField(fieldValue, fieldRules)

    if (!fieldValidation.isValid) {
      isValid = false
      errors.push(
        ...fieldValidation.errors.map((error) => `${field}: ${error}`)
      )
    }
  })

  return { isValid, errors }
}

// Common validation rules
export const commonRules = {
  required: { required: true },
  email: { email: true },
  url: { url: true },
  password: {
    required: true,
    minLength: 8,
    pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
    custom: (value: string) => {
      if (!/(?=.*[a-z])/.test(value))
        return 'Password must contain at least one lowercase letter'
      if (!/(?=.*[A-Z])/.test(value))
        return 'Password must contain at least one uppercase letter'
      if (!/(?=.*\d)/.test(value))
        return 'Password must contain at least one number'
      return true
    },
  },
  phone: {
    pattern: /^[+]?[1-9][\d]{0,15}$/,
    custom: (value: string) => {
      const cleaned = value.replace(/\D/g, '')
      return cleaned.length >= 10 && cleaned.length <= 15
    },
  },
}

// Format validation error for display
export const formatValidationError = (error: string): string => {
  return error.charAt(0).toUpperCase() + error.slice(1)
}
