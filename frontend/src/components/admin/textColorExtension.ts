import { Mark, mergeAttributes } from '@tiptap/core'

export const ALLOWED_COLOR_HEXES = [
  '#017151',
  '#000000',
  '#174243',
  '#FFFFFF',
  '#BAD7BB',
  '#39687B',
  '#5EA99E',
  '#F1E5A6',
  '#FF5050'
] as const

export type AllowedColorHex = (typeof ALLOWED_COLOR_HEXES)[number]

export interface ColorOption {
  name: string
  hex: AllowedColorHex
}

export interface ColorSection {
  title: string
  colors: ColorOption[]
}

export const COLOR_SECTIONS: ColorSection[] = [
  {
    title: 'PRIMARY COLORS',
    colors: [
      { name: 'Dark Green', hex: '#017151' },
      { name: 'Black', hex: '#000000' },
      { name: 'Teal', hex: '#174243' },
      { name: 'White', hex: '#FFFFFF' }
    ]
  },
  {
    title: 'SECONDARY COLORS',
    colors: [
      { name: 'Light Green', hex: '#BAD7BB' }
    ]
  },
  {
    title: 'TERTIARY COLORS',
    colors: [
      { name: 'Air Force Blue', hex: '#39687B' },
      { name: 'Yellow', hex: '#F1E5A6' },
      { name: 'Mint Green', hex: '#5EA99E' },
      { name: 'Red', hex: '#FF5050' }
    ]
  }
]

const ALLOWED_SET = new Set<string>(ALLOWED_COLOR_HEXES)

export function normalizeAllowedColor(raw: string | null | undefined): AllowedColorHex | null {
  if (!raw || typeof raw !== 'string') return null
  const trimmed = raw.trim().toUpperCase()
  if (ALLOWED_SET.has(trimmed)) {
    return trimmed as AllowedColorHex
  }
  const rgbMatch = trimmed.match(/^RGB\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/)
  if (rgbMatch) {
    const r = Number(rgbMatch[1]).toString(16).padStart(2, '0').toUpperCase()
    const g = Number(rgbMatch[2]).toString(16).padStart(2, '0').toUpperCase()
    const b = Number(rgbMatch[3]).toString(16).padStart(2, '0').toUpperCase()
    const hex = `#${r}${g}${b}`
    if (ALLOWED_SET.has(hex)) {
      return hex as AllowedColorHex
    }
  }
  return null
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    textColor: {
      /** Set the text color on the current selection or stored marks */
      setTextColor: (color: AllowedColorHex) => ReturnType
      /** Remove the text color mark */
      unsetTextColor: () => ReturnType
    }
  }
}

export const TextColor = Mark.create({
  name: 'textColor',

  addOptions() {
    return {
      HTMLAttributes: {}
    }
  },

  addAttributes() {
    return {
      color: {
        default: null,
        parseHTML: (element) => {
          return normalizeAllowedColor(element.style.color)
        },
        renderHTML: (attributes) => {
          const validColor = normalizeAllowedColor(attributes.color)
          if (!validColor) {
            return {}
          }
          return {
            style: `color: ${validColor}`
          }
        }
      }
    }
  },

  parseHTML() {
    return [
      {
        style: 'color',
        getAttrs: (value) => {
          if (typeof value !== 'string') return false
          const normalized = normalizeAllowedColor(value)
          return normalized ? { color: normalized } : false
        }
      },
      {
        tag: 'span[style*="color"]',
        getAttrs: (element) => {
          if (!(element instanceof HTMLElement)) return false
          const normalized = normalizeAllowedColor(element.style.color)
          return normalized ? { color: normalized } : false
        }
      }
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes(this.options.HTMLAttributes, HTMLAttributes), 0]
  },

  addCommands() {
    return {
      setTextColor:
        (color: AllowedColorHex) =>
        ({ chain }) => {
          const validColor = normalizeAllowedColor(color)
          if (!validColor) return false
          return chain().setMark(this.name, { color: validColor }).run()
        },
      unsetTextColor:
        () =>
        ({ chain }) => {
          return chain().unsetMark(this.name).run()
        }
    }
  }
})
