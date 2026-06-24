import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Play, Loader2 } from 'lucide-react'
import useBenchmark from '../hooks/useBenchmark'

const CATEGORY_LABELS = {
  data_analysis: '数据分析',
  visualization: '可视化',
  code_generation: '代码生成',
  research: '研究搜索',
  report: '报告生成',
  complex: '复杂任务',
}

const CATEGORY_COLORS = {
  data_analysis: '#a78bfa',
  visualization: '#60a5fa',
  code_generation: '#34d399',
  research: '#fbbf24',
  report: '#f472b6',
  complex: '#fb923c',
}

function RingChart({ percent }) {
  const r = 54
  const c = 2 * Math.PI * r
  const offset = c - (percent / 100) * c
  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} fill="none" stroke="#27272a" strokeWidth="10" />
      <circle cx="70" cy="70" r={r} fill="none" stroke="#a78bfa" strokeWidth="10"
        strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
        transform="rotate(-90 70 70)" style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
      <text x="70" y="64" textAnchor="middle" fill="#fafafa" fontSize="28" fontWeight="700">{percent}%</text>
      <text x="70" y="84" textAnchor="middle" fill="#a1a1aa" fontSize="12">通过率</text>
    </svg>
  )
}

function StatCard({ label, value, unit }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-4 min-w-0">
      <div className="text-zinc-500 text-xs mb-1">{label}</div>
      <div className="text-zinc-100 text-2xl font-bold">
        {value}<span className="text-sm font-normal text-zinc-500 ml-1">{unit}</span>
      </div>
    </div>
  )
}

function CategoryBar({ cat, stats }) {
  const pct = stats.total > 0 ? Math.round((stats.passed / stats.total) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <span className="text-zinc-400 text-xs w-20 shrink-0">{cat}</span>
      <div className="flex-1 h-5 bg-zinc-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: CATEGORY_COLORS[stats.key] || '#a78bfa' }} />
      </div>
      <span className="text-zinc-300 text-xs w-14 text-right">{stats.passed}/{stats.total}</span>
      <span className="text-zinc-500 text-xs w-10 text-right">{pct}%</span>
    </div>
  )
}

