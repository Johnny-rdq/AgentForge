import { useState, useRef } from 'react'
import { Send, Square, Paperclip, X, FileText } from 'lucide-react'

export default function MessageInput({ onSend, onStop, isStreaming }) {
  const [input, setInput] = useState('')
  const [files, setFiles] = useState([])
  const fileRef = useRef(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if ((!input.trim() && !files.length) || isStreaming) return
    onSend(input, files)
    setInput('')
    setFiles([])
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const addFiles = (e) => {
    const selected = Array.from(e.target.files || [])
    setFiles(prev => [...prev, ...selected])
    fileRef.current.value = ''
  }

  const removeFile = (i) => {
    setFiles(prev => prev.filter((_, idx) => idx !== i))
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-zinc-800 p-4 bg-zinc-950">
      {files.length > 0 && (
        <div className="flex flex-wrap gap-1.5 max-w-4xl mx-auto mb-2">
          {files.map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 text-xs bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1 text-zinc-300">
              <FileText size={12} className="text-zinc-500" />
              <span className="max-w-[120px] truncate">{f.name}</span>
              <button type="button" onClick={() => removeFile(i)} className="text-zinc-500 hover:text-red-400">
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex items-center gap-3 max-w-4xl mx-auto">
        <input type="file" ref={fileRef} onChange={addFiles} className="hidden" multiple accept=".csv,.xlsx,.xls,.json,.txt,.md,.py,.pdf,.doc,.docx,.html,.css,.js,.ts,.yaml,.yml,.xml,.log" />
        <button
          type="button"
          onClick={() => fileRef.current.click()}
          className="shrink-0 w-10 h-10 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 rounded-xl flex items-center justify-center transition-colors"
        >
          <Paperclip size={16} />
        </button>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="描述你的任务，Agent 自动拆解执行..."
          rows={1}
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder-zinc-500 resize-none focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500/50 transition-colors"
          style={{ minHeight: '2.75rem', maxHeight: '8rem' }}
          onInput={e => {
            e.target.style.height = 'auto'
            e.target.style.height = Math.min(e.target.scrollHeight, 128) + 'px'
          }}
        />
        {isStreaming ? (
          <button
            type="button"
            onClick={onStop}
            className="shrink-0 w-10 h-10 bg-red-600 hover:bg-red-500 text-white rounded-xl flex items-center justify-center transition-colors"
          >
            <Square size={16} fill="currentColor" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim() && !files.length}
            className="shrink-0 w-10 h-10 bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white rounded-xl flex items-center justify-center transition-colors"
          >
            <Send size={16} />
          </button>
        )}
      </div>
    </form>
  )
}
