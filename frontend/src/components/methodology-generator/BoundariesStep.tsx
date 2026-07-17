import type { BoundariesForm, DataSourceForm, PageForm } from '../../types'
import { FormField } from './FormField'
import { SimpleModeToggle } from './SimpleModeToggle'
import { Plus, Trash2, Loader2 } from 'lucide-react'

interface BoundariesStepProps {
  form: PageForm
  fieldErrors: Record<string, string>
  showAdvanced: boolean
  onToggleAdvanced: (show: boolean) => void
  onChangeBoundary: (key: keyof BoundariesForm, value: string) => void
  onChangeDataSource: (idx: number, key: keyof DataSourceForm, value: string) => void
  onAddDataSource: () => void
  onRemoveDataSource: (idx: number) => void
  onClearError: (key: string) => void
  onClearTemplateSelection: () => void
  onBack: () => void
  onSubmit: () => void
  isSubmitting: boolean
}

export function BoundariesStep({
  form,
  fieldErrors,
  showAdvanced,
  onToggleAdvanced,
  onChangeBoundary,
  onChangeDataSource,
  onAddDataSource,
  onRemoveDataSource,
  onClearError,
  onClearTemplateSelection,
  onBack,
  onSubmit,
  isSubmitting,
}: BoundariesStepProps) {
  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <SimpleModeToggle showAdvanced={showAdvanced} onChange={onToggleAdvanced} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField
          label="Geographic scope *"
          htmlFor="geographic_scope"
          helper="Where will the project activity take place?"
          error={fieldErrors.geographic_scope}
        >
          <input
            id="geographic_scope"
            className="input-modern"
            placeholder="e.g. Kwale County, Kenya"
            value={form.boundaries.geographic_scope}
            onChange={(e) => {
              onChangeBoundary('geographic_scope', e.target.value)
              onClearError('geographic_scope')
              onClearTemplateSelection()
            }}
          />
        </FormField>

        <FormField
          label="Temporal scope *"
          htmlFor="temporal_scope"
          helper="What time period will the methodology cover?"
          error={fieldErrors.temporal_scope}
        >
          <input
            id="temporal_scope"
            className="input-modern"
            placeholder="e.g. 2025-01-01 to 2034-12-31"
            value={form.boundaries.temporal_scope}
            onChange={(e) => {
              onChangeBoundary('temporal_scope', e.target.value)
              onClearError('temporal_scope')
              onClearTemplateSelection()
            }}
          />
        </FormField>

        <FormField
          label="Physical boundary *"
          htmlFor="physical_boundary"
          helper="What physical assets, sites, or processes are included?"
          error={fieldErrors.physical_boundary}
        >
          <input
            id="physical_boundary"
            className="input-modern"
            placeholder="e.g. project-installation sites and supply chain"
            value={form.boundaries.physical_boundary}
            onChange={(e) => {
              onChangeBoundary('physical_boundary', e.target.value)
              onClearError('physical_boundary')
              onClearTemplateSelection()
            }}
          />
        </FormField>

        {showAdvanced && (
          <FormField
            label="Greenhouse gases covered (optional)"
            htmlFor="ghg_sources_included"
            helper="Which greenhouse gases and sources are explicitly included?"
            advanced
          >
            <input
              id="ghg_sources_included"
              className="input-modern"
              placeholder="e.g. CO2, CH4 from avoided fuel combustion"
              value={form.boundaries.ghg_sources_included}
              onChange={(e) => {
                onChangeBoundary('ghg_sources_included', e.target.value)
                onClearError('ghg_sources_included')
                onClearTemplateSelection()
              }}
            />
          </FormField>
        )}
      </div>

      <FormField label="Data sources *" error={fieldErrors.data_sources}>
        <div className="space-y-3">
          {form.data_sources.map((ds, idx) => (
            <div
              key={idx}
              className="border border-surface-200 dark:border-surface-700 rounded-xl p-3 bg-surface-50 dark:bg-surface-900/50"
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <FormField
                  label="Source type *"
                  htmlFor={`source_type_${idx}`}
                  helper="e.g. satellite, IoT sensor, survey"
                  error={fieldErrors[`data_source_${idx}_type`]}
                >
                  <input
                    id={`source_type_${idx}`}
                    className="input-modern"
                    placeholder="e.g. satellite, IoT, survey"
                    value={ds.source_type}
                    onChange={(e) => {
                      onChangeDataSource(idx, 'source_type', e.target.value)
                      onClearError(`data_source_${idx}_type`)
                      onClearTemplateSelection()
                    }}
                  />
                </FormField>

                <FormField
                  label="Frequency"
                  htmlFor={`frequency_${idx}`}
                  helper="How often is the data collected?"
                >
                  <input
                    id={`frequency_${idx}`}
                    className="input-modern"
                    placeholder="e.g. monthly, annual"
                    value={ds.frequency}
                    onChange={(e) => {
                      onChangeDataSource(idx, 'frequency', e.target.value)
                      onClearTemplateSelection()
                    }}
                  />
                </FormField>

                <div className="md:col-span-2">
                  <FormField
                    label="Description *"
                    htmlFor={`description_${idx}`}
                    helper="What does this source measure and how is it used?"
                    error={fieldErrors[`data_source_${idx}_description`]}
                  >
                    <input
                      id={`description_${idx}`}
                      className="w-full input-modern"
                      placeholder="Description of what the source measures"
                      value={ds.description}
                      onChange={(e) => {
                        onChangeDataSource(idx, 'description', e.target.value)
                        onClearError(`data_source_${idx}_description`)
                        onClearTemplateSelection()
                      }}
                    />
                  </FormField>
                </div>

                {showAdvanced && (
                  <div className="md:col-span-2">
                    <FormField
                      label="Provider / quality assurance"
                      htmlFor={`provider_quality_${idx}`}
                      helper="Who provides the data and how is quality assured?"
                      advanced
                    >
                      <input
                        id={`provider_quality_${idx}`}
                        className="w-full input-modern"
                        placeholder="Provider / quality assurance notes"
                        value={ds.provider_quality}
                        onChange={(e) => {
                          onChangeDataSource(idx, 'provider_quality', e.target.value)
                          onClearTemplateSelection()
                        }}
                      />
                    </FormField>
                  </div>
                )}
              </div>
              {form.data_sources.length > 1 && (
                <button
                  className="mt-2 text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 inline-flex items-center space-x-1"
                  onClick={() => onRemoveDataSource(idx)}
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Remove</span>
                </button>
              )}
            </div>
          ))}
        </div>
        <button
          className="mt-3 text-sm text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300 inline-flex items-center space-x-1"
          onClick={onAddDataSource}
        >
          <Plus className="w-4 h-4" />
          <span>Add source</span>
        </button>
      </FormField>

      <div className="flex items-center space-x-3">
        <button className="btn-secondary" onClick={onBack}>
          Back
        </button>
        <button className="btn-primary" onClick={onSubmit} disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
          <span>Save & Analyze Gap</span>
        </button>
      </div>
    </div>
  )
}
