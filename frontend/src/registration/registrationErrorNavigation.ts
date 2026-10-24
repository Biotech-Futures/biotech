import type { RegistrationIntakeJourney } from '@/registration/registration'

const fieldStepPatterns: Record<RegistrationIntakeJourney, Array<[RegExp, number]>> = {
  student_individual: [
    [/^studentIndividual\.student\.(firstName|lastName|email|emailConfirm)$/, 0],
    [
      /^studentIndividual\.student\.(school|yearLevel|country|state|interests|pronouns|pronounsOther|profilePhoto)$/,
      1,
    ],
    [/^studentIndividual\.supervisor(\.|$)/, 2],
    [/^studentIndividual\.student\.(guardian|guardianDeferred)(\.|$)/, 2],
  ],
  student_team: [
    [/^studentTeam\.creator\.(firstName|lastName|email|emailConfirm)$/, 0],
    [
      /^studentTeam\.creator\.(school|yearLevel|country|state|interests|pronouns|pronounsOther|profilePhoto)$/,
      1,
    ],
    [/^studentTeam\.supervisor(\.|$)/, 2],
    [/^studentTeam\.creator\.(guardian|guardianDeferred)(\.|$)/, 1],
    [/^studentTeam\.(teammates|size|joinCode)(\.|$)/, 2],
  ],
  supervisor_individual: [[/^supervisorIndividual\.(student|extraStudents)(\.|$)/, 0]],
  supervisor_group: [
    [/^supervisorGroup\.(students|size)(\.|$)/, 0],
    [/^supervisorGroup\.interests(\.|$)/, 1],
  ],
  supervisor_csv: [
    [/^supervisorCsv\.(file|fileName)$/, 0],
    [/^supervisorCsv\.(rows|excludedRowNumbers|invalid)(\.|$)/, 1],
  ],
  mentor: [
    [/^mentor\.(firstName|lastName|email|country|state)$/, 0],
    [/^mentor\.(affiliation|institution|company|universityYear|fieldOfStudy)$/, 1],
    [/^mentor\.(interests|capacity|motivation)$/, 2],
  ],
  supervisor: [
    [/^supervisor\.(firstName|lastName|email)$/, 0],
    [/^supervisor\.(school|relationship|country|state|pronouns|pronounsOther|profilePhoto)$/, 1],
  ],
}

export const earliestRegistrationErrorStep = (
  journey: RegistrationIntakeJourney,
  fieldKeys: string[],
): number | null => {
  const mappedSteps = fieldKeys.flatMap((field) => {
    const match = fieldStepPatterns[journey].find(([pattern]) => pattern.test(field))
    return match ? [match[1]] : []
  })

  return mappedSteps.length ? Math.min(...mappedSteps) : null
}
