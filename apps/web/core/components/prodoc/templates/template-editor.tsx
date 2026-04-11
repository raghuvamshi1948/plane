import { useCallback, useEffect, useMemo } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { useNavigate } from "react-router";
import useSWR from "swr";
import { ChevronLeft } from "lucide-react";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Collapsible } from "@plane/ui";
import { ProdocFeatureGate } from "@/components/prodoc/components/prodoc-feature-gate";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";
import type { ProdocTemplate } from "@/components/prodoc/hooks/use-prodoc-api";
import type { TemplateFormValues } from "./template-form-types";
import { MetadataSection } from "./sections/metadata-section";
import { ProjectDefaultsSection } from "./sections/project-defaults-section";
import { WavesSection } from "./sections/waves-section";
import { TasksSection } from "./sections/tasks-section";
import { DependenciesSection } from "./sections/dependencies-section";
import { SitesSection } from "./sections/sites-section";
import { VersionStatusSection } from "./sections/version-status-section";
import { ActionButtons } from "./action-buttons";
import { detectCycle } from "./sections/dependencies-section";

type Props = {
  workspaceSlug: string;
  templateId?: string;
  parentTemplateId?: string;
};

const DEFAULT_VALUES: TemplateFormValues = {
  name: "",
  description: "",
  cover_image_url: "",
  icon: "",
  default_project_name_pattern: "",
  default_lead_role: "",
  is_public: false,
  require_sites: false,
  expected_site_count: 1,
  waves: [],
  tasks: [],
  dependencies: [],
};

