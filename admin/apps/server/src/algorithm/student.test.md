# Student Algorithm Test Inputs And Outputs

This file summarizes the test cases in [student.test.ts](/Users/charles/Desktop/project/biotech/admin/apps/server/src/algorithm/student.test.ts).

The inputs are simplified to the fields that matter for each assertion. The outputs are the expected behavior, not the full returned object.

## assignTrack

| Test | Input | Expected output |
| --- | --- | --- |
| maps known region tracks and defaults others to GLOBAL | Regions: `AUS-NSW`, `AUS-QLD`, `AUS-VIC`, `AUS-WA`, `BRA`, `USA-CA` | Supported region codes return themselves; `USA-CA` returns `GLOBAL`. |
| requires exact supported region codes | Regions: empty string, `aus-nsw`, ` AUS-NSW ` | All return `GLOBAL`. |

## scoreGroup

| Test | Input | Expected output |
| --- | --- | --- |
| rejects groups outside the 2-5 member size range | One student; six students | `scoreGroup` returns `null`. |
| allows chained interest overlap when every member matches at least one peer | Three students with interests `math`, `math/science`, `science` | Valid group; `qualityScore = 100`, `objectiveScore = 103`. |
| normalizes interest case and whitespace before checking overlap | Two students with `  Robotics ` and `robotics` | Valid group with `qualityScore = 100`. |
| uses yearlevel fallback when yearLevel is missing | Student has `yearlevel = 9`; peer has `yearLevel = 11` | Per-student `yearPenalty = 16`, score `84`. |
| caps global timezone penalty and ignores timezone when country matches | Global pairs with timezone gap 26; one cross-country pair and one same-country pair | Cross-country timezone penalty caps at `18`; same-country timezone and country penalties are `0`. |

## buildGroups

| Test | Input | Expected output |
| --- | --- | --- |
| returns empty collections for empty input | No students | Empty `groups`, `studentScores`, `unmatchedStudentIds`, and `unmatchedStudentReasons`. |
| marks a single student as unmatched with no compatible peers | One student | No groups; student unmatched with `NO_SHARED_INTEREST_IN_TRACK`, score `0`. |
| never creates groups larger than five and explains compatible leftovers | Six same-track students sharing `math` | One 5-student group; sixth student unmatched with `LEFTOVER_AFTER_GROUP_SELECTION`. |
| does not cross tracks | Two `AUS-NSW` students and two unsupported-region/global students | Two groups: one `AUS-NSW`, one `GLOBAL`. |
| keeps students unmatched when mandatory overlap cannot be satisfied | Three students with unrelated interests | No groups; all unmatched with `NO_SHARED_INTEREST_IN_TRACK`, score `0`. |
| region tracks prioritize lower year spread | Same-track students in years 7, 8, and 12 | Group contains years 7 and 8; year 12 student unmatched. |
| global scoring prefers same country, then timezone, then year | Compare global pair with near timezone but different countries against same-country pair with larger timezone gap | Same-country pair has higher quality score. |
| prefers larger valid groups when quality is close | Four same-track students with same interest and same year | One group of size 4 containing all students. |
| does not prefer larger groups when quality degradation is high | Five students sharing interest, but two are two years apart from the first three | Best selected group is smaller than 5. |
| returns deterministic output for equal-score candidates | Same four-student input run twice | Both runs return identical results. |
| marks leftover single student as unmatched | Two students share `math`; one student has `history` | One group for the `math` pair; `history` student unmatched with `NO_SHARED_INTEREST_IN_TRACK`. |
| assigns all students when valid groups exist for all of them | Three `AUS-NSW` students share `math`; two global students share `robotics` | No unmatched students; every input student appears in a group. |
| returns per-student score entries for grouped students | Two students share `math`, years 10 and 11 | One group; two student score entries, one per student. |
| builds two full groups from a common 10-student ungrouped cohort | Five `math` students and five `robotics` students, all ungrouped | Builds two 5-student groups; returns 10 student scores and no unmatched students. |

## recommendGroupsByTrack

