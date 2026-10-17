export interface MutualInterestItem {
  name: string
  count: number
}

export interface MemberWithInterests {
  interests?: string[] | null
}

/**
 * Compute overlapping interests shared by 2 or more members.
 *
 * Deduplicates interests per member, counts frequency across members,
 * filters for count >= 2, and sorts by count descending, then case-insensitive
 * name ascending (matching backend `compute_mutual_interests` in group.py).
 */
export function computeMutualInterests(
  members: Array<MemberWithInterests | null | undefined>
): MutualInterestItem[] {
  if (!members || !members.length) {
    return []
  }

  const countMap = new Map<string, number>()
  for (const member of members) {
    if (!member || !member.interests) continue
    const ints = new Set(
      Array.isArray(member.interests)
        ? member.interests
            .filter((i): i is string => typeof i === 'string')
            .map((i) => i.trim())
            .filter((i) => i.length > 0)
        : []
    )
    for (const interest of ints) {
      countMap.set(interest, (countMap.get(interest) || 0) + 1)
    }
  }

  const result: MutualInterestItem[] = []
  for (const [name, count] of countMap.entries()) {
    if (count >= 2) {
      result.push({ name, count })
    }
  }

  result.sort((a, b) => {
    if (b.count !== a.count) {
      return b.count - a.count
    }
    const aLower = a.name.toLowerCase()
    const bLower = b.name.toLowerCase()
    if (aLower < bLower) return -1
    if (aLower > bLower) return 1
    return a.name.localeCompare(b.name)
  })

  return result
}
