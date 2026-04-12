# Student Grouping And Recommendation Algorithm

This document describes the behavior implemented in [student.ts](/Users/charles/Desktop/project/biotech/admin/apps/server/src/algorithm/student.ts).

## Purpose

The module does two related jobs:

1. Build new student groups from a list of students.
2. Recommend the best existing group for each student within the same track.

The algorithm is deterministic. Given the same input, it produces the same output ordering and the same tie-breaking decisions.

## Track Assignment

Supported region tracks:

- `AUS-NSW`
- `AUS-QLD`
- `AUS-VIC`
- `AUS-WA`
- `BRA`

Any other region is mapped to `GLOBAL`.

Track resolution rules:

1. If a student already has `trackId` equal to one of the supported region tracks, use it.
2. If a student has `trackId === "GLOBAL"`, use `GLOBAL`.
3. Otherwise derive the track from `region`.
4. If `region` is not one of the supported region tracks, fall back to `GLOBAL`.

## Input Normalization

The implementation normalizes source data before scoring:

- Student IDs come from `id` or fallback `userId`.
- Names come from `name` or derived `firstName + lastName`.
- `yearLevel` falls back to `yearlevel`.
- `country` falls back to `countryName`.
- Interests may be raw strings or objects with `interestDesc` / `name`.
- Interests are trimmed, lowercased for comparison, and empty values are removed.

Missing numeric fields default to `0` when scoring:

- `yearLevel`
- `timezoneOffsetHours`

Missing `country` defaults to an empty string.

## Hard Constraints

These constraints apply to both grouping and recommendations:

- Groups must contain between 2 and 5 students.
- Students cannot be grouped across tracks.
- Shared interest overlap is mandatory.

Mandatory overlap means:

- For a proposed new group, every student must share at least one normalized interest with at least one other student in that same group.
- For recommendation into an existing group, the student must share at least one normalized interest with at least one current member of the group.

If the shared-interest rule fails, the candidate group is invalid.

## Scoring Constants

- Base score: `100`
- Regional year-gap weight: `8`
- Global year-gap weight: `6`
- Cross-country penalty in global track: `12`
- Timezone weight in global track: `2`
- Maximum timezone penalty per pair: `18`

Size bonus by resulting group size:

- Size 2: `0`
- Size 3: `3`
- Size 4: `5`
- Size 5: `6`

Two scores are used:

- `qualityScore = clamp(100 - totalPenalty, 0, 100)`
- `objectiveScore = clamp(qualityScore + sizeBonus, 0, 106)`

`qualityScore` measures compatibility. `objectiveScore` is used for ranking and adds a mild preference for larger valid groups.

## New Group Scoring

For a valid candidate group:

1. Compute all unique student pairs.
2. For each pair, calculate penalties.
3. Average each penalty type across all pairs.
4. Convert penalties into `qualityScore`.
5. Add the size bonus to get `objectiveScore`.

### Regional Track Penalty

For non-`GLOBAL` tracks, only year spread matters:

- Pair year penalty = `abs(yearA - yearB) * 8`

No country or timezone penalty is used.

### Global Track Penalty

For `GLOBAL`:

- Pair year penalty = `abs(yearA - yearB) * 6`
- If countries differ, add country penalty `12`
- If countries differ, also add timezone penalty:
  `min(18, abs(timezoneA - timezoneB) * 2)`
- If countries are the same, timezone contributes `0`

This means global ranking prioritizes:

1. Same country
2. Smaller timezone gap when country differs
3. Smaller year difference

## Per-Student Score In A Group

After a group is selected, each member receives an individual score:

1. Compare the student only against their peers in the selected group.
2. Average the penalties across those peers.
3. Convert to a `0..100` score using the same track rules.

This per-student score does not include the size bonus.

## Group Construction Strategy

Grouping is performed independently per track.

Within one track:

1. Sort remaining students by stringified ID.
2. Generate every combination of size 2 through 5.
3. Score each valid combination.
4. Sort candidates by:
   - highest `objectiveScore`
   - then highest `qualityScore`
   - then smallest year spread
   - then lexicographically smallest joined member IDs
5. Select the top candidate.
6. Remove those students from the remaining pool.
7. Repeat until fewer than 2 students remain or no valid candidate exists.

This is a greedy algorithm. It does not search for the global optimum across all possible partitions; it repeatedly takes the current best-scoring valid group.

## Unmatched Students

A student becomes unmatched when:

- no valid 2-5 person group can be formed for them in their track, or
- they are left over after higher-ranked groups were selected.

Two unmatched reason codes are returned:

- `NO_SHARED_INTEREST_IN_TRACK`
  The student has no shared-interest peers in the same track.
- `LEFTOVER_AFTER_GROUP_SELECTION`
  The student has compatible peers in the track, but no valid group remained after greedy selection removed others.

Each unmatched student receives:

- `score = 0`
- `baseScore = 100`
- `totalPenalty = 100`

## Existing Group Recommendation

Recommendations are also processed track by track.

A student is eligible for an existing group only if:

1. The student and group are in the same track.
2. The group is not full.
3. The student shares at least one interest with at least one current group member.

Default max group size is `5`, unless `group.maxSize` is provided.

### Recommendation Score

For each eligible group:

1. Compare the student against every current member.
2. Average year, country, and timezone penalties using the same rules as group scoring.
3. Compute:
   - `score = clamp(100 - totalPenalty, 0, 100)`
   - `objectiveScore = clamp(score + sizeBonus(resultingGroupSize), 0, 106)`

The size bonus is based on the group size after the student joins.

### Recommendation Ranking

Eligible groups are ranked by:

1. highest `objectiveScore`
2. highest raw `score`
3. smallest average year gap
4. for global tracks, smallest average timezone gap
5. lexicographically smallest group ID

### Recommendation Reasons

Matched recommendations produce a human-readable reason based on the winning candidate:

- Regional track: shared interest + close year match
- Global with same country: shared interest + same country
- Global with zero timezone penalty: shared interest + avoids extra timezone penalty
- Otherwise: shared interest + relatively close timezone

If no eligible group exists, the algorithm returns `recommendGroup: null` with one of these explanations:

- no groups exist in the track
- all groups are full
- no non-full group shares an interest
- generic fallback: no eligible group found in the track

## Output Ordering

The module sorts outputs for stable results:

- Groups by track, then joined student IDs
- Student scores by student ID
- Unmatched student IDs by student ID
- Unmatched reasons by student ID
- Recommendations by student ID

## Behavioral Notes

- Interest comparison is case-insensitive after trimming.
- Timezone differences matter only in `GLOBAL`, and only when countries differ.
- Regional tracks ignore country and timezone completely.
- Larger groups are preferred only when the quality loss is small enough for the size bonus to compensate.
- Equal-score situations are resolved deterministically through explicit tie-breakers.

## Verified By Tests

The current test suite in [student.test.ts](/Users/charles/Desktop/project/biotech/admin/apps/server/src/algorithm/student.test.ts) confirms:

- track separation is enforced
- mandatory interest overlap is enforced
- regional grouping prefers lower year spread
- global grouping prefers same country before timezone
- size bonus can favor larger groups
- larger groups are rejected when quality degradation is too high
- full groups are excluded from recommendation
- unmatched reasons and score breakdowns are returned
- equal-score scenarios remain deterministic
