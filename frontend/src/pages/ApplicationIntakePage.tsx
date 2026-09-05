import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSubmitApplication, IntakePayload } from '../hooks/useApplications'

const SECTORS = ['cookstoves', 'forestry', 'renewable_energy', 'agriculture', 'waste']
const METHODOLOGIES = ['VM0050', 'VMR0006', 'AMS-II.G', 'TPDDTEC_v4', 'Not sure']

const INITIAL_FORM: IntakePayload = {
  applicant_email: '',
  organization_name: '',
  project_title: '',
  country: '',
  sector: '',
  proposed_methodology: '',
}

export default function ApplicationIntakePage() {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState<IntakePayload>(INITIAL_FORM)
  const navigate = useNavigate()
  const submit = useSubmitApplication()

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    submit.mutate(form, {
      onSuccess: () => navigate('/apply/success'),
    })
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4">
      <div className="max-w-2xl mx-auto card p-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Apply for Carbon Credit Verification
        </h1>
        <p className="text-gray-600 dark:text-gray-300 mb-6">
          Our AI will review your documents and guide you through the audit-ready process.
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          {step === 1 && (
            <div className="space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Email *</span>
                <input
                  type="email"
                  name="applicant_email"
                  required
                  value={form.applicant_email}
                  onChange={handleChange}
                  className="input-modern w-full mt-1"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Organization</span>
                <input
                  type="text"
                  name="organization_name"
                  value={form.organization_name}
                  onChange={handleChange}
                  className="input-modern w-full mt-1"
                />
              </label>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Project Title *</span>
                <input
                  type="text"
                  name="project_title"
                  required
                  value={form.project_title}
                  onChange={handleChange}
                  className="input-modern w-full mt-1"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Country</span>
                <input
                  type="text"
                  name="country"
                  value={form.country}
                  onChange={handleChange}
                  className="input-modern w-full mt-1"
                />
              </label>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Sector</span>
                <select name="sector" value={form.sector} onChange={handleChange} className="select-modern w-full mt-1">
                  <option value="">Select sector</option>
                  {SECTORS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Proposed Methodology</span>
                <select
                  name="proposed_methodology"
                  value={form.proposed_methodology}
                  onChange={handleChange}
                  className="select-modern w-full mt-1"
                >
                  <option value="">Select methodology</option>
                  {METHODOLOGIES.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </label>
            </div>
          )}

          <div className="flex justify-between pt-4">
            {step > 1 && (
              <button type="button" onClick={() => setStep(step - 1)} className="btn-secondary">
                Back
              </button>
            )}
            {step < 3 ? (
              <button type="button" onClick={() => setStep(step + 1)} className="btn-primary ml-auto">
                Next
              </button>
            ) : (
              <button type="submit" disabled={submit.isPending} className="btn-primary ml-auto">
                {submit.isPending ? 'Submitting...' : 'Submit Application'}
              </button>
            )}
          </div>

          {submit.isError && (
            <p className="text-red-600 text-sm">
              {submit.error?.message || 'Submission failed. Please try again.'}
            </p>
          )}
        </form>
      </div>
    </div>
  )
}
