import { Mark, mergeAttributes } from '@tiptap/core'

export const ALLOWED_FONTS = ['Arial', 'Times New Roman'] as const
export type AllowedFont = (typeof ALLOWED_FONTS)[number]

export const FONT_STYLES: Record<AllowedFont, string> = {
  Arial: 'Arial, sans-serif',
  'Times New Roman': '"Times New Roman", Times, serif'
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    fontFamily: {
      /** Set the font family on the current selection or stored marks */
      setFontFamily: (fontFamily: string) => ReturnType
      /** Remove the font family mark */
      unsetFontFamily: () => ReturnType
    }
  }
}

export const FontFamily = Mark.create({
  name: 'fontFamily',

  addOptions() {
    return {
      HTMLAttributes: {}
    }
  },

  addAttributes() {
    return {
      fontFamily: {
        default: null,
        parseHTML: (element) => {
          const style = element.style.fontFamily || ''
          const lower = style.toLowerCase()
          if (lower.includes('times new roman') || lower.includes('times')) {
            return 'Times New Roman'
          }
          if (lower.includes('arial')) {
            return 'Arial'
          }
          return null
        },
        renderHTML: (attributes) => {
          if (!attributes.fontFamily) {
            return {}
          }
          const cssValue = FONT_STYLES[attributes.fontFamily as AllowedFont] || attributes.fontFamily
          return {
            style: `font-family: ${cssValue}`
          }
        }
      }
    }
  },

  parseHTML() {
    return [
      {
        style: 'font-family',
        getAttrs: (value) => {
          if (!value || typeof value !== 'string') return false
          const lower = value.toLowerCase()
          if (lower.includes('times new roman') || lower.includes('times')) {
            return { fontFamily: 'Times New Roman' }
          }
          if (lower.includes('arial')) {
            return { fontFamily: 'Arial' }
          }
          return false
        }
      },
      {
        tag: 'span[style*="font-family"]',
        getAttrs: (element) => {
          if (!(element instanceof HTMLElement)) return false
          const lower = (element.style.fontFamily || '').toLowerCase()
          if (lower.includes('times new roman') || lower.includes('times')) {
            return { fontFamily: 'Times New Roman' }
          }
          if (lower.includes('arial')) {
            return { fontFamily: 'Arial' }
          }
          return false
        }
      },
      {
        tag: 'font[face]',
        getAttrs: (element) => {
          if (!(element instanceof HTMLElement)) return false
          const face = (element.getAttribute('face') || '').toLowerCase()
          if (face.includes('times')) {
            return { fontFamily: 'Times New Roman' }
          }
          if (face.includes('arial')) {
            return { fontFamily: 'Arial' }
          }
          return false
        }
      }
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes(this.options.HTMLAttributes, HTMLAttributes), 0]
  },

  addCommands() {
    return {
      setFontFamily:
        (fontFamily: string) =>
        ({ chain }) => {
          return chain().setMark(this.name, { fontFamily }).run()
        },
      unsetFontFamily:
        () =>
        ({ chain }) => {
          return chain().unsetMark(this.name).run()
        }
    }
  }
})
