import { Link } from 'react-router-dom'

export default function ApplicationIntakeSuccessPage() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4">
      <div className="max-w-2xl mx-auto card p-8 text-center">
        <h1 className="text-2xl font-bold text-green-600 mb-2">Application received!</h1>
        <p className="text-gray-600 dark:text-gray-300 mb-6">
          Our AI pipeline has started reviewing your submission. Check your email for a secure link
          to upload documents and track progress.
        </p>
        <Link to="/" className="btn-secondary inline-block">Back to home</Link>
      </div>
    </div>
  )
}