export default function BenchmarkPage() {
  const navigate = useNavigate()
  const [runCount, setRunCount] = useState(5)
  const { reports, currentReport, loading, loadReport, runBenchmark, benchRunning, benchProgress } = useBenchmark()

  if (loading && !currentReport) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-zinc-500 text-sm">加载评测报告...</div>
      </div>
    )
  }

  if (!currentReport) {
    return (
      <div className="flex-1 flex items-center justify-center flex-col gap-4">
        <div className="text-zinc-500 text-sm">暂无评测报告</div>
        <div className="text-zinc-600 text-xs">选择题目数，点击运行评测</div>
        <div className="flex items-center gap-2">
          <select
            value={runCount}
            onChange={e => setRunCount(Number(e.target.value))}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-300"
            disabled={benchRunning}
          >
            <option value={5}>5 题（约1分钟）</option>
            <option value={10}>10 题（约2分钟）</option>
            <option value={20}>20 题（约4分钟）</option>
            <option value={50}>50 题（约10分钟）</option>
          </select>
          <button
            onClick={() => runBenchmark(runCount)}
            disabled={benchRunning}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              benchRunning
                ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                : 'bg-purple-600 hover:bg-purple-500 text-white'
            }`}
          >
            {benchRunning ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                {benchProgress.current}/{benchProgress.total}
              </>
            ) : (
              <>
                <Play size={16} />
                运行评测
              </>
            )}
          </button>
        </div>
        {benchRunning && (
          <div className="w-64">
            <div className="flex justify-between text-xs text-zinc-500 mb-1">
              <span>{benchProgress.message?.slice(0, 60)}</span>
              <span>{Math.round((benchProgress.current / benchProgress.total) * 100)}%</span>
            </div>
            <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-500 rounded-full transition-all duration-500"
                style={{ width: `${(benchProgress.current / benchProgress.total) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>
    )
  }

  const r = currentReport
  const passNum = parseFloat(r.pass_rate) || 0

  const categories = r.categories || {}
  const catEntries = Object.entries(categories).map(([k, v]) => ({ key: k, ...v }))

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/')}
              className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">评测结果</h2>
              <p className="text-zinc-500 text-xs mt-1">{r.timestamp}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {benchRunning && (
              <div className="flex items-center gap-2 text-xs text-zinc-400">
                <Loader2 size={14} className="animate-spin" />
                {benchProgress.current}/{benchProgress.total}
              </div>
            )}
            <select
              value={runCount}
              onChange={e => setRunCount(Number(e.target.value))}
              className="bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1 text-xs text-zinc-400"
              disabled={benchRunning}
            >
              <option value={5}>5题</option>
              <option value={10}>10题</option>
              <option value={20}>20题</option>
              <option value={50}>50题</option>
            </select>
            <button
              onClick={() => runBenchmark(runCount)}
              disabled={benchRunning}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                benchRunning
                  ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                  : 'bg-purple-600/20 border border-purple-600/30 text-purple-400 hover:bg-purple-600/30'
              }`}
            >
              {benchRunning ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
              {benchRunning ? '运行中' : '重新评测'}
            </button>
            {reports.length > 1 && (
              <select
                onChange={e => loadReport(e.target.value)}
                className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-300"
              >
                {reports.map(rp => (
                  <option key={rp.filename} value={rp.filename}>{rp.filename}</option>
                ))}
              </select>
            )}
          </div>
        </div>

        <div className="flex items-start gap-8 flex-wrap">
          <RingChart percent={Math.round(passNum)} />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 flex-1 min-w-0">
            <StatCard label="总任务数" value={r.total} unit="个" />
            <StatCard label="通过" value={r.passed} unit="个" />
            <StatCard label="失败" value={r.total - r.passed} unit="个" />
            <StatCard label="平均耗时" value={r.avg_duration_s?.toFixed(1)} unit="s" />
            <StatCard label="平均质量分" value={r.avg_quality_score?.toFixed(2)} unit="/1" />
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h3 className="text-sm font-medium text-zinc-300 mb-4">分类通过率</h3>
          <div className="space-y-3">
            {catEntries.map(({ key, total, passed }) => (
              <CategoryBar
                key={key}
                cat={CATEGORY_LABELS[key] || key}
                stats={{ key, total, passed }}
              />
            ))}
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-medium text-zinc-300">任务详情</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-xs">
                  <th className="text-left px-5 py-2.5 font-normal">ID</th>
                  <th className="text-left px-5 py-2.5 font-normal">分类</th>
                  <th className="text-left px-5 py-2.5 font-normal">任务</th>
                  <th className="text-center px-5 py-2.5 font-normal">状态</th>
                  <th className="text-center px-5 py-2.5 font-normal">子任务</th>
                  <th className="text-right px-5 py-2.5 font-normal">耗时</th>
                  <th className="text-right px-5 py-2.5 font-normal">质量分</th>
                </tr>
              </thead>
              <tbody>
                {(r.details || []).map(d => (
                  <tr key={d.task_id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                    <td className="px-5 py-2.5 text-zinc-400 font-mono text-xs">{d.task_id}</td>
                    <td className="px-5 py-2.5">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300">
                        {CATEGORY_LABELS[d.category] || d.category}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-zinc-300 max-w-xs truncate">{d.task}</td>
                    <td className="px-5 py-2.5 text-center">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        d.passed
                          ? 'bg-emerald-900/40 text-emerald-400'
                          : 'bg-red-900/40 text-red-400'
                      }`}>
                        {d.passed ? 'PASS' : 'FAIL'}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-center text-zinc-400">{d.subtask_count}</td>
                    <td className="px-5 py-2.5 text-right text-zinc-400 font-mono">{d.duration_s?.toFixed(1)}s</td>
                    <td className="px-5 py-2.5 text-right text-zinc-400 font-mono">{d.quality_score?.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  )
}
