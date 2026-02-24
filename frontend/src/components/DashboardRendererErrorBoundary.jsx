import React from 'react'

/**
 * Error boundary around Copilot-driven DynamicDashboardRenderer.
 * One bad widget or invalid layout won't break the whole page; shows fallback and retry.
 */
class DashboardRendererErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('DynamicDashboardRenderer error:', error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-800" role="alert">
          <p className="font-medium">Dashboard view couldn’t be displayed</p>
          <p className="mt-1 text-sm text-amber-700">
            One of the widgets had an error. You can try again or use the rest of the page.
          </p>
          <button
            type="button"
            onClick={this.handleRetry}
            className="mt-3 text-sm font-medium text-amber-800 underline hover:no-underline"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default DashboardRendererErrorBoundary
