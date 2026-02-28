import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Terminal, ChevronRight } from 'lucide-react'

const LOG_COLORS = {
  alpha: 'text-terminal-cyan',
  beta: 'text-terminal-yellow',
  'gamma-execute': 'text-terminal-green',
  'gamma-abort': 'text-terminal-red',
  'gamma-inform': 'text-terminal-cyan',
  'gamma-research': 'text-terminal-yellow',
  'gamma-verdict': 'text-terminal-green',
  rag: 'text-emerald-400',
  scraper: 'text-purple-400',
  router: 'text-orange-400',
  docgen: 'text-pink-400',
  system: 'text-terminal-muted',
  user: 'text-white',
  swarm: 'text-white font-medium',
  scheduler: 'text-blue-400',
  success: 'text-terminal-green',
  error: 'text-terminal-red',
}

const LOG_PREFIX = {
  alpha: '⚡',
  beta: '🛡️',
  'gamma-execute': '✅',
  'gamma-abort': '🛑',
  'gamma-inform': '📋',
  'gamma-research': '🔍',
  'gamma-verdict': '◆',
  rag: '🌐',
  scraper: '🕷️',
  router: '🧭',
  docgen: '📄',
  system: '›',
  user: '$',
  swarm: '◈',
  scheduler: '⏰',
  success: '✓',
  error: '✗',
}

function formatTime(date) {
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function StructuredDataCard({ data }) {
  if (!data || typeof data !== 'object') return null

  const { summary, timeline_or_metrics } = data
  const metrics = Array.isArray(timeline_or_metrics) ? timeline_or_metrics : []

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="my-2 mx-1 rounded-lg border border-gray-700/40 bg-[#161B22]/80 overflow-hidden"
    >
      {/* Summary block */}
      {summary && (
        <div className="px-4 py-3 border-b border-gray-700/30">
          <p className="text-[13px] leading-relaxed text-gray-200/90">{summary}</p>
        </div>
      )}

      {/* Metrics table */}
      {metrics.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm border-collapse">
            <thead>
              <tr className="border-b border-gray-700/40">
                <th className="px-4 py-2 text-[11px] font-medium uppercase tracking-wider text-gray-500">
                  Key
                </th>
                <th className="px-4 py-2 text-[11px] font-medium uppercase tracking-wider text-gray-500">
                  Value
                </th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((entry, i) => (
                <tr
                  key={i}
                  className="border-b border-gray-700/20 last:border-b-0 hover:bg-white/[0.02] transition-colors"
                >
                  <td className="px-4 py-2 text-[12px] font-medium text-gray-400 whitespace-nowrap align-top">
                    {entry?.key || '—'}
                  </td>
                  <td className="px-4 py-2 text-[12px] text-gray-200 leading-relaxed break-words max-w-md">
                    {entry?.value || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {!summary && metrics.length === 0 && (
        <div className="px-4 py-3 text-[12px] text-gray-500 italic">No structured data available.</div>
      )}
    </motion.div>
  )
}

function tryParseStructuredData(text) {
  try {
    const jsonStart = text.indexOf('{')
    if (jsonStart === -1) return null
    const parsed = JSON.parse(text.slice(jsonStart))
    if (parsed.structured_data && typeof parsed.structured_data === 'object') {
      return {
        domain: parsed.domain || 'general',
        decision: parsed.decision || 'inform',
        structuredData: parsed.structured_data,
        reasoning: parsed.reasoning || '',
      }
    }
  } catch {
  }
  return null
}

export default function SwarmTerminal({ logs }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Terminal size={14} className="text-slate-accent" />
        <h2 className="font-serif text-lg font-medium text-charcoal">
          Swarm Terminal
        </h2>
        <span className="text-xs font-sans text-charcoal-muted ml-1">
          Live multi-agent debate feed
        </span>
      </div>

      <div className="rounded-xl overflow-hidden border border-terminal-border shadow-lg">
        {/* Title bar */}
        <div className="flex items-center gap-2 px-4 py-2.5 bg-[#161B22] border-b border-terminal-border">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-terminal-red/80" />
            <div className="w-3 h-3 rounded-full bg-terminal-yellow/80" />
            <div className="w-3 h-3 rounded-full bg-terminal-green/80" />
          </div>
          <span className="ml-2 text-xs font-mono text-terminal-muted">
            x10v-swarm — ws://localhost:8000/ws
          </span>
        </div>

        {/* Log output */}
        <div
          ref={scrollRef}
          className="bg-terminal-bg p-4 h-80 overflow-y-auto terminal-scroll font-mono text-sm leading-relaxed"
        >
          {logs.length === 0 && (
            <div className="flex items-center gap-2 text-terminal-muted">
              <ChevronRight size={12} />
              <span>Awaiting commands…</span>
              <span className="cursor-blink">▌</span>
            </div>
          )}

          <AnimatePresence>
            {logs.map((log) => {
              // Check if this is a Gamma verdict with structured_data
              const isGammaLog = log.type?.startsWith('gamma-')
              const parsed = isGammaLog ? tryParseStructuredData(log.text) : null

              if (parsed) {
                // Render the structured data card instead of raw JSON
                const decisionStyle = {
                  inform: { label: 'INFORM', color: 'text-terminal-cyan', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20' },
                  execute: { label: 'EXECUTE', color: 'text-terminal-green', bg: 'bg-green-500/10', border: 'border-green-500/20' },
                  abort: { label: 'ABORT', color: 'text-terminal-red', bg: 'bg-red-500/10', border: 'border-red-500/20' },
                }[parsed.decision] || { label: 'INFORM', color: 'text-terminal-cyan', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20' }

                return (
                  <motion.div
                    key={log.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, ease: 'easeOut' }}
                    className="py-1"
                  >
                    {/* Header bar */}
                    <div className="flex items-center gap-2 py-1">
                      <span className="text-terminal-muted/40 text-xs font-light shrink-0 select-none">
                        {formatTime(log.time)}
                      </span>
                      <span className="shrink-0 w-4 text-center select-none">◆</span>
                      <span className={`text-xs font-semibold uppercase tracking-wide ${decisionStyle.color}`}>
                        Gamma Verdict
                      </span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium uppercase tracking-wider ${decisionStyle.bg} ${decisionStyle.border} border ${decisionStyle.color}`}>
                        {decisionStyle.label}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 border border-gray-700/30 text-gray-400 uppercase tracking-wider font-medium">
                        {parsed.domain}
                      </span>
                    </div>
                    {/* Structured data table */}
                    <StructuredDataCard data={parsed.structuredData} />
                    {/* Reasoning footer */}
                    {parsed.reasoning && (
                      <div className="px-2 py-1 text-[11px] text-gray-500 italic">
                        🔎 {parsed.reasoning}
                      </div>
                    )}
                  </motion.div>
                )
              }

              // Default: render as plain text log line
              return (
                <motion.div
                  key={log.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, ease: 'easeOut' }}
                  className={`flex items-start gap-2 py-0.5 ${LOG_COLORS[log.type] || 'text-terminal-muted'}`}
                >
                  <span className="text-terminal-muted/40 text-xs font-light shrink-0 mt-0.5 select-none">
                    {formatTime(log.time)}
                  </span>
                  <span className="shrink-0 w-4 text-center select-none">
                    {LOG_PREFIX[log.type] || '›'}
                  </span>
                  <span className="break-all">{log.text}</span>
                </motion.div>
              )
            })}
          </AnimatePresence>

          {logs.length > 0 && (
            <div className="flex items-center gap-2 text-terminal-muted mt-1">
              <ChevronRight size={12} />
              <span className="cursor-blink">▌</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