function TemplateEditorInner({ workspaceSlug, templateId, parentTemplateId }: Props) {
  const api = useProdocApi();
  const navigate = useNavigate();

  const { data: template } = useSWR(templateId ? `PRODOC_TEMPLATE_${workspaceSlug}_${templateId}` : null, () =>
    api.getTemplate(workspaceSlug, templateId!)
  );

  const { data: tasks } = useSWR(templateId ? `PRODOC_TEMPLATE_TASKS_${templateId}` : null, () =>
    api.listTasks(workspaceSlug, templateId!)
  );

  const { data: deps } = useSWR(templateId ? `PRODOC_TEMPLATE_DEPS_${templateId}` : null, () =>
    api.listDependencies(workspaceSlug, templateId!)
  );

  const { data: migReqs } = useSWR(`PRODOC_MIGRATION_REQS_${workspaceSlug}`, () =>
    api.listMigrationRequirements(workspaceSlug)
  );

  const { data: tools } = useSWR(`PRODOC_THIRD_PARTY_TOOLS_${workspaceSlug}`, () =>
    api.listThirdPartyTools(workspaceSlug)
  );

  const migReqSlugs = useMemo(() => migReqs?.map((r) => r.slug) ?? [], [migReqs]);
  const toolSlugs = useMemo(() => tools?.map((t) => t.slug) ?? [], [tools]);

  const isLocked = template?.status === "locked";

  const methods = useForm<TemplateFormValues>({ defaultValues: DEFAULT_VALUES, mode: "onChange" });
  const {
    reset,
    handleSubmit,
    formState: { isValid, isSubmitting },
  } = methods;

  useEffect(() => {
    if (template && tasks) {
      const wavesFromPreview =
        (
          template.rendered_preview as {
            waves?: { name: string; slug: string; sequence: number; description: string }[];
          }
        )?.waves ?? [];

      reset({
        name: template.name,
        description: template.description,
        cover_image_url: template.cover_image_url ?? "",
        icon: template.icon ?? "",
        default_project_name_pattern: template.default_project_name_pattern ?? "",
        default_lead_role: template.default_lead_role ?? "",
        is_public: template.is_public ?? false,
        require_sites: template.require_sites ?? false,
        expected_site_count: template.expected_site_count ?? 1,
        waves: wavesFromPreview,
        tasks: tasks.map((t) => ({
          id: t.id,
          name: t.name,
          slug: t.slug,
          description: t.description,
          wave_slug: t.wave_slug,
          duration_days: t.duration_days,
          offset_days: t.offset_days,
          assignee_role_label: t.assignee_role_label,
          migration_requirement_slugs: t.migration_requirement_slugs ?? [],
          third_party_tool_slugs: t.third_party_tool_slugs ?? [],
          sequence: t.sequence,
        })),
        dependencies:
          deps?.map((d) => ({
            id: d.id,
            blocker_task_slug: tasks.find((t) => t.id === d.blocker_task)?.slug ?? "",
            blocked_task_slug: tasks.find((t) => t.id === d.blocked_task)?.slug ?? "",
            relation_type: d.relation_type ?? "blocked_by",
          })) ?? [],
      });
    }
  }, [template, tasks, deps, reset]);

  const validateAndSave = useCallback(
    async (data: TemplateFormValues, publish: boolean) => {
      const cycleError = detectCycle(data.dependencies);
      if (cycleError) {
        setToast({ type: TOAST_TYPE.ERROR, title: "Validation error", message: cycleError });
        return;
      }

      const waveSlugs = new Set(data.waves.map((w) => w.slug));
      const dupeWaveSlugs = data.waves.filter((w, i, arr) => arr.findIndex((o) => o.slug === w.slug) !== i);
      if (dupeWaveSlugs.length > 0) {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Validation error",
          message: `Duplicate wave slug: "${dupeWaveSlugs[0].slug}"`,
        });
        return;
      }

      const taskSlugs = data.tasks.map((t) => t.slug);
      const dupeTaskSlugs = taskSlugs.filter((s, i) => taskSlugs.indexOf(s) !== i);
      if (dupeTaskSlugs.length > 0) {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Validation error",
          message: `Duplicate task slug: "${dupeTaskSlugs[0]}"`,
        });
        return;
      }

      for (const task of data.tasks) {
        if (task.wave_slug && !waveSlugs.has(task.wave_slug)) {
          setToast({
            type: TOAST_TYPE.ERROR,
            title: "Validation error",
            message: `Task "${task.name}" references unknown wave slug "${task.wave_slug}"`,
          });
          return;
        }
      }

      try {
        const templatePayload: Partial<ProdocTemplate> = {
          name: data.name,
          description: data.description,
          cover_image_url: data.cover_image_url,
          icon: data.icon,
          default_project_name_pattern: data.default_project_name_pattern,
          default_lead_role: data.default_lead_role,
          is_public: data.is_public,
          require_sites: data.require_sites,
          expected_site_count: data.expected_site_count,
        };

        if (publish) {
          (templatePayload as Record<string, unknown>).status = "locked";
        }

        let savedTemplate: ProdocTemplate;
        if (templateId) {
          savedTemplate = await api.updateTemplate(workspaceSlug, templateId, templatePayload);
        } else {
          if (parentTemplateId) {
            (templatePayload as Record<string, unknown>).parent_template = parentTemplateId;
          }
          savedTemplate = await api.createTemplate(workspaceSlug, templatePayload);
        }

        // Sync tasks (parallel)
        const existingTasks = tasks ?? [];
        const taskUpserts = data.tasks.map((taskData) => {
          const existing = existingTasks.find((t) => t.id === (taskData as { id?: string }).id);
          if (existing) {
            return api.updateTask(workspaceSlug, savedTemplate.id, existing.id, taskData);
          }
          return api.createTask(workspaceSlug, savedTemplate.id, taskData);
        });
        await Promise.all(taskUpserts);

        // Delete removed tasks (parallel)
        const formTaskIds = new Set(data.tasks.map((t) => (t as { id?: string }).id).filter(Boolean));
        const taskDeletes = existingTasks
          .filter((existing) => !formTaskIds.has(existing.id))
          .map((existing) => api.deleteTask(workspaceSlug, savedTemplate.id, existing.id));
        await Promise.all(taskDeletes);

        // Sync dependencies: delete all existing, re-create (parallel)
        const existingDeps = deps ?? [];
        await Promise.all(existingDeps.map((dep) => api.deleteDependency(workspaceSlug, savedTemplate.id, dep.id)));

        const savedTasks = await api.listTasks(workspaceSlug, savedTemplate.id);
        const depCreates = data.dependencies
          .map((depData) => {
            const blockerId = savedTasks.find((t) => t.slug === depData.blocker_task_slug)?.id;
            const blockedId = savedTasks.find((t) => t.slug === depData.blocked_task_slug)?.id;
            if (blockerId && blockedId) {
              return api.createDependency(workspaceSlug, savedTemplate.id, {
                blocker_task: blockerId,
                blocked_task: blockedId,
                relation_type: depData.relation_type,
              });
            }
            return null;
          })
          .filter(Boolean);
        await Promise.all(depCreates);

        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: publish ? "Template published" : "Template saved",
        });
        navigate(`/${workspaceSlug}/settings/prodoc/templates`);
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Failed to save template";
        setToast({ type: TOAST_TYPE.ERROR, title: "Error", message });
      }
    },
    [templateId, parentTemplateId, workspaceSlug, api, navigate, tasks, deps]
  );

  const handleSaveDraft = handleSubmit((data) => validateAndSave(data, false));
  const handlePublish = handleSubmit((data) => validateAndSave(data, true));

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-subtle px-6 py-3">
        <button
          type="button"
          className="rounded p-1 text-secondary hover:bg-surface-2 hover:text-primary"
          onClick={() => navigate(`/${workspaceSlug}/settings/prodoc/templates`)}
        >
          <ChevronLeft className="size-5" />
        </button>
        <h2 className="text-16 font-medium">{templateId ? "Edit template" : "New template"}</h2>
      </div>

      <FormProvider {...methods}>
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="mx-auto max-w-3xl space-y-4">
            {template && (
              <VersionStatusSection
                version={template.version}
                status={template.status}
                templateId={template.id}
                workspaceSlug={workspaceSlug}
              />
            )}

            <Collapsible
              title={<SectionTitle label="Metadata" required />}
              defaultOpen
              buttonClassName="flex w-full items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3 text-left hover:bg-surface-2"
            >
              <div className="px-4 pt-2 pb-4">
                <MetadataSection />
              </div>
            </Collapsible>

            <Collapsible
              title={<SectionTitle label="Project Defaults" />}
              buttonClassName="flex w-full items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3 text-left hover:bg-surface-2"
            >
              <div className="px-4 pt-2 pb-4">
                <ProjectDefaultsSection />
              </div>
            </Collapsible>

            <Collapsible
              title={<SectionTitle label="Waves" required />}
              defaultOpen
              buttonClassName="flex w-full items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3 text-left hover:bg-surface-2"
            >
              <div className="px-4 pt-2 pb-4">
                <WavesSection />
              </div>
            </Collapsible>

            <Collapsible
              title={<SectionTitle label="Tasks" required />}
              defaultOpen
              buttonClassName="flex w-full items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3 text-left hover:bg-surface-2"
            >
              <div className="px-4 pt-2 pb-4">
                <TasksSection migrationRequirementSlugs={migReqSlugs} thirdPartyToolSlugs={toolSlugs} />
              </div>
            </Collapsible>

            <Collapsible
              title={<SectionTitle label="Dependencies" />}
              buttonClassName="flex w-full items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3 text-left hover:bg-surface-2"
            >
              <div className="px-4 pt-2 pb-4">
                <DependenciesSection />
              </div>
            </Collapsible>

            <Collapsible
              title={<SectionTitle label="Sites Configuration" />}
              buttonClassName="flex w-full items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3 text-left hover:bg-surface-2"
            >
              <div className="px-4 pt-2 pb-4">
                <SitesSection />
              </div>
            </Collapsible>
          </div>
        </div>

        <ActionButtons
          onSaveDraft={handleSaveDraft}
          onPublish={handlePublish}
          onCancel={() => navigate(`/${workspaceSlug}/settings/prodoc/templates`)}
          isSubmitting={isSubmitting}
          isValid={isValid}
          isLocked={isLocked}
        />
      </FormProvider>
    </div>
  );
}

function SectionTitle({ label, required }: { label: string; required?: boolean }) {
  return (
    <span className="text-14 font-medium text-primary">
      {label}
      {required && <span className="ml-1 text-danger-primary">*</span>}
    </span>
  );
}

export function TemplateEditor(props: Props) {
  return (
    <ProdocFeatureGate>
      <TemplateEditorInner {...props} />
    </ProdocFeatureGate>
  );
}
