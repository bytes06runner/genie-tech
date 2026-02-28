import { motion, AnimatePresence } from 'framer-motion'
import {
  Clock,
  MessageSquare,
  CheckCircle2,
  XCircle,
  Loader2,
  BrainCircuit,
  Play,
  ListTodo,
} from 'lucide-react'

const STATUS_CONFIG = {
  pending: {
    label: 'Pending',
    color: 'text-charcoal-muted',
    bg: 'bg-charcoal/5',
    border: 'border-charcoal/10',
    icon: Clock,
  },
  scraping: {
    label: 'Scraping',
    color: 'text-blue-600',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    icon: Loader2,
    animate: true,
  },
  swarm_debating: {
    label: 'Swarm Debating',
    color: 'text-amber-600',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    icon: BrainCircuit,
    animate: true,
  },
  executing: {
    label: 'Executing',
    color: 'text-purple-600',
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    icon: Play,
    animate: true,
  },
  completed: {
    label: 'Completed',
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    icon: CheckCircle2,
  },
  vetoed: {
    label: 'Vetoed',
    color: 'text-red-500',
    bg: 'bg-red-50',
    border: 'border-red-200',
    icon: XCircle,
  },
  failed: {
    label: 'Failed',
    color: 'text-red-600',
    bg: 'bg-red-50',
    border: 'border-red-200',
    icon: XCircle,
  },
}

function StatusBadge({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending
  const Icon = config.icon

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-sans font-medium
                  ${config.color} ${config.bg} border ${config.border}`}
    >
      {config.animate ? (
        <motion.span
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
          className="inline-flex"
        >
          <Icon size={12} />
        </motion.span>
      ) : (
        <Icon size={12} />
      )}
      {config.label}
    </span>
  )
}

function formatRunAt(isoString) {
  try {
    const d = new Date(isoString)
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    })
  } catch {
    return isoString
  }
}

export default function TaskQueue({ tasks }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ListTodo size={14} className="text-bronze-accent" />
          <h2 className="font-serif text-lg font-medium text-charcoal">
            Active Automations
          </h2>
          <span className="text-xs font-sans text-charcoal-muted ml-1">
            APScheduler queue
          </span>
        </div>
        <span className="text-xs font-sans text-charcoal-muted/50">
          {tasks.length} task{tasks.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="space-y-3">
        <AnimatePresence>
          {tasks.map((task, i) => (
            <motion.div
              key={task.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.3, delay: i * 0.05, ease: 'easeOut' }}
              className="flex items-center justify-between p-4 rounded-xl
                         bg-white border border-charcoal/5
                         shadow-[0_1px_3px_rgba(0,0,0,0.02)]
                         hover:border-charcoal/10 transition-colors duration-200"
            >
              <div className="flex-1 min-w-0 mr-4">
                <p className="font-sans text-sm text-charcoal leading-snug truncate">
                  {task.description}
                </p>
                <div className="flex items-center gap-3 mt-1.5">
                  <span className="flex items-center gap-1 text-xs text-charcoal-muted">
                    <Clock size={10} />
                    {formatRunAt(task.run_at)}
                  </span>
                  <span className="text-xs text-charcoal-muted/40 font-mono">
                    {task.id}
                  </span>
                </div>
                {task.result && (
                  <p className="mt-1.5 text-xs text-charcoal-muted/70 font-sans italic truncate">
                    {typeof task.result === 'string'
                      ? task.result
                      : JSON.stringify(task.result)}
                  </p>
                )}
              </div>

              <StatusBadge status={task.status} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {tasks.length === 0 && (
        <div className="text-center py-12 text-charcoal-muted/50 font-sans text-sm">
          <MessageSquare size={24} className="mx-auto mb-2 opacity-30" />
          No tasks scheduled yet. Use the command center above.
        </div>
      )}
    </div>
  )
}
