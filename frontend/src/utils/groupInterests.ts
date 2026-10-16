/**
 * An area of interest a group's students have, how many of them have it, and
 * which: their places in the list given, from 1.
 */
export type SharedInterest = { name: string; count: number; students: number[] }

/**
 * A group's areas of interest, worked out from its students' own: each area
 * any of them has, with how many have it, the most shared first. An area every
 * student has is what the group as a whole shares. Each student counts once
 * per area, whatever the case it's written in.
 */
export function sharedInterests(studentInterests: (readonly string[] | null | undefined)[]): SharedInterest[] {
  const counts = new Map<string, SharedInterest>()
  for (const [index, interests] of studentInterests.entries()) {
    const seen = new Set<string>()
    for (const raw of interests ?? []) {
      const name = String(raw ?? '').trim()
      const key = name.toLowerCase()
      if (!name || seen.has(key)) continue
      seen.add(key)
      const entry = counts.get(key) ?? { name, count: 0, students: [] }
      entry.count += 1
      entry.students.push(index + 1)
      counts.set(key, entry)
    }
  }
  return [...counts.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
}
