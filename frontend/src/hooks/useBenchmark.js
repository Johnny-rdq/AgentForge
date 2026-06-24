import { useState, useEffect, useCallback, useRef } from 'react'

export default function useBenchmark() {
  const [reports, setReports] = useState([])
  const [currentReport, setCurrentReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [benchRunning, setBenchRunning] = useState(false)
  const [benchProgress, setBenchProgress] = useState({ current: 0, total: 50, message: '' })
  const pollRef = useRef(null)

  const loadReports = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await fetch('/api/v1/benchmark/reports')
      if (resp.ok) {
        const data = await resp.json()
        setReports(data.reports || [])
        if (data.reports?.length) {
          return data.reports[0].filename
        }
      }
    } catch {}
    setLoading(false)
    return null
  }, [])

  const loadReport = useCallback(async (filename) => {
    setLoading(true)
    try {
      const resp = await fetch(`/api/v1/benchmark/reports/${filename}`)
      if (resp.ok) {
        const data = await resp.json()
        setCurrentReport(data)
      }
    } catch {}
    setLoading(false)
  }, [])

  const runBenchmark = useCallback(async () => {
    try {
      const resp = await fetch('/api/v1/benchmark/run', { method: 'POST' })
      const data = await resp.json()
      if (data.status === 'already_running') {
        setBenchRunning(true)
        setBenchProgress(data.progress || benchProgress)
      } else if (data.status === 'started') {
        setBenchRunning(true)
        setBenchProgress({ current: 0, total: 50, message: '启动评测...' })
      }
    } catch {}
  }, [benchProgress])

  useEffect(() => {
    if (benchRunning) {
      pollRef.current = setInterval(async () => {
        try {
          const resp = await fetch('/api/v1/benchmark/status')
          const data = await resp.json()
          setBenchProgress({ current: data.current, total: data.total, message: data.message })
          if (!data.running) {
            setBenchRunning(false)
            clearInterval(pollRef.current)
            const filename = await loadReports()
            if (filename) loadReport(filename)
          }
        } catch {}
      }, 1500)
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [benchRunning, loadReports, loadReport])

  useEffect(() => {
    loadReports().then(filename => {
      if (filename) loadReport(filename)
    })
  }, [loadReports, loadReport])

  return { reports, currentReport, loading, loadReport, runBenchmark, benchRunning, benchProgress }
}
