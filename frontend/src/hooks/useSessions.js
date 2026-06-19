import { useState, useCallback, useEffect } from 'react'

export default function useSessions() {
  const [sessions, setSessions] = useState([])
  const [activeId, setActiveId] = useState(null)

  useEffect(() => {
    fetch('/api/v1/sessions')
      .then(r => r.json())
      .then(data => {
        if (data.sessions?.length) {
          setSessions(data.sessions)
          setActiveId(data.sessions[0].id)
        } else {
          createNewSession()
        }
      })
      .catch(() => {
        createNewSession()
      })
  }, [])

  const createNewSession = useCallback(() => {
    const id = `session_${Date.now()}`
    const s = { id, title: '新会话', createdAt: Date.now() }
    setSessions(prev => [s, ...prev])
    setActiveId(id)
    return id
  }, [])

  const createSession = useCallback(async () => {
    const id = `session_${Date.now()}`
    const s = { id, title: '新会话', createdAt: Date.now() }

    try {
      await fetch('/api/v1/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: id, title: '新会话' }),
      })
    } catch {}

    setSessions(prev => [s, ...prev])
    setActiveId(id)
    return id
  }, [])

  const updateSessionTitle = useCallback((id, title) => {
    const short = title.length > 20 ? title.slice(0, 20) : title
    setSessions(prev => prev.map(s =>
      s.id === id ? { ...s, title: short } : s
    ))
  }, [])

  const deleteSession = useCallback(async (id) => {
    if (sessions.length <= 1) return
    try {
      await fetch(`/api/v1/sessions/${id}`, { method: 'DELETE' })
    } catch {}
    setSessions(prev => prev.filter(s => s.id !== id))
    if (activeId === id) {
      const remaining = sessions.filter(s => s.id !== id)
      setActiveId(remaining[0]?.id || null)
    }
  }, [sessions, activeId])

  return { sessions, activeId, setActiveId, createSession, deleteSession, updateSessionTitle }
}
