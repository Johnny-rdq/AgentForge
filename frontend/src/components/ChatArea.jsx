import { useEffect, useRef } from 'react'
import { Sparkles } from 'lucide-react'
import ChatMessage from './ChatMessage'
import WorkflowPanel from './WorkflowPanel'

export default function ChatArea({ messages, workflowState, isStreaming }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, workflowState])

  return (
    <div className="flex-1 overflow-y-auto">
      {messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full text-zinc-600 px-4">
          <div className="w-16 h-16 bg-zinc-900 rounded-2xl flex items-center justify-center mb-4 border border-zinc-800">
            <Sparkles size={28} className="text-purple-500" />
          </div>
          <h2 className="text-lg font-semibold text-zinc-400 mb-2">AgentForge</h2>
          <p className="text-sm text-zinc-600 text-center max-w-md">
            输入你的任务，多Agent系统自动拆解、调度、执行。
          </p>
          <div className="flex gap-2 mt-6 flex-wrap justify-center">
            {['分析销售数据并生成报告', '搜索对比主流AI框架', '用Python写一个贪吃蛇游戏'].map(hint => (
              <button
                key={hint}
                onClick={() => {
                  const input = document.querySelector('textarea')
                  if (input) {
                    input.value = hint
                    input.focus()
                    input.dispatchEvent(new Event('input', { bubbles: true }))
                  }
                }}
                className="px-3 py-1.5 text-xs bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition-colors"
              >
                {hint}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="pb-4">
          {messages.map(msg => (
            <ChatMessage key={msg.id} message={msg} />
          ))}
          {workflowState && <WorkflowPanel workflowState={workflowState} />}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
