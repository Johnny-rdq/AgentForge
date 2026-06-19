import { useMemo } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user'

  const html = useMemo(() => {
    if (isUser || !message.content) return null
    const raw = marked.parse(message.content, { breaks: true })
    return DOMPurify.sanitize(raw)
  }, [message.content, isUser])

  return (
    <div className={`flex px-4 py-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`min-w-0 max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        {isUser ? (
          <p className="text-sm text-zinc-200 whitespace-pre-wrap leading-relaxed bg-zinc-800 rounded-2xl rounded-tr-md px-4 py-2.5 inline-block text-left">
            {message.content}
          </p>
        ) : message.isStreaming && !message.content ? null : (
          <div className="markdown-body text-sm text-zinc-300" dangerouslySetInnerHTML={{ __html: html }} />
        )}
        {message.isStreaming && message.content && (
          <span className="inline-block w-1.5 h-4 bg-purple-400 animate-pulse-dot ml-0.5 align-middle" />
        )}
      </div>
    </div>
  )
}
