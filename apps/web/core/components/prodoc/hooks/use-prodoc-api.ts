import { useMemo } from "react";
import { APIService } from "@/services/api.service";

const BASE_URL = "/api/v1/prodoc";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ProdocTemplate = {
  id: string;
  name: string;
  description: string;
  status: "draft" | "active" | "locked";
  version: number;
  parent_template: string | null;
  cover_image_url: string;
  icon: string;
  default_project_name_pattern: string;
  default_lead_role: string;
  is_public: boolean;
  require_sites: boolean;
  expected_site_count: number;
  rendered_preview: Record<string, unknown>;
  workspace: string;
  created_at: string;
  updated_at: string;
};

export type ProdocTemplateSection = {
  id: string;
  template: string;
  name: string;
  description: string;
  sequence: number;
  created_at: string;
  updated_at: string;
};

export type ProdocTemplateTask = {
  id: string;
  template: string;
  section: string | null;
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
  created_at: string;
  updated_at: string;
};

export type ProdocTemplateTaskDependency = {
  id: string;
  template: string;
  blocker_task: string;
  blocked_task: string;
  relation_type: string;
  created_at: string;
  updated_at: string;
};

export type ProdocMigrationRequirement = {
  id: string;
  workspace: string;
  name: string;
  slug: string;
  description: string;
  category: string;
  default_owner_role: string;
  created_at: string;
  updated_at: string;
};

export type ProdocThirdPartyTool = {
  id: string;
  workspace: string;
  name: string;
  slug: string;
  description: string;
  category: string;
  default_owner_role: string;
  created_at: string;
  updated_at: string;
};

export type ProdocSite = {
  id: string;
  project: string;
  name: string;
  address: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  go_live_date: string | null;
  created_at: string;
  updated_at: string;
};

export type ProdocWave = {
  id: string;
  project: string;
  template_wave_slug: string;
  name: string;
  sequence: number;
  description: string;
  plane_module: string | null;
  created_at: string;
  updated_at: string;
  sites: string[];
};

export type ProdocMaterializationJob = {
  id: string;
  project: string;
  template: string;
  status: "pending" | "running" | "success" | "failed";
  progress: Record<string, unknown>;
  error_message: string;
  tasks_created_so_far: number;
  tasks_total: number;
  created_at: string;
  updated_at: string;
};

export type ProdocProjectSettings = {
  id: string;
  project: string;
  prodoc_template_source: string | null;
  created_at: string;
  updated_at: string;
};

export type DryRunResult = {
  waves: Record<string, unknown>[];
  tasks: Record<string, unknown>[];
  dependencies: Record<string, unknown>[];
  errors: string[];
  estimated_duration_days: number;
};

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

class ProdocApiService extends APIService {
  constructor() {
    super(BASE_URL);
  }

  // -- Templates --

  async listTemplates(workspaceSlug: string): Promise<ProdocTemplate[]> {
    return this.get(`/workspaces/${workspaceSlug}/templates/`).then((r) => r.data);
  }

  async getTemplate(workspaceSlug: string, templateId: string): Promise<ProdocTemplate> {
    return this.get(`/workspaces/${workspaceSlug}/templates/${templateId}/`).then((r) => r.data);
  }

  async createTemplate(workspaceSlug: string, data: Partial<ProdocTemplate>): Promise<ProdocTemplate> {
    return this.post(`/workspaces/${workspaceSlug}/templates/`, data).then((r) => r.data);
  }

  async updateTemplate(
    workspaceSlug: string,
    templateId: string,
    data: Partial<ProdocTemplate>
  ): Promise<ProdocTemplate> {
    return this.patch(`/workspaces/${workspaceSlug}/templates/${templateId}/`, data).then((r) => r.data);
  }

  async deleteTemplate(workspaceSlug: string, templateId: string): Promise<void> {
    return this.delete(`/workspaces/${workspaceSlug}/templates/${templateId}/`).then(() => undefined);
  }

  // -- Template sections --

