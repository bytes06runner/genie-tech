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
  rag: 'text-emerald-400',
  scraper: 'text-purple-400',
  router: 'text-orange-400',
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
  rag: '🌐',
  scraper: '🕷️',
  router: '🧭',
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
            {logs.map((log) => (
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
            ))}
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
