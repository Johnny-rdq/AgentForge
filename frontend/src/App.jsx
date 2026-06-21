import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import useChat from './hooks/useChat'
import useSessions from './hooks/useSessions'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import MessageInput from './components/MessageInput'
import ErrorBoundary from './components/ErrorBoundary'
import BenchmarkPage from './pages/BenchmarkPage'

function ChatView({ activeId, sidebarOpen, setSidebarOpen, sessions, handleSelectSession, handleSend, handleCreate, deleteSession, messages, isStreaming, workflowState, workflowSessionId, stopStreaming, handleApprove }) {
  return (
    <div className="flex h-screen overflow-hidden">
      {sidebarOpen && (
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          onSelect={handleSelectSession}
          onCreate={handleCreate}
          onDelete={deleteSession}
          onCollapse={() => setSidebarOpen(false)}
        />
      )}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="shrink-0 w-10 h-screen bg-zinc-900 border-r border-zinc-800 flex items-start pt-4 justify-center hover:bg-zinc-800 transition-colors"
        >
          <span className="text-zinc-500 text-lg">☰</span>
        </button>
      )}
      <main className="flex-1 flex flex-col min-w-0">
        <ChatArea
          messages={messages}
          workflowState={workflowState}
          workflowSessionId={workflowSessionId}
          activeId={activeId}
          isStreaming={isStreaming}
          onApprove={handleApprove}
        />
        <MessageInput
          onSend={handleSend}
          onStop={stopStreaming}
          isStreaming={isStreaming}
        />
      </main>
    </div>
  )
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { sessions, activeId, setActiveId, createSession, deleteSession, updateSessionTitle } = useSessions()
  const { messages, isStreaming, workflowState, workflowSessionId, sendMessage, stopStreaming, loadHistory, approveTask } = useChat(activeId)

  useEffect(() => {
    if (activeId) loadHistory(activeId)
  }, [activeId, loadHistory])

  const handleSelectSession = (id) => {
    setActiveId(id)
    loadHistory(id)
  }

  const handleCreate = () => {
    if (activeId && messages.length === 0) return
    createSession()
  }

  const handleSend = (task, files = []) => {
    let targetId = activeId
    if (!targetId) targetId = createSession()
    if (messages.length === 0) updateSessionTitle(targetId, task)
    sendMessage(task, targetId, files)
  }

  const handleApprove = (taskId, action, modifications) => {
    approveTask(taskId, action, modifications)
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/benchmark" element={<BenchmarkPage />} />
        <Route path="*" element={
          <ErrorBoundary>
            <ChatView
              activeId={activeId} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}
              sessions={sessions} handleSelectSession={handleSelectSession}
              handleSend={handleSend} handleCreate={handleCreate}
              deleteSession={deleteSession} messages={messages}
              isStreaming={isStreaming} workflowState={workflowState}
              workflowSessionId={workflowSessionId}
              stopStreaming={stopStreaming} handleApprove={handleApprove}
            />
          </ErrorBoundary>
        } />
      </Routes>
    </BrowserRouter>
  )
}
