import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { ROLES_WITHOUT_GEOGRAPHY, USER_ROLES, roleHasGeography } from '@/utils/userOptions'

/**
 * The role lists this app shares with the backend (ported from adminweb
 * src/type/user.test.ts).
 *
 * Two of them are the same rule written twice, once per language, and there
 * is no type system spanning the gap. That is exactly how the defect behind
 * this file happened: "support" was added to the create path's exemption in
 * apps/admin/services/user.py and not to the update path's, so an admin could
 * make a support agent and then never save one again. The editor sent
 * `countryId: null` and the server answered "Country cannot be cleared".
 *
 * The backend was then consolidated onto one constant, ROLES_WITHOUT_GEOGRAPHY,
 * and pinned by a test. This file is the portal's half. Without it, adding a
 * role to the portal's list passes every portal test and type check while
 * every save of that role 400s in production.
 *
 * The backend file is read as text rather than reimplemented. A hand-copied
 * expectation would be a third copy of the rule, and a third copy is a third
 * thing to drift. Read from disk rather than imported with ?raw: Vite serves
 * only what is under the frontend root.
 */
const HERE = dirname(fileURLToPath(import.meta.url))
const REPO = resolve(HERE, '../../../..')
const read = (path: string) => readFileSync(resolve(REPO, path), 'utf8')

const backendSource = read('backend/apps/admin/services/user.py')

function backendList(name: string): string[] {
  // ROLES_WITHOUT_GEOGRAPHY = ("admin", "support")
  const match = backendSource.match(new RegExp(`^${name}\\s*=\\s*[\\(\\[]([^\\)\\]]*)[\\)\\]]`, 'm'))
  if (!match) {
    throw new Error(
      `${name} was not found in backend/apps/admin/services/user.py. If it was renamed or ` +
        'moved, this test has to follow it rather than be deleted: it is the only thing ' +
        'keeping the two languages in step.'
    )
  }
  return [...match[1].matchAll(/["']([^"']+)["']/g)].map((m) => m[1])
}

describe('the roles that carry no geography', () => {
  it('is the same list the backend exempts', () => {
    expect([...ROLES_WITHOUT_GEOGRAPHY].sort()).toEqual(backendList('ROLES_WITHOUT_GEOGRAPHY').sort())
  })

  it('exempts admin and support, and nobody else', () => {
    // Spelled out as well as compared, so a change that edits both files at
    // once still has to be a deliberate one.
    expect([...ROLES_WITHOUT_GEOGRAPHY].sort()).toEqual(['admin', 'support'])
  })

  it('roleHasGeography is the inverse of that list', () => {
    for (const role of USER_ROLES) {
      expect(roleHasGeography(role)).toBe(!ROLES_WITHOUT_GEOGRAPHY.includes(role))
    }
    expect(roleHasGeography('student')).toBe(true)
    expect(roleHasGeography('support')).toBe(false)
  })
})

describe('the roles the People page offers', () => {
  it('is exactly the backend’s list of roles', () => {
    // ROLES is the backend's list of every role the platform has. It was
    // missing "support" for two months after the role shipped. Compared both
    // ways: a role the backend has and this list lacks is a role nobody can
    // pick, which is how the portal could not create a support agent at all.
    expect([...USER_ROLES].sort()).toEqual(backendList('ROLES').sort())
  })

  it('offers support', () => {
    expect(USER_ROLES).toContain('support')
  })
})

describe('bulk import never reaches support', () => {
  it('the roles a spreadsheet may create are fewer than the roles that exist', () => {
    /* The one a bulk upload must not reach. Both endpoints that import users
     * meet in add_users_by_role, and the list they are held to is this one: a
     * CSV that could set role=support would hand queue access, on a platform
     * whose users are minors, to as many accounts as it had rows.
     *
     * Written out rather than derived, and asserted against the backend
     * source, so that widening either side has to be done in both places. */
    const importable = backendList('BULK_IMPORTABLE_ROLES')
    expect([...importable].sort()).toEqual(['mentor', 'student', 'supervisor'])
    expect(importable).not.toContain('support')
    expect(importable).not.toContain('admin')
  })

  it('the portal’s import code does not take its role from the People role list', () => {
    // The portal's two importers are single-role by construction: student
    // rows carry no role at all and mentor rows hard-code "mentor". USER_ROLES
    // now includes support, so the day an importer starts reading it (a role
    // column, a role picker) is the day a spreadsheet can ask for an agent.
    // The server would still refuse; this keeps the portal from offering it.
    const importCode = [
      'frontend/src/utils/adminStudentCsv.ts',
      'frontend/src/utils/adminMentorCsv.ts',
      'frontend/src/components/admin/users/AdminStudentImportSheet.vue',
      'frontend/src/components/admin/mentors/AdminMentorImportSheet.vue'
    ]
    const findings = importCode.map((path) => {
      const source = read(path)
      return {
        path,
        readsRoleList: /USER_ROLES|userOptions/.test(source),
        namesSupport: /['"]support['"]/.test(source)
      }
    })
    expect(findings).toEqual(
      importCode.map((path) => ({ path, readsRoleList: false, namesSupport: false }))
    )
  })
})
