import { useState, useRef, useCallback, useEffect } from 'react'

export default function useChat(activeSessionId) {
  const [allMessages, setAllMessages] = useState({})
  const [isStreaming, setIsStreaming] = useState(false)
  const [workflowState, setWorkflowState] = useState(null)
  const [workflowSessionId, setWorkflowSessionId] = useState(null)
  const abortRef = useRef(null)
  const needsApprovalRef = useRef(false)

  const messages = allMessages[activeSessionId] || []

  // 切换会话时清空执行过程状态（防止跨会话污染）
  useEffect(() => {
    if (activeSessionId !== workflowSessionId && workflowSessionId !== null) {
      setWorkflowState(null)
    }
  }, [activeSessionId, workflowSessionId])

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
              files: m.files || [],
              isStreaming: false,
              elapsed_ms: m.elapsed_ms || 0,
            }))
          }))
        }
      }
    } catch {}
  }, [allMessages])

  const sendMessage = useCallback(async (task, threadId, files = []) => {
    if ((!task.trim() && !files.length) || isStreaming) return

    // 上传文件，记录路径和元数据
    const uploaded = []
    let fileContext = ''
    if (files.length) {
      for (const f of files) {
        try {
          const fd = new FormData()
          fd.append('file', f)
          const upResp = await fetch('/api/v1/upload', { method: 'POST', body: fd })
          if (upResp.ok) {
            const upData = await upResp.json()
            uploaded.push({ ...upData, originalName: f.name })
            fileContext += `\n\n（用户上传了文件「${upData.filename}」，路径「${upData.saved_path}」，请用 read_file 读取并分析其内容）`
          }
        } catch {}
      }
    }

    // 后端 上传文件的元数据 JSON（不含本地预览 URL，仅持久化所需字段）
    const filesMeta = uploaded.map(f => ({ filename: f.filename, originalName: f.originalName, saved_path: f.saved_path }))
    const filesJson = JSON.stringify(filesMeta)

    const displayContent = (task.trim() || '请分析我上传的文件') + fileContext
    const userMsg = { id: Date.now(), role: 'user', content: task.trim() || `📎 上传了 ${files.length} 个文件`, files: uploaded }
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
    setWorkflowSessionId(threadId)
    needsApprovalRef.current = false

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const resp = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: displayContent, thread_id: threadId || 'default', files_json: filesJson }),
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
            handleSSEEvent(currentEvent, data, assistantMsg.id, threadId, setAllMessages, setWorkflowState, setIsStreaming, needsApprovalRef)
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
      if (needsApprovalRef.current) {
        // 后端 审批模式：保留 state 等待用户操作，只更新消息流式状态
        setAllMessages(prev => ({
          ...prev,
          [threadId]: prev[threadId].map(m =>
            m.id === assistantMsg.id ? { ...m, isStreaming: false } : m
          )
        }))
      } else {
        setWorkflowState(null)
        setWorkflowSessionId(null)
        setAllMessages(prev => ({
          ...prev,
          [threadId]: prev[threadId].map(m =>
            m.id === assistantMsg.id ? { ...m, isStreaming: false } : m
          )
        }))
      }
    }
  }, [isStreaming])

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
    setWorkflowState(null)
    setWorkflowSessionId(null)
    needsApprovalRef.current = false
  }, [])

  const approveTask = useCallback(async (taskId, action, modifications) => {
    // 找到当前会话的助手消息 ID 用于更新
    const threadId = activeSessionId || 'default'
    const currentMsgs = allMessages[threadId] || []
    const lastAssistant = [...currentMsgs].reverse().find(m => m.role === 'assistant')
    const msgId = lastAssistant?.id
    if (!msgId) return

    setIsStreaming(true)
    setWorkflowState({ stage: 'execute', message: '审批通过，开始执行...', subtasks: [] })
    setWorkflowSessionId(threadId)
    needsApprovalRef.current = false

    try {
      const resp = await fetch('/api/v1/chat/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, thread_id: threadId, action, subtasks: modifications }),
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
            handleSSEEvent(currentEvent, line.slice(6), msgId, threadId, setAllMessages, setWorkflowState, setIsStreaming, needsApprovalRef)
          }
        }
      }
    } catch {}

    setIsStreaming(false)
    setWorkflowState(null)
    setWorkflowSessionId(null)
    setAllMessages(prev => ({
      ...prev,
      [threadId]: prev[threadId].map(m =>
        m.id === msgId ? { ...m, isStreaming: false } : m
      )
    }))
  }, [activeSessionId, allMessages])

  return { messages, isStreaming, workflowState, workflowSessionId, sendMessage, stopStreaming, loadHistory, approveTask }
}

function handleSSEEvent(event, data, msgId, threadId, setAllMessages, setWorkflowState, setIsStreaming, needsApprovalRef) {
  try {
    const parsed = JSON.parse(data)
    if (typeof parsed === 'string') {
      try { Object.assign(parsed, JSON.parse(parsed)) } catch {}
    }

    switch (event) {
      case 'thinking':
        setWorkflowState({
          stage: parsed?.stage || 'execute',
          message: parsed?.message || '',
          runningIds: parsed?.running_ids || [],
        })
        break

      case 'subtask_update':
        setWorkflowState({
          stage: 'decompose',
          message: `拆解为 ${parsed?.subtasks?.length || 0} 个子任务`,
          subtasks: parsed?.subtasks || [],
        })
        break

      case 'token':
        setWorkflowState(null)
        const tokenText = parsed == null ? '' : (typeof parsed === 'string' ? parsed : (parsed.data || ''))
        setAllMessages(prev => ({
          ...prev,
          [threadId]: prev[threadId].map(m =>
            m.id === msgId ? { ...m, content: m.content + tokenText } : m
          )
        }))
        break

      case 'result':
        if (parsed?.output) {
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
        needsApprovalRef.current = true
        setWorkflowState({
          stage: 'review',
          message: parsed?.message || '请审批子任务方案',
          taskId: parsed?.task_id,
          plan: parsed?.plan || [],
          needsApproval: true,
        })
        break

      case 'done':
        if (parsed?.elapsed) {
          setAllMessages(prev => ({
            ...prev,
            [threadId]: prev[threadId].map(m =>
              m.id === msgId ? { ...m, elapsed: parsed.elapsed, isStreaming: false } : m
            )
          }))
        } else {
          setAllMessages(prev => ({
            ...prev,
            [threadId]: prev[threadId].map(m =>
              m.id === msgId ? { ...m, isStreaming: false } : m
            )
          }))
        }
        setWorkflowState(null)
        setIsStreaming(false)
        break

      case 'error':
        setAllMessages(prev => ({
          ...prev,
          [threadId]: prev[threadId].map(m =>
            m.id === msgId ? { ...m, content: `❌ ${parsed?.message || '执行失败'}`, isStreaming: false } : m
          )
        }))
        setWorkflowState(null)
        break
    }
  } catch {}
}
