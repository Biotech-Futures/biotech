import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { USER_ROLES } from '@/utils/userOptions'

/**
 * The role lists this app shares with the backend (ported from adminweb
 * src/type/user.test.ts).
 *
 * There is no type system spanning the two languages, so a role added on one
 * side and not the other passes every portal test and type check and then
 * fails in production. This file is the portal's half of keeping them in step.
 * (It also pinned a portal copy of the backend's ROLES_WITHOUT_GEOGRAPHY until
 * main's 20 October 2026 Add user form stopped hiding geography by that list;
 * the backend's own test pins what is left of it.)
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
  // ROLES = ("student", "mentor", ...)
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
        // The role list itself, not the module that holds it: an importer
        // may read the mentor background categories from userOptions
        // without being able to ask for a role.
        readsRoleList: /USER_ROLES|UserRole/.test(source),
        namesSupport: /['"]support['"]/.test(source)
      }
    })
    expect(findings).toEqual(
      importCode.map((path) => ({ path, readsRoleList: false, namesSupport: false }))
    )
  })
})
