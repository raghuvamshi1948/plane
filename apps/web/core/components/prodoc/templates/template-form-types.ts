export type WaveFormValues = {
  id?: string;
  name: string;
  slug: string;
  sequence: number;
  description: string;
};

export type TaskFormValues = {
  id?: string;
  name: string;
  slug: string;
  description: string;
  wave_slug: string;
  duration_days: number;
  offset_days: number;
  assignee_role_label: string;
  migration_requirement_slugs: string[];
  third_party_tool_slugs: string[];
  sequence: number;
};

export type DependencyFormValues = {
  id?: string;
  blocker_task_slug: string;
  blocked_task_slug: string;
  relation_type: string;
};

export type TemplateFormValues = {
  name: string;
  description: string;
  cover_image_url: string;
  icon: string;
  default_project_name_pattern: string;
  default_lead_role: string;
  is_public: boolean;
  require_sites: boolean;
  expected_site_count: number;
  waves: WaveFormValues[];
  tasks: TaskFormValues[];
  dependencies: DependencyFormValues[];
};
