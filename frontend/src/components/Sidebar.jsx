import { useState, useEffect } from 'react'
import { Plus, Trash2, MessageSquare, Zap, PanelLeftClose, BarChart3, ShieldCheck, ShieldOff } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

export default function Sidebar({ sessions, activeId, onSelect, onCreate, onDelete, onCollapse }) {
  const location = useLocation()
  const [hitlEnabled, setHitlEnabled] = useState(false)

  useEffect(() => {
    fetch('/api/v1/settings/hitl')
      .then(r => r.json())
      .then(d => setHitlEnabled(d.hitl_enabled))
      .catch(() => {})
  }, [])

  const toggleHitl = async () => {
    try {
      const r = await fetch('/api/v1/settings/hitl', { method: 'POST' })
      const d = await r.json()
      setHitlEnabled(d.hitl_enabled)
    } catch {}
  }

  return (
    <aside className="w-64 h-screen bg-zinc-900 border-r border-zinc-800 flex flex-col shrink-0">
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-purple-600 rounded-lg flex items-center justify-center">
              <Zap size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-zinc-100">AgentForge</h1>
              <p className="text-[10px] text-zinc-500">AI 智能助手</p>
            </div>
          </div>
          <button
            onClick={onCollapse}
            className="text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <PanelLeftClose size={16} />
          </button>
        </div>
        <button
          onClick={onCreate}
          className="w-full flex items-center justify-center gap-2 py-2 text-sm bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors"
        >
          <Plus size={16} />
          新会话
        </button>
        <Link
          to="/benchmark"
          className={`w-full flex items-center gap-2.5 px-3 py-2 mt-2 rounded-lg text-sm transition-colors ${
            location.pathname === '/benchmark'
              ? 'bg-zinc-800 text-purple-400'
              : 'text-zinc-500 hover:bg-zinc-800/50 hover:text-zinc-300'
          }`}
        >
          <BarChart3 size={14} className="shrink-0" />
          评测结果
        </Link>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {sessions.map(s => (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left text-sm transition-colors group ${
              activeId === s.id
                ? 'bg-zinc-800 text-zinc-100'
                : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200'
            }`}
          >
            <MessageSquare size={14} className="shrink-0" />
            <span className="truncate flex-1">{s.title}</span>
            <button
              onClick={e => { e.stopPropagation(); onDelete(s.id) }}
              className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all"
            >
              <Trash2 size={13} />
            </button>
          </button>
        ))}
      </div>

      <div className="p-3 border-t border-zinc-800 space-y-2">
        <button
          onClick={toggleHitl}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all ${
            hitlEnabled
              ? 'bg-yellow-600/15 border border-yellow-600/30 text-yellow-300'
              : 'bg-zinc-800/50 border border-zinc-700/30 text-zinc-500'
          }`}
        >
          {hitlEnabled ? <ShieldCheck size={14} /> : <ShieldOff size={14} />}
          <span>人工审批 {hitlEnabled ? 'ON' : 'OFF'}</span>
          <span className={`ml-auto w-7 h-4 rounded-full transition-colors relative ${hitlEnabled ? 'bg-yellow-600' : 'bg-zinc-700'}`}>
            <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${hitlEnabled ? 'left-3.5' : 'left-0.5'}`} />
          </span>
        </button>
        <p className="text-[10px] text-zinc-600 text-center">AgentForge v1.0</p>
      </div>
    </aside>
  )
}
