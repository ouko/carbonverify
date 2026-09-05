import { useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useApplicantPortal, useUploadApplicationDocument } from '../hooks/useApplications'

const STATUS_BADGES: Record<string, string> = {
  intake: 'badge-slate',
  documents_pending: 'badge-amber',
  pre_audit: 'badge-blue',
  gaps: 'badge-red',
  ready_for_calculation: 'badge-blue',
  ready_for_review: 'badge-blue',
  approved: 'badge-green',
  submitted: 'badge-green',
  rejected: 'badge-red',
}

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  pdd: 'Project Design Document',
  monitoring_report: 'Monitoring Report',
  kpt_results: 'KPT Results',
  sales_receipt: 'Sales Receipt',
  survey_form: 'Survey Form',
  gps_data: 'GPS Data',
  stove_inventory: 'Stove Inventory',
  other: 'Other',
}

export default function ApplicationPortalPage() {
  const [searchParams] = useSearchParams()
  const applicationId = searchParams.get('application_id') || ''
  const token = searchParams.get('token') || ''

  const portal = useApplicantPortal(applicationId, token)
  const upload = useUploadApplicationDocument(applicationId, token)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  if (!applicationId || !token) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4">
        <div className="max-w-2xl mx-auto card p-8 text-center">
          <h1 className="text-xl font-bold text-red-600 mb-2">Invalid portal link</h1>
          <p className="text-gray-600 dark:text-gray-300">
            This link is missing required information. Please use the secure link from your email.
          </p>
        </div>
      </div>
    )
  }

  if (portal.isError) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4">
        <div className="max-w-2xl mx-auto card p-8 text-center">
          <h1 className="text-xl font-bold text-red-600 mb-2">Unable to load your application</h1>
          <p className="text-gray-600 dark:text-gray-300">
            Your secure link may have expired (links are valid for 7 days) or the application was not found.
          </p>
        </div>
      </div>
    )
  }

  if (portal.isLoading || !portal.data) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4">
        <div className="max-w-2xl mx-auto card p-8 text-center text-gray-600 dark:text-gray-300">
          Loading your application…
        </div>
      </div>
    )
  }

  const data = portal.data
  const gaps = data.gap_findings || {}

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile) return
    upload.mutate(selectedFile, {
      onSuccess: () => setSelectedFile(null),
    })
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="card p-8">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{data.project_title}</h1>
              <p className="text-gray-600 dark:text-gray-300">Carbon credit verification application</p>
            </div>
            <span className={STATUS_BADGES[data.status] || 'badge-slate'}>{data.status.replace(/_/g, ' ')}</span>
          </div>

          {gaps.has_gaps && gaps.remediation && gaps.remediation.length > 0 && (
            <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <h2 className="text-sm font-semibold text-red-800 dark:text-red-300 mb-2">
                Documents still needed to pass the pre-audit:
              </h2>
              <ul className="list-disc list-inside space-y-1 text-sm text-red-700 dark:text-red-200">
                {gaps.remediation.map((r) => (
                  <li key={r.document_type}>
                    <span className="font-medium">{DOCUMENT_TYPE_LABELS[r.document_type] || r.document_type}:</span>{' '}
                    {r.guidance}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!gaps.has_gaps && data.status !== 'intake' && (
            <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
              <p className="text-sm text-green-700 dark:text-green-200">
                All required documents have been received. Our AI is preparing your application for pre-audit review.
              </p>
            </div>
          )}
        </div>

        <div className="card p-8">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Your documents</h2>
          {data.documents.length === 0 ? (
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              No documents uploaded yet. Upload your Project Design Document (PDD) and supporting evidence below.
            </p>
          ) : (
            <table className="w-full text-sm mb-4">
              <thead>
                <tr className="border-b text-left text-gray-600 dark:text-gray-400">
                  <th className="py-2">File</th>
                  <th className="py-2">Type</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.documents.map((doc) => (
                  <tr key={doc.id} className="border-b">
                    <td className="py-2 text-gray-900 dark:text-gray-100">{doc.original_filename || '—'}</td>
                    <td className="py-2 text-gray-600 dark:text-gray-400">
                      {DOCUMENT_TYPE_LABELS[doc.document_type || ''] || doc.document_type || 'Pending classification'}
                    </td>
                    <td className="py-2">
                      <span className={doc.status === 'processed' ? 'badge-green' : 'badge-amber'}>
                        {doc.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <form onSubmit={handleUpload} className="space-y-3">
            <input
              type="file"
              accept=".xlsx,.xls,.csv,.pdf,.jpg,.jpeg,.png,.webp,.txt"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-600 dark:text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 dark:file:bg-blue-900 dark:file:text-blue-200 hover:file:bg-blue-100"
            />
            <div className="flex items-center gap-3">
              <button type="submit" disabled={!selectedFile || upload.isPending} className="btn-primary">
                {upload.isPending ? 'Uploading…' : 'Upload document'}
              </button>
              {upload.isError && (
                <span className="text-red-600 text-sm">
                  {upload.error?.message || 'Upload failed. Please try again.'}
                </span>
              )}
              {upload.isSuccess && <span className="text-green-600 text-sm">Uploaded — AI review in progress.</span>}
            </div>
          </form>
        </div>

        <p className="text-center text-sm text-gray-500 dark:text-gray-400">
          Questions? Reply to your application email.{' '}
          <Link to="/" className="underline">Back to home</Link>
        </p>
      </div>
    </div>
  )
}
