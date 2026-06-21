import { useState } from 'react'
import { Brain, Search, Code, CheckCircle, ChevronRight, Loader2, AlertCircle } from 'lucide-react'

const stageIcons = {
  decompose: Brain,
  execute: Code,
  reflect: CheckCircle,
  aggregate: Search,
  review: AlertCircle,
}

const stageLabels = {
  decompose: '拆解任务',
  execute: '执行子任务',
  reflect: '自反思检查',
  aggregate: '汇总交付',
  review: '等待审批',
}

export default function WorkflowPanel({ workflowState, onApprove }) {
  if (!workflowState) return null

  const { stage, message, subtasks, plan, taskId, needsApproval } = workflowState
  const Icon = stageIcons[stage] || Loader2
  const [modifyText, setModifyText] = useState('')
  const [showModify, setShowModify] = useState(false)

  return (
    <div className="animate-fade-in mb-4 mx-4">
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 backdrop-blur">
        <div className="flex items-center gap-3 mb-3">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${stage === 'review' ? 'bg-yellow-600/20' : 'bg-purple-600/20'}`}>
            <Icon size={16} className={stage === 'review' ? 'text-yellow-400' : 'text-purple-400'} />
          </div>
          <div>
            <p className="text-sm font-medium text-zinc-200">{stageLabels[stage] || stage}</p>
            <p className="text-xs text-zinc-500">{message}</p>
          </div>
        </div>

        {subtasks && subtasks.length > 0 && (
          <div className="space-y-1.5 ml-11">
            {subtasks.map((sub) => (
              <div key={sub.id} className="flex items-center gap-2 text-xs">
                <ChevronRight size={10} className="text-zinc-600" />
                <span className="px-1.5 py-0.5 bg-zinc-800 rounded text-zinc-400 font-mono text-[10px]">
                  [{sub.agent_type}]
                </span>
                <span className="text-zinc-300 truncate">{sub.description}</span>
                {sub.depends_on?.length > 0 && (
                  <span className="text-[10px] text-zinc-600">
                    ← {sub.depends_on.join(', ')}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {(!subtasks || subtasks.length === 0) && stage !== 'decompose' && (
          <div className="flex items-center gap-2 ml-11">
            <Loader2 size={12} className="animate-spin text-purple-400" />
            <span className="text-xs text-zinc-500">{message}</span>
          </div>
        )}

        {stage === 'review' && needsApproval && plan && (
          <div className="mt-4 pt-3 border-t border-zinc-800 ml-11">
            <p className="text-xs text-zinc-400 mb-2">子任务计划：</p>
            {plan.map((p) => (
              <div key={p.id} className="text-xs text-zinc-300 mb-1">
                <span className="text-purple-400">[{p.agent_type}]</span> {p.description}
              </div>
            ))}
            <div className="flex gap-2 mt-3">
              <button
                onClick={() => onApprove(taskId, 'approve')}
                className="px-3 py-1.5 text-xs bg-green-600 hover:bg-green-500 text-white rounded-lg transition-colors"
              >
                ✅ 批准
              </button>
              <button
                onClick={() => setShowModify(!showModify)}
                className="px-3 py-1.5 text-xs bg-yellow-600 hover:bg-yellow-500 text-white rounded-lg transition-colors"
              >
                ✏️ 修改
              </button>
              <button
                onClick={() => onApprove(taskId, 'reject')}
                className="px-3 py-1.5 text-xs bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors"
              >
                ❌ 拒绝
              </button>
            </div>
            {showModify && (
              <div className="mt-2">
                <textarea
                  value={modifyText}
                  onChange={e => setModifyText(e.target.value)}
                  placeholder="输入修改后的子任务 JSON..."
                  rows={4}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-zinc-200 resize-none focus:outline-none focus:border-purple-500"
                />
                <button
                  onClick={() => onApprove(taskId, 'modify', modifyText ? JSON.parse(modifyText) : undefined)}
                  className="mt-1 px-3 py-1 text-xs bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors"
                >
                  提交修改
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