  async listSections(workspaceSlug: string, templateId: string): Promise<ProdocTemplateSection[]> {
    return this.get(`/workspaces/${workspaceSlug}/templates/${templateId}/sections/`).then((r) => r.data);
  }

  async createSection(
    workspaceSlug: string,
    templateId: string,
    data: Partial<ProdocTemplateSection>
  ): Promise<ProdocTemplateSection> {
    return this.post(`/workspaces/${workspaceSlug}/templates/${templateId}/sections/`, data).then((r) => r.data);
  }

  async updateSection(
    workspaceSlug: string,
    templateId: string,
    sectionId: string,
    data: Partial<ProdocTemplateSection>
  ): Promise<ProdocTemplateSection> {
    return this.patch(`/workspaces/${workspaceSlug}/templates/${templateId}/sections/${sectionId}/`, data).then(
      (r) => r.data
    );
  }

  async deleteSection(workspaceSlug: string, templateId: string, sectionId: string): Promise<void> {
    return this.delete(`/workspaces/${workspaceSlug}/templates/${templateId}/sections/${sectionId}/`).then(
      () => undefined
    );
  }

  // -- Template tasks --

  async listTasks(workspaceSlug: string, templateId: string): Promise<ProdocTemplateTask[]> {
    return this.get(`/workspaces/${workspaceSlug}/templates/${templateId}/tasks/`).then((r) => r.data);
  }

  async createTask(
    workspaceSlug: string,
    templateId: string,
    data: Partial<ProdocTemplateTask>
  ): Promise<ProdocTemplateTask> {
    return this.post(`/workspaces/${workspaceSlug}/templates/${templateId}/tasks/`, data).then((r) => r.data);
  }

  async updateTask(
    workspaceSlug: string,
    templateId: string,
    taskId: string,
    data: Partial<ProdocTemplateTask>
  ): Promise<ProdocTemplateTask> {
    return this.patch(`/workspaces/${workspaceSlug}/templates/${templateId}/tasks/${taskId}/`, data).then(
      (r) => r.data
    );
  }

  async deleteTask(workspaceSlug: string, templateId: string, taskId: string): Promise<void> {
    return this.delete(`/workspaces/${workspaceSlug}/templates/${templateId}/tasks/${taskId}/`).then(() => undefined);
  }

  // -- Template dependencies --

  async listDependencies(workspaceSlug: string, templateId: string): Promise<ProdocTemplateTaskDependency[]> {
    return this.get(`/workspaces/${workspaceSlug}/templates/${templateId}/dependencies/`).then((r) => r.data);
  }

  async createDependency(
    workspaceSlug: string,
    templateId: string,
    data: Partial<ProdocTemplateTaskDependency>
  ): Promise<ProdocTemplateTaskDependency> {
    return this.post(`/workspaces/${workspaceSlug}/templates/${templateId}/dependencies/`, data).then((r) => r.data);
  }

  async deleteDependency(workspaceSlug: string, templateId: string, dependencyId: string): Promise<void> {
    return this.delete(`/workspaces/${workspaceSlug}/templates/${templateId}/dependencies/${dependencyId}/`).then(
      () => undefined
    );
  }

  // -- Migration requirements --

  async listMigrationRequirements(workspaceSlug: string): Promise<ProdocMigrationRequirement[]> {
    return this.get(`/workspaces/${workspaceSlug}/migration-requirements/`).then((r) => r.data);
  }

  async createMigrationRequirement(
    workspaceSlug: string,
    data: Partial<ProdocMigrationRequirement>
  ): Promise<ProdocMigrationRequirement> {
    return this.post(`/workspaces/${workspaceSlug}/migration-requirements/`, data).then((r) => r.data);
  }

  async updateMigrationRequirement(
    workspaceSlug: string,
    id: string,
    data: Partial<ProdocMigrationRequirement>
  ): Promise<ProdocMigrationRequirement> {
    return this.patch(`/workspaces/${workspaceSlug}/migration-requirements/${id}/`, data).then((r) => r.data);
  }

