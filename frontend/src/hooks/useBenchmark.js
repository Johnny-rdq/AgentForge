import { useState, useEffect, useCallback } from 'react'

export default function useBenchmark() {
  const [reports, setReports] = useState([])
  const [currentReport, setCurrentReport] = useState(null)
  const [loading, setLoading] = useState(false)

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

  useEffect(() => {
    loadReports().then(filename => {
      if (filename) loadReport(filename)
    })
  }, [loadReports, loadReport])

  return { reports, currentReport, loading, loadReport }
}
