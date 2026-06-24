import { useMemo, useCallback } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { FileText } from 'lucide-react'

export default function ChatMessage({ message, onImageClick }) {
  const isUser = message.role === 'user'

  const handleClick = useCallback((e) => {
    if (e.target.tagName === 'IMG') {
      onImageClick?.(e.target.src, e.target.alt)
    }
  }, [onImageClick])

  const html = useMemo(() => {
    if (isUser || !message.content) return ''
    try {
      let content = message.content
      // 后端 LLM 可能生成完整 URL（如 http://localhost:7860/generated/x.png），统一转为相对路径
      content = content.replace(/https?:\/\/[^/]+\/generated\//g, '/generated/')
      const raw = marked.parse(content, { breaks: true })
      return DOMPurify.sanitize(raw, { ADD_ATTR: ['target'] }) || ''
    } catch (e) {
      console.error('Markdown parse error:', e)
      try {
        return DOMPurify.sanitize(`<p>${String(message.content).slice(0, 500)}</p>`) || ''
      } catch {
        return '<p>内容解析失败</p>'
      }
    }
  }, [message.content, isUser])

  const files = message.files || []

  return (
    <div className={`flex px-4 py-2 group ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`min-w-0 max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        {isUser ? (
          <div className="inline-block text-left">
            {files.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-1.5 justify-end">
                {files.map((f, i) => (
                  <span key={i} className="inline-flex items-center gap-1 text-xs bg-zinc-700 border border-zinc-600 rounded-lg px-2 py-1 text-zinc-300">
                    <FileText size={12} className="text-zinc-400" />
                    {f.originalName || f.filename}
                  </span>
                ))}
              </div>
            )}
            {message.content && (
              <p className="text-sm text-zinc-200 whitespace-pre-wrap leading-relaxed bg-zinc-800 rounded-2xl rounded-tr-md px-4 py-2.5">
                {message.content}
              </p>
            )}
          </div>
        ) : message.isStreaming && !message.content ? null : (
          <>
            {html ? <div className="markdown-body text-sm text-zinc-300" dangerouslySetInnerHTML={{ __html: html }} onClick={handleClick} /> : <p className="text-sm text-zinc-500">等待输出...</p>}
            {!message.isStreaming && (message.elapsed || message.elapsed_ms) && (
              <p className="text-xs text-zinc-500 mt-1.5">⏱️ {message.elapsed || (message.elapsed_ms / 1000).toFixed(1)}s</p>
            )}
          </>
        )}
        {message.isStreaming && message.content && (
          <span className="inline-block w-1.5 h-4 bg-purple-400 animate-pulse-dot ml-0.5 align-middle" />
        )}
      </div>
    </div>
  )
}
