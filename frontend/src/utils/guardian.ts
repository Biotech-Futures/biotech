/**
 * A student created without a guardian gets their own name copied into the
 * guardian fields (the columns can't be blank), so that name isn't a guardian.
 */
export const isPlaceholderGuardian = (
  guardianFirstName: string | null | undefined,
  guardianLastName: string | null | undefined,
  studentFirstName: string | null | undefined,
  studentLastName: string | null | undefined
) => {
  const guardian = `${guardianFirstName || ''} ${guardianLastName || ''}`.trim().toLowerCase()
  const student = `${studentFirstName || ''} ${studentLastName || ''}`.trim().toLowerCase()
  return !guardian || guardian === student
}
