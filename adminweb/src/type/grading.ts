// Response shapes for /api/v1/grading/*. Decimal fields (mark, max_mark) come
// down as strings because Django's DecimalField serialises that way — callers
// convert to Number only at the last moment for display / input state.

export interface SubmissionComponent {
  id: number;
  code: string;
  name: string;
  is_optional: boolean;
  accepts_file: boolean;
  accepts_text: boolean;
  accepts_link: boolean;
  order: number;
}

export interface Submission {
  id: number;
  component: number;
  file_url: string | null;
  text: string;
  link: string;
  submitted_at: string;
  is_late: boolean;
}

export interface RubricCriterion {
  id: number;
  rubric: number;
  name: string;
  description: string;
  max_mark: string;
  order: number;
}

export interface Grade {
  id: number;
  submission: number;
  criterion: number;
  mark: string | null;
  comment: string;
  graded_by: number | null;
  graded_at: string;
}

export interface GroupMarkingComponentBlock {
  component: SubmissionComponent;
  submission: Submission | null;
  rubric_id: number | null;
  criteria: RubricCriterion[];
  grades: Grade[];
}

export interface GroupMarkingPayload {
  group: { id: number; group_name: string };
  year: number;
  components: GroupMarkingComponentBlock[];
}

export interface GradeBulkItem {
  submission: number;
  criterion: number;
  mark: string | null;
  comment: string;
}

// GET /api/v1/grading/components/{code}/ — one row per group, whether or not
// they've submitted. Used to power the per-component table + prev/next nav.
export interface ComponentRow {
  group_id: number;
  group_name: string;
  submission_id: number | null;
  submitted_at: string | null;
  is_late: boolean;
  criteria_graded: number;
}

export interface ComponentListPayload {
  component: SubmissionComponent;
  year: number;
  criteria_total: number;
  rows: ComponentRow[];
}
