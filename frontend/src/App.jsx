import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import useChat from './hooks/useChat'
import useSessions from './hooks/useSessions'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import MessageInput from './components/MessageInput'
import BenchmarkPage from './pages/BenchmarkPage'

function ChatView({ activeId, sidebarOpen, setSidebarOpen, sessions, handleSelectSession, handleSend, createSession, deleteSession, messages, isStreaming, workflowState, stopStreaming }) {
  return (
    <div className="flex h-screen overflow-hidden">
      {sidebarOpen && (
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          onSelect={handleSelectSession}
          onCreate={createSession}
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
          isStreaming={isStreaming}
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
  const { messages, isStreaming, workflowState, sendMessage, stopStreaming, loadHistory } = useChat(activeId)

  useEffect(() => {
    if (activeId) loadHistory(activeId)
  }, [activeId, loadHistory])

  const handleSelectSession = (id) => {
    setActiveId(id)
    loadHistory(id)
  }

  const handleSend = (task) => {
    updateSessionTitle(activeId, task)
    sendMessage(task, activeId)
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/benchmark" element={<BenchmarkPage />} />
        <Route path="*" element={
          <ChatView
            activeId={activeId} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}
            sessions={sessions} handleSelectSession={handleSelectSession}
            handleSend={handleSend} createSession={createSession}
            deleteSession={deleteSession} messages={messages}
            isStreaming={isStreaming} workflowState={workflowState}
            stopStreaming={stopStreaming}
          />
        } />
      </Routes>
    </BrowserRouter>
  )
}
