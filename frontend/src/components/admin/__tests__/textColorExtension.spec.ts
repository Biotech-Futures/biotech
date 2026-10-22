import { describe, expect, it } from 'vitest'
import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import {
  ALLOWED_COLOR_HEXES,
  COLOR_SECTIONS,
  TextColor,
  normalizeAllowedColor
} from '../textColorExtension'

describe('textColorExtension palette and configuration', () => {
  it('organizes colors into PRIMARY and SECONDARY sections correctly', () => {
    expect(COLOR_SECTIONS).toHaveLength(2)
    const [primary, secondary] = COLOR_SECTIONS

    expect(primary.title).toBe('PRIMARY COLORS')
    expect(primary.colors).toEqual([
      { name: 'Dark Green', hex: '#017151' },
      { name: 'Light Green', hex: '#C3ECCA' },
      { name: 'Dark Cyan', hex: '#234142' },
      { name: 'Teal', hex: '#174243' },
      { name: 'Black', hex: '#000000' },
      { name: 'White', hex: '#FFFFFF' }
    ])

    expect(secondary.title).toBe('SECONDARY COLORS')
    expect(secondary.colors).toEqual([
      { name: 'Air Force Blue', hex: '#26697D' },
      { name: 'Mint Green', hex: '#3EAD9F' },
      { name: 'Yellow', hex: '#F3E69D' },
      { name: 'Red', hex: '#FF5050' }
    ])
  })

  it('contains all 10 allowed hexes in ALLOWED_COLOR_HEXES', () => {
    expect(ALLOWED_COLOR_HEXES).toEqual([
      '#017151',
      '#C3ECCA',
      '#234142',
      '#174243',
      '#000000',
      '#FFFFFF',
      '#26697D',
      '#3EAD9F',
      '#F3E69D',
      '#FF5050'
    ])
  })

  describe('normalizeAllowedColor', () => {
    it('normalizes valid hex colors', () => {
      expect(normalizeAllowedColor('#017151')).toBe('#017151')
      expect(normalizeAllowedColor('#c3ecca')).toBe('#C3ECCA')
      expect(normalizeAllowedColor('#234142')).toBe('#234142')
      expect(normalizeAllowedColor('#26697d')).toBe('#26697D')
      expect(normalizeAllowedColor('#3ead9f')).toBe('#3EAD9F')
      expect(normalizeAllowedColor('#f3e69d')).toBe('#F3E69D')
      expect(normalizeAllowedColor('#ff5050')).toBe('#FF5050')
    })

    it('maps legacy color hexes to their new equivalents', () => {
      expect(normalizeAllowedColor('#BAD7BB')).toBe('#C3ECCA')
      expect(normalizeAllowedColor('#bad7bb')).toBe('#C3ECCA')
      expect(normalizeAllowedColor('#39687B')).toBe('#26697D')
      expect(normalizeAllowedColor('#5EA99E')).toBe('#3EAD9F')
      expect(normalizeAllowedColor('#F1E5A6')).toBe('#F3E69D')
    })

    it('normalizes RGB strings to allowed uppercase hexes', () => {
      expect(normalizeAllowedColor('rgb(1, 113, 81)')).toBe('#017151')
      expect(normalizeAllowedColor('rgb(195, 236, 202)')).toBe('#C3ECCA')
      expect(normalizeAllowedColor('rgb(35, 65, 66)')).toBe('#234142')
    })

    it('returns null for disallowed colors', () => {
      expect(normalizeAllowedColor('#123456')).toBeNull()
      expect(normalizeAllowedColor('blue')).toBeNull()
      expect(normalizeAllowedColor('')).toBeNull()
      expect(normalizeAllowedColor(null)).toBeNull()
      expect(normalizeAllowedColor(undefined)).toBeNull()
    })
  })

  describe('TipTap TextColor mark', () => {
    it('applies text color and parses HTML correctly', () => {
      const editor = new Editor({
        extensions: [StarterKit, TextColor],
        content: '<p>Hello world</p>'
      })

      editor.commands.setTextSelection({ from: 1, to: 6 })
      editor.commands.setTextColor('#234142')

      expect(editor.getAttributes('textColor').color).toBe('#234142')
      expect(editor.getHTML()).toMatch(/<span style="color: (?:#234142|rgb\(35, 65, 66\));?">Hello<\/span>/)

      editor.destroy()
    })

    it('unsets text color mark', () => {
      const editor = new Editor({
        extensions: [StarterKit, TextColor],
        content: '<p><span style="color: #017151">Hello</span> world</p>'
      })

      editor.commands.setTextSelection({ from: 1, to: 6 })
      editor.commands.unsetTextColor()

      expect(editor.getHTML()).toBe('<p>Hello world</p>')

      editor.destroy()
    })
  })
})
