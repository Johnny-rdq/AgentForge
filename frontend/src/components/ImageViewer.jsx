import { useEffect, useCallback } from 'react'
import { X, Download, ZoomIn, ZoomOut } from 'lucide-react'
import { useState } from 'react'

export default function ImageViewer({ src, alt, onClose }) {
  const [zoom, setZoom] = useState(1)

  const handleClose = useCallback(() => {
    setZoom(1)
    onClose()
  }, [onClose])

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') handleClose()
    }
    document.addEventListener('keydown', handleKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.body.style.overflow = ''
    }
  }, [handleClose])

  if (!src) return null

  const getImageSrc = (raw) => {
    const decoded = decodeURIComponent(raw)
    // 移除协议+域名前缀（http://xxx/generated/... → /generated/...）
    const cleaned = decoded.replace(/^https?:\/\/[^/]+\/generated\//, '/generated/')
    // 如果已经是 /generated/ 开头的相对路径，直接返回
    if (cleaned.startsWith('/generated/')) return cleaned
    // 兜底：提取 /generated/ 之后的部分（含可能的子目录如 thread_id）
    const match = decoded.match(/\/generated\/(.+\.(png|jpg|jpeg|gif|svg|webp|bmp))(?:\?.*)?$/i)
    if (match) return `/generated/${match[1]}`
    return cleaned
  }
  const imgSrc = getImageSrc(src)

  return (
    <div
      className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center animate-fade-in"
      onClick={handleClose}
    >
      <div className="absolute top-4 right-4 flex items-center gap-2">
        <button
          onClick={() => setZoom(z => Math.max(0.25, z - 0.25))}
          className="p-2 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors"
          title="缩小"
        >
          <ZoomOut size={18} />
        </button>
        <button
          onClick={() => setZoom(z => Math.min(5, z + 0.25))}
          className="p-2 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors"
          title="放大"
        >
          <ZoomIn size={18} />
        </button>
        <a
          href={imgSrc}
          download
          onClick={e => e.stopPropagation()}
          className="p-2 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors"
          title="下载"
        >
          <Download size={18} />
        </a>
        <button
          onClick={handleClose}
          className="p-2 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors"
          title="关闭"
        >
          <X size={20} />
        </button>
      </div>
      <div
        className="max-w-[90vw] max-h-[90vh] overflow-auto"
        onClick={e => e.stopPropagation()}
      >
        <img
          src={imgSrc}
          alt={alt || '查看图片'}
          className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl transition-transform duration-200"
          style={{ transform: `scale(${zoom})` }}
        />
      </div>
      {alt && (
        <p className="absolute bottom-4 left-1/2 -translate-x-1/2 text-sm text-zinc-400 bg-zinc-900/80 px-4 py-1.5 rounded-full">
          {alt}
        </p>
      )}
    </div>
  )
}
