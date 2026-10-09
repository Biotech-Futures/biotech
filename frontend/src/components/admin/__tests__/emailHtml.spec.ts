import { describe, expect, it } from 'vitest'
import { formatHtml, visualLosses } from '@/components/admin/emailHtml'

describe('visualLosses', () => {
  it('finds nothing to drop in what the visual view holds', () => {
    expect(
      visualLosses(
        '<h1 class="headline" style="color:#1a2e23">Hi</h1><p>Text <strong>bold</strong></p>' +
          '<div class="email-box" style="border:1px solid #d8e1dc"><p>Box</p></div>' +
          '<div class="email-button"><a class="cta-link" href="https://x.org">Go</a></div>' +
          '<table><tr><td>Cell</td></tr></table><ul><li>One</li></ul><hr>'
      )
    ).toEqual([])
  })

  it("names Outlook's code, layout divs and tags it can't hold", () => {
    expect(
      visualLosses(
        '<!--[if mso]><v:roundrect></v:roundrect><![endif]-->' +
          '<div style="display:inline-block; width:50%">Column</div>' +
          '<center>Centred</center><font color="red">Red</font>'
      )
    ).toEqual([
      "Outlook's button code and other HTML comments",
      'layouts made with <div>',
      'the tags <center>, <font>'
    ])
  })
})

describe('formatHtml', () => {
  it('puts each block on its own line, never between words or inline tags', () => {
    expect(formatHtml('<p>Hi <strong>Pat</strong><em>!</em></p><ul><li>One</li><li>Two</li></ul><hr><p>End</p>')).toBe(
      '<p>Hi <strong>Pat</strong><em>!</em></p>\n<ul><li>One</li>\n<li>Two</li>\n</ul>\n<hr>\n<p>End</p>'
    )
  })
})