| Test | Input | Expected output |
| --- | --- | --- |
| only recommends groups in the same track | `AUS-NSW` student with one `AUS-NSW` group and one `GLOBAL` group | Recommends the `AUS-NSW` group. |
| rejects groups with no shared interest overlap | Student has `biology`; group member has `math` | No recommendation; score `0`; reason mentions common interest. |
| prefers closer year level within a region track | Student year 10; candidate groups year 10 and year 12 | Recommends the year 10 group. |
| prefers same country over cross-country in global track | Global student from US; candidate groups in US and MX | Recommends same-country group. |
| prefers smaller timezone gap when countries differ in global track | Global student from US; candidate groups in CA and BR | Recommends closer-timezone group. |
| adds a size bonus for larger non-full groups when quality is close | One small group and one larger group with same year and interest quality | Recommends larger group; `sizeBonus = 5`. |
| does not prefer larger groups when quality is materially worse | Small close-year group vs larger far-year group | Recommends smaller close-year group. |
| ignores full groups | Existing group already has 5 members | No recommendation; reason mentions full. |
| respects custom maxSize when deciding whether a group is full | Existing group has `maxSize = 2` and two members | No recommendation; reason says all groups are full. |
| returns no-groups reason when the resolved student track has no groups | Global student with empty group list | No recommendation; reason says no existing groups are available. |
| does not recommend when the input bucket track differs from the student track | Global-resolving student placed in `AUS-NSW` bucket | No recommendation for resolved track; reason says no existing groups are available. |
| sorts recommendations by student id across multiple track buckets | Student `b` in `GLOBAL`; student `a` in `AUS-NSW` | Result order is `a`, then `b`, with their matching groups. |
| returns null recommendation with clear reason when no valid group exists | Student has `history`; only group has `math` | `recommendGroup = null`, score `0`, reason mentions common interest. |
| returns deterministic output for equal-score candidates | Equal candidate groups `a-group` and `b-group`, run twice | Both runs match; `a-group` wins by tie-breaker. |
| returns score breakdown with expected penalties and objective score | Global student US/timezone -8/year 10; group member MX/timezone -5/year 12 | Breakdown is base `100`, year `12`, country `12`, timezone `6`, total `30`, objective `70`; score `70`. |
| recommends a common batch of 10 ungrouped students across 3 existing groups | Existing groups: NSW math, NSW biology, global robotics. Ungrouped students: 4 math, 3 biology, 2 robotics, 1 history | Recommends 4 students to NSW math, 3 to NSW biology, 2 to global robotics, and leaves the history student without a recommendation. |

## Common Scenarios

### Build Groups For 10 Ungrouped Students

Input students:

| Student IDs | Track source | Year | Interests |
| --- | --- | --- | --- |
| `math-1`, `math-2`, `math-3`, `math-4`, `math-5` | default `AUS-NSW` from test helper | 10 | `math` |
| `robotics-1`, `robotics-2`, `robotics-3`, `robotics-4`, `robotics-5` | default `AUS-NSW` from test helper | 11 | `robotics` |

Expected output:

| Output field | Expected value |
| --- | --- |
| `groups.length` | `2` |
| First group | `studentIds = ["math-1", "math-2", "math-3", "math-4", "math-5"]`, `groupSize = 5` |
| Second group | `studentIds = ["robotics-1", "robotics-2", "robotics-3", "robotics-4", "robotics-5"]`, `groupSize = 5` |
| `studentScores.length` | `10` |
| `unmatchedStudentIds` | `[]` |
| `unmatchedStudentReasons` | `[]` |

### Recommend 10 Ungrouped Students Into 3 Existing Groups

Existing group input:

| Group ID | Track | Group interest | Current group students |
| --- | --- | --- | --- |
| `nsw-math` | `AUS-NSW` | `math` | `math-member-1` year 10 interest `math`; `math-member-2` year 10 interest `math` |
| `nsw-biology` | `AUS-NSW` | `biology` | `biology-member-1` year 11 interest `biology`; `biology-member-2` year 11 interest `biology` |
| `global-robotics` | `GLOBAL` | `robotics` | `robotics-member-1` country `US`, timezone `-8`, year 10, interest `robotics`; `robotics-member-2` country `US`, timezone `-8`, year 10, interest `robotics` |

Ungrouped student input:

| Student IDs | Track source | Country / timezone | Year | Interests |
| --- | --- | --- | --- | --- |
| `math-1`, `math-2`, `math-3`, `math-4` | `AUS-NSW` | default `AU` / `10` | 10 | `math` |
| `biology-1`, `biology-2`, `biology-3` | `AUS-NSW` | default `AU` / `10` | 11 | `biology` |
| `robotics-1`, `robotics-2` | unsupported region `USA-CA`, resolves to `GLOBAL` | `US` / `-8` | 10 | `robotics` |
| `history-1` | `AUS-NSW` | default `AU` / `10` | 10 | `history` |

Expected recommendation output:

| Output | Expected value |
| --- | --- |
| `result.length` | `10` |
| Students recommended to `nsw-math` | `4`: `math-1`, `math-2`, `math-3`, `math-4` |
| Students recommended to `nsw-biology` | `3`: `biology-1`, `biology-2`, `biology-3` |
| Students recommended to `global-robotics` | `2`: `robotics-1`, `robotics-2` |
| Unmatched recommendation | `history-1` has `recommendGroup = null` and `score = 0` |
| Important behavior | Recommendations are calculated per ungrouped student; the test does not consume existing group capacity across the batch. |

## formatRecommendationInput

| Test | Input | Expected output |
| --- | --- | --- |
| formats raw groupStudents and individualStudents into recommendation input | Raw NSW group rows, raw global group row, one NSW individual, one global individual | Buckets are `AUS-NSW` and `GLOBAL`; grouped rows are merged by group ID; student names and interests are normalized. |
| normalizes names, tracks, tutors, and mixed interest object shapes | Group row with null name, tutor ID, region fallback, `yearlevel`, mixed interest objects; individual row with explicit name | Group name falls back to ID; track resolves from region; tutor name becomes empty string; blank interests are removed. |
| throws when a source student has neither id nor userId | Individual source has no `id` or `userId` | Throws `Student source is missing id/userId.` |
