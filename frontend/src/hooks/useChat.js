import { useState, useRef, useCallback } from 'react'

export default function useChat(activeSessionId) {
  const [allMessages, setAllMessages] = useState({})
  const [isStreaming, setIsStreaming] = useState(false)
  const [workflowState, setWorkflowState] = useState(null)
  const abortRef = useRef(null)

  const messages = allMessages[activeSessionId] || []

  const loadHistory = useCallback(async (threadId) => {
    if (allMessages[threadId]) return
    try {
      const resp = await fetch(`/api/v1/sessions/${threadId}/messages`)
      if (resp.ok) {
        const data = await resp.json()
        if (data.messages?.length) {
          setAllMessages(prev => ({
            ...prev,
            [threadId]: data.messages.map(m => ({
              id: m.id || Date.now(),
              role: m.role,
              content: m.content,
              isStreaming: false,
            }))
          }))
        }
      }
    } catch {}
  }, [allMessages])

  const sendMessage = useCallback(async (task, threadId) => {
    if (!task.trim() || isStreaming) return

    const userMsg = { id: Date.now(), role: 'user', content: task }
    const assistantMsg = {
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      workflow: [],
      isStreaming: true,
    }

    setAllMessages(prev => ({
      ...prev,
      [threadId]: [...(prev[threadId] || []), userMsg, assistantMsg],
    }))
    setIsStreaming(true)
    setWorkflowState({ stage: 'decompose', message: '正在分析任务...', subtasks: [] })

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const resp = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, thread_id: threadId || 'default' }),
        signal: controller.signal,
      })

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6)
            handleSSEEvent(currentEvent, data, assistantMsg.id, threadId, setAllMessages, setWorkflowState)
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setAllMessages(prev => ({
          ...prev,
          [threadId]: prev[threadId].map(m =>
            m.id === assistantMsg.id ? { ...m, content: `请求失败: ${err.message}`, isStreaming: false } : m
          )
        }))
      }
    } finally {
      setIsStreaming(false)
      setWorkflowState(null)
      setAllMessages(prev => ({
        ...prev,
        [threadId]: prev[threadId].map(m =>
          m.id === assistantMsg.id ? { ...m, isStreaming: false } : m
        )
      }))
    }
  }, [isStreaming])

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
    setWorkflowState(null)
  }, [])

  return { messages, isStreaming, workflowState, sendMessage, stopStreaming, loadHistory }
}

function handleSSEEvent(event, data, msgId, threadId, setAllMessages, setWorkflowState) {
  try {
    const parsed = JSON.parse(data)
    if (typeof parsed === 'string') {
      try { Object.assign(parsed, JSON.parse(parsed)) } catch {}
    }

    switch (event) {
      case 'thinking':
        setWorkflowState({
          stage: parsed.stage || 'execute',
          message: parsed.message || '',
          runningIds: parsed.running_ids || [],
        })
        break

      case 'subtask_update':
        setWorkflowState({
          stage: 'decompose',
          message: `拆解为 ${parsed.subtasks?.length || 0} 个子任务`,
          subtasks: parsed.subtasks || [],
        })
        break

      case 'token':
        setAllMessages(prev => ({
          ...prev,
          [threadId]: prev[threadId].map(m =>
            m.id === msgId ? { ...m, content: m.content + (typeof parsed === 'string' ? parsed : (parsed.data || '')) } : m
          )
        }))
        break

      case 'result':
        if (parsed.output) {
          setAllMessages(prev => ({
            ...prev,
            [threadId]: prev[threadId].map(m =>
              m.id === msgId ? { ...m, content: parsed.output } : m
            )
          }))
        }
        setWorkflowState(null)
        break

      case 'review_required':
        setWorkflowState({
          stage: 'review',
          message: parsed.message || '请审批子任务方案',
          taskId: parsed.task_id,
          plan: parsed.plan || [],
          needsApproval: true,
        })
        break

      case 'done':
        setWorkflowState(null)
        break

      case 'error':
        setAllMessages(prev => ({
          ...prev,
          [threadId]: prev[threadId].map(m =>
            m.id === msgId ? { ...m, content: `❌ ${parsed.message || '执行失败'}`, isStreaming: false } : m
          )
        }))
        setWorkflowState(null)
        break
    }
  } catch {}
}
