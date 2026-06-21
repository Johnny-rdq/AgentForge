import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen bg-zinc-950 text-zinc-400 px-4">
          <div className="w-16 h-16 bg-red-600/20 rounded-2xl flex items-center justify-center mb-4 border border-red-800">
            <span className="text-2xl">⚠️</span>
          </div>
          <h2 className="text-lg font-semibold text-zinc-300 mb-2">页面出错了</h2>
          <p className="text-sm text-zinc-500 text-center max-w-md mb-4">
            {this.state.error?.message || '发生了未预期的错误'}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null })
              window.location.reload()
            }}
            className="px-4 py-2 text-sm bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors"
          >
            刷新页面
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
