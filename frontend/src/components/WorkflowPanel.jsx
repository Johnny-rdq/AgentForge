import { Brain, Search, Code, CheckCircle, ChevronRight, Loader2 } from 'lucide-react'

const stageIcons = {
  decompose: Brain,
  execute: Code,
  reflect: CheckCircle,
  aggregate: Search,
}

const stageLabels = {
  decompose: '拆解任务',
  execute: '执行子任务',
  reflect: '自反思检查',
  aggregate: '汇总交付',
}

export default function WorkflowPanel({ workflowState }) {
  if (!workflowState) return null

  const { stage, message, subtasks } = workflowState
  const Icon = stageIcons[stage] || Loader2

  return (
    <div className="animate-fade-in mb-4 mx-4">
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 backdrop-blur">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 bg-purple-600/20 rounded-lg flex items-center justify-center">
            <Icon size={16} className="text-purple-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-zinc-200">{stageLabels[stage] || stage}</p>
            <p className="text-xs text-zinc-500">{message}</p>
          </div>
        </div>

        {subtasks && subtasks.length > 0 && (
          <div className="space-y-1.5 ml-11">
            {subtasks.map((sub, i) => (
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
      </div>
    </div>
  )
}
