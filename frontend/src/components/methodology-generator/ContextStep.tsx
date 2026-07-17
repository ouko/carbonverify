import type { MethodologyTemplate, PageForm, Project } from '../../types'
import { FormField } from './FormField'
import { MethodologyTemplateSelector } from './MethodologyTemplateSelector'
import { Loader2 } from 'lucide-react'

interface ContextStepProps {
  form: PageForm
  fieldErrors: Record<string, string>
  templates?: MethodologyTemplate[]
  templatesLoading: boolean
  projects?: Project[]
  projectsLoading: boolean
  selectedTemplateId: string | null
  onSelectTemplate: (template: MethodologyTemplate) => void
  onChange: (updates: Partial<PageForm>) => void
  onClearError: (key: string) => void
  onNext: () => void
}

export function ContextStep({
  form,
  fieldErrors,
  templates,
  templatesLoading,
  projects,
  projectsLoading,
  selectedTemplateId,
  onSelectTemplate,
  onChange,
  onClearError,
  onNext,
}: ContextStepProps) {
  return (
    <div className="space-y-4">
      {templatesLoading ? (
        <div className="flex items-center space-x-2 text-surface-500 dark:text-surface-400">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Loading templates...</span>
        </div>
      ) : templates && templates.length > 0 ? (
        <MethodologyTemplateSelector
          templates={templates}
          selectedId={selectedTemplateId ?? undefined}
          onSelect={onSelectTemplate}
        />
      ) : null}

      <FormField
        label="Project this methodology is for *"
        htmlFor="project_id"
        error={fieldErrors.project_id}
      >
        {projectsLoading ? (
          <div className="flex items-center space-x-2 text-surface-500 dark:text-surface-400">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Loading projects...</span>
          </div>
        ) : (
          <>
            <select
              id="project_id"
              className="input-modern"
              value={form.project_id}
              onChange={(e) => {
                onChange({ project_id: e.target.value })
                onClearError('project_id')
              }}
            >
              <option value="">Select an existing project</option>
              {projects?.map((project: Project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
            {(!projects || projects.length === 0) && (
              <p className="text-sm text-amber-600 dark:text-amber-400 mt-1">
                No projects found. Create a project first from the Projects page.
              </p>
            )}
          </>
        )}
      </FormField>

      <FormField
        label="Methodology name *"
        htmlFor="name"
        helper="Choose a clear, descriptive name. Example: Improved Cookstoves Distribution Methodology v1.0"
        error={fieldErrors.name}
      >
        <input
          id="name"
          className="input-modern"
          placeholder="e.g. Mangrove Restoration Methodology v1.0"
          value={form.name}
          onChange={(e) => {
            onChange({ name: e.target.value })
            onClearError('name')
          }}
        />
      </FormField>

      <FormField
        label="Sector / project type *"
        htmlFor="sector"
        helper="Pick the sector that best describes the project. Examples: Blue Carbon, Cookstoves, Forestry, Renewable Energy."
        error={fieldErrors.sector}
      >
        <input
          id="sector"
          className="input-modern"
          placeholder="e.g. Blue Carbon, Cookstoves"
          value={form.sector}
          onChange={(e) => {
            onChange({ sector: e.target.value })
            onClearError('sector')
          }}
        />
      </FormField>

      <FormField
        label="Activity description *"
        htmlFor="activity_description"
        helper="Include what is being measured, where it happens, and why existing methodologies may not apply."
        error={fieldErrors.activity_description}
      >
        <textarea
          id="activity_description"
          className="input-modern"
          rows={4}
          placeholder="Describe the project activity in detail (at least 10 characters)"
          value={form.activity_description}
          onChange={(e) => {
            onChange({ activity_description: e.target.value })
            onClearError('activity_description')
          }}
        />
      </FormField>

      <button className="btn-primary" onClick={onNext}>
        <span>Next: Boundaries & Data Sources</span>
      </button>
    </div>
  )
}
