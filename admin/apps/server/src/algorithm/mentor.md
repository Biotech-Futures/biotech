# Mentor–Group Matching Algorithm

This document describes the behavior implemented in [mentor.ts](mentor.ts).

## Purpose

Recommend the best available mentor for each unmatched group.

The algorithm is deterministic. Given the same input, it produces the same assignment and tie-breaking decisions.

## Match Modes

Three modes control which mentors are eligible and whether poor-quality assignments are surfaced or suppressed.

### `balanced`

All available mentors are considered for every group. After the Gale-Shapley algorithm assigns mentors, any assignment that fails the quality threshold is **rejected** and returned as unmatched for admin review.

Quality threshold — an assignment is rejected if either:

- `interestBonus === 0` (no shared interests between mentor and group students), or
- `timezonePenalty >= TIMEZONE_MAX_PENALTY` (timezone gap of 9 or more hours).

Rejected groups receive `recommendedMentor: null` with an explanatory reason.

### `strict`

Only same-track mentors and `GLOBAL` mentors are eligible for each group. Groups with no compatible mentor in their track are left unmatched.

No quality threshold is applied — if a compatible mentor exists it will be assigned regardless of interest or timezone fit.

### `coverage`

Two-phase algorithm designed to maximise the number of matched groups.

**Phase 1** — same-track / GLOBAL Gale-Shapley. Each group proposes only to its eligible mentors (same-track or GLOBAL). This mirrors the strict-mode eligibility but is not limited to capacity-positive mentors.

**Phase 2** — cross-track fallback. Groups still unmatched after phase 1 enter a second Gale-Shapley run against all mentors that have remaining capacity after phase 1.

No quality threshold is applied in either phase. Every group that can be assigned a mentor will be, even if the match has no interest overlap or a large timezone gap.

## Track and Timezone Reference

Supported tracks and their UTC offsets used for timezone scoring:

| Track     | UTC offset |
|-----------|------------|
| `AUS-NSW` | +10        |
| `AUS-QLD` | +10        |
| `AUS-VIC` | +10        |
| `AUS-WA`  | +8         |
| `BRA`     | −3         |
| `GLOBAL`  | 0 (neutral — no timezone penalty applied) |

Tracks not present in this table default to UTC offset `0`.

## Scoring Constants

- Base score: `100`
- Track mismatch penalty: `40`
- Maximum interest overlap bonus: `30`
- Timezone weight: `2` (points per hour of difference)
- Maximum timezone penalty: `18` (capped at 9-hour gap × 2)
- Capacity bonus per remaining slot: `2`

## Per-Pair Score

For each (group, mentor) pair:

```
objectiveScore = BASE
               − trackPenalty
               + interestBonus
               − timezonePenalty
               + capacityBonus
```

### Track penalty

- `0` if mentor track equals group track, or either is `GLOBAL`.
- `40` otherwise (cross-track mismatch).

### Interest bonus

Computed from the overlap between mentor interests and the union of student interests across all group members:

```
overlapRatio = overlapCount / max(mentorInterestCount, groupInterestCount)
interestBonus = round(overlapRatio × 30)
```

Interest comparison is case-insensitive after trimming. Maximum bonus is `30` (full overlap).

### Timezone penalty

Skipped entirely when either the mentor or group track is `GLOBAL`.

Otherwise:

```
tzDist = |mentorUTCOffset − groupUTCOffset|
timezonePenalty = min(tzDist × 2, 18)
```

### Capacity bonus

```
remainingSlots = mentor.maxGroupCount − mentor.currentAcceptedCount
capacityBonus  = remainingSlots × 2
```

Mentors with zero remaining capacity are excluded from the available pool before scoring.

## Gale-Shapley (College Admissions)

Both `balanced` and `coverage` use a variant of the Gale-Shapley algorithm, where groups are the proposing side and mentors are the accepting side.

- Each group ranks its eligible mentors in descending `objectiveScore` order and proposes to them in that order across rounds.
- Each mentor holds at most `remainingSlots` groups at any time.
- When a full mentor receives a proposal with a higher score than its current worst-held group, it displaces the worst-held group in favour of the newcomer.
- Displaced groups continue proposing to their next-ranked mentor in subsequent rounds.
- The algorithm terminates when no group has an unproposed mentor remaining.

Because track mismatch penalty (40) exceeds the maximum interest bonus (30), a same-track group will always score higher than any cross-track group with the same mentor, guaranteeing that same-track groups are never displaced by cross-track proposals.

For `strict` and coverage phase 1, a per-group variant (`galeShapleyPerGroup`) is used. Each group's preference list is restricted to its own eligible mentors rather than the full mentor pool.

## Unmatched Reasons

| Condition | Reason text |
|-----------|-------------|
| No mentors registered | "No mentors are registered in the system." |
| No mentors with capacity | "No available mentors with remaining capacity." |
| Strict / no same-track mentor | "No mentors are available for track `<X>` (strict mode)." |
| All compatible mentors full | "All compatible mentors for track `<X>` are fully assigned to higher-scoring groups." |
| All mentors full (general) | "All available mentors are fully assigned to higher-scoring groups." |
| Balanced — no interest overlap | "No shared interests between the mentor and group students. Manual assignment recommended." |
| Balanced — timezone too large | "Timezone difference too large for a productive mentoring relationship. Manual assignment recommended." |

## Output Shape

Each element of the returned `MentorGroupRecommendation[]` contains:

- `group` — the original `GroupSource` (including optional `students` display field).
- `recommendedMentor` — mentor id, name, track, institution, interests, and remaining capacity after this run; `null` if unmatched.
- `reason` — human-readable explanation of why this mentor was chosen or why no match was found.
- `score` — the `objectiveScore` of the assigned pair; `0` if unmatched.
- `scoreBreakdown` — individual components: `baseScore`, `trackPenalty`, `interestBonus`, `timezonePenalty`, `capacityBonus`, `objectiveScore`.

## Behavioral Notes

- Mentors with `currentAcceptedCount >= maxGroupCount` are excluded before the algorithm runs.
- Capacity is evaluated at algorithm run time using `currentAcceptedCount` from the database. Assignments are not written to the database until an admin confirms them.
- The `students` field on `GroupSource` is display-only and is not read by the algorithm.
- Interest comparison is case-insensitive after trimming.
- GLOBAL mentors skip both track penalty and timezone penalty for every group.
- The `balanced` quality filter runs as a post-processing step after Gale-Shapley. Rejected assignments free up no mentor capacity within the run; they are simply not surfaced to the admin for confirmation.

## Verified By Tests

The current test suite in [mentor.test.ts](mentor.test.ts) confirms:

- balanced mode matches all groups when quality is acceptable
- balanced mode rejects assignments with zero interest overlap
- balanced mode rejects assignments with timezone penalty at the maximum
- strict mode leaves groups unmatched when no same-track or GLOBAL mentor exists
- coverage mode matches groups that strict mode would leave unmatched
- coverage phase 2 uses remaining capacity from phase 1
- Gale-Shapley displacement works correctly when a mentor is full
- same-track groups are never displaced by cross-track groups (penalty > max bonus)
- capacity bonus reflects mentor's available slots
- GLOBAL mentors apply no track or timezone penalty