  async deleteMigrationRequirement(workspaceSlug: string, id: string): Promise<void> {
    return this.delete(`/workspaces/${workspaceSlug}/migration-requirements/${id}/`).then(() => undefined);
  }

  // -- Third-party tools --

  async listThirdPartyTools(workspaceSlug: string): Promise<ProdocThirdPartyTool[]> {
    return this.get(`/workspaces/${workspaceSlug}/third-party-tools/`).then((r) => r.data);
  }

  async createThirdPartyTool(
    workspaceSlug: string,
    data: Partial<ProdocThirdPartyTool>
  ): Promise<ProdocThirdPartyTool> {
    return this.post(`/workspaces/${workspaceSlug}/third-party-tools/`, data).then((r) => r.data);
  }

  async updateThirdPartyTool(
    workspaceSlug: string,
    id: string,
    data: Partial<ProdocThirdPartyTool>
  ): Promise<ProdocThirdPartyTool> {
    return this.patch(`/workspaces/${workspaceSlug}/third-party-tools/${id}/`, data).then((r) => r.data);
  }

  async deleteThirdPartyTool(workspaceSlug: string, id: string): Promise<void> {
    return this.delete(`/workspaces/${workspaceSlug}/third-party-tools/${id}/`).then(() => undefined);
  }

  // -- Sites --

  async listSites(workspaceSlug: string, projectId: string): Promise<ProdocSite[]> {
    return this.get(`/workspaces/${workspaceSlug}/projects/${projectId}/sites/`).then((r) => r.data);
  }

  async createSite(workspaceSlug: string, projectId: string, data: Partial<ProdocSite>): Promise<ProdocSite> {
    return this.post(`/workspaces/${workspaceSlug}/projects/${projectId}/sites/`, data).then((r) => r.data);
  }

  async updateSite(
    workspaceSlug: string,
    projectId: string,
    siteId: string,
    data: Partial<ProdocSite>
  ): Promise<ProdocSite> {
    return this.patch(`/workspaces/${workspaceSlug}/projects/${projectId}/sites/${siteId}/`, data).then((r) => r.data);
  }

  async deleteSite(workspaceSlug: string, projectId: string, siteId: string): Promise<void> {
    return this.delete(`/workspaces/${workspaceSlug}/projects/${projectId}/sites/${siteId}/`).then(() => undefined);
  }

  // -- Waves --

  async listWaves(workspaceSlug: string, projectId: string): Promise<ProdocWave[]> {
    return this.get(`/workspaces/${workspaceSlug}/projects/${projectId}/waves/`).then((r) => r.data);
  }

  async getWave(workspaceSlug: string, projectId: string, waveId: string): Promise<ProdocWave> {
    return this.get(`/workspaces/${workspaceSlug}/projects/${projectId}/waves/${waveId}/`).then((r) => r.data);
  }

  // -- Materialization --

  async materialize(
    workspaceSlug: string,
    projectId: string,
    data: { template_id: string; dry_run?: boolean }
  ): Promise<DryRunResult | ProdocMaterializationJob> {
    return this.post(`/workspaces/${workspaceSlug}/projects/${projectId}/materialize/`, data).then((r) => r.data);
  }

  async getMaterializationJob(
    workspaceSlug: string,
    projectId: string,
    jobId: string
  ): Promise<ProdocMaterializationJob> {
    return this.get(`/workspaces/${workspaceSlug}/projects/${projectId}/materialization-jobs/${jobId}/`).then(
      (r) => r.data
    );
  }

  // -- Project settings --

  async getProjectSettings(workspaceSlug: string, projectId: string): Promise<ProdocProjectSettings> {
    return this.get(`/workspaces/${workspaceSlug}/projects/${projectId}/settings/`).then((r) => r.data);
  }
}

const prodocApiService = new ProdocApiService();

export function useProdocApi(): ProdocApiService {
  return useMemo(() => prodocApiService, []);
}
