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

  const createSession = useCallback(() => {
    const id = `session_${Date.now()}`
    const s = { id, title: '新会话', createdAt: Date.now() }

    // 后台异步注册到后端，不阻塞 UI
    fetch('/api/v1/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: id, title: '新会话' }),
    }).catch(() => {})

    setSessions(prev => [s, ...prev])
    setActiveId(id)
    return id
  }, [])

  const updateSessionTitle = useCallback((id, title) => {
    const short = title.length > 12 ? title.slice(0, 12) : title
    setSessions(prev => prev.map(s =>
      s.id === id ? { ...s, title: short } : s
    ))
  }, [])

  const deleteSession = useCallback((id) => {
    // 乐观更新：先从 UI 移除，避免卡顿感
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id)
      if (activeId === id) setActiveId(next[0]?.id || null)
      return next
    })
    // 后台异步删 API，不阻塞 UI
    fetch(`/api/v1/sessions/${id}`, { method: 'DELETE' }).catch(() => {})
  }, [activeId])

  return { sessions, activeId, setActiveId, createSession, deleteSession, updateSessionTitle }
}
