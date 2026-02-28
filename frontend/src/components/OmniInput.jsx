import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Loader2, Sparkles, MonitorUp, MonitorOff, Timer, Eye, EyeOff } from 'lucide-react'

export default function OmniInput({ onSubmit, isProcessing, isSharing, isPiP, onStartShare, onStopShare, videoRef }) {
  const [value, setValue] = useState('')
  const [countdown, setCountdown] = useState(null)
  const [pendingCommand, setPendingCommand] = useState(null)
  const [showViewfinder, setShowViewfinder] = useState(true)
  const inputRef = useRef(null)
  const intervalRef = useRef(null)
  const viewfinderRef = useRef(null)

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  useEffect(() => {
    if (!viewfinderRef.current || !videoRef?.current) return
    const srcObj = videoRef.current.srcObject
    if (isSharing && srcObj) {
      viewfinderRef.current.srcObject = srcObj
      viewfinderRef.current.play().catch(() => {})
    } else {
      viewfinderRef.current.srcObject = null
    }
  }, [isSharing, videoRef])

  useEffect(() => {
    if (countdown === 0 && pendingCommand) {
      setCountdown(null)
      const cmd = pendingCommand
      setPendingCommand(null)
      setValue('')
      onSubmit(cmd)
    }
  }, [countdown, pendingCommand, onSubmit])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!value.trim() || isProcessing || countdown !== null) return

    if (isSharing && !isPiP) {
      const cmd = value.trim()
      setPendingCommand(cmd)
      setCountdown(3)

      intervalRef.current = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
            return 0
          }
          return prev - 1
        })
      }, 1000)
    } else {
      const cmd = value.trim()
      setValue('')
      onSubmit(cmd)
    }
  }

  const isLocked = isProcessing || countdown !== null

  const getPlaceholder = () => {
    if (countdown !== null && countdown > 0) {
      return `Switch to target tab… Capturing in [${countdown}]…`
    }
    if (countdown === 0) {
      return 'Capturing screen now…'
    }
    if (isProcessing) {
      return 'Swarm processing…'
    }
    if (isSharing) {
      return isPiP
        ? 'PiP active — type your command, capture is instant …'
        : 'Screen is live — "Analyze this chart", "What do you see?", …'
    }
    return 'Ask the swarm to analyze a chart, schedule a trade, or automate a task…'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles size={14} className="text-bronze-accent" />
          <h2 className="font-serif text-lg font-medium text-charcoal">
            Command Center
          </h2>
        </div>

        {isSharing && (
          <button
            type="button"
            onClick={() => setShowViewfinder((v) => !v)}
            className="flex items-center gap-1.5 text-xs font-sans text-charcoal-muted
                       hover:text-slate-accent transition-colors"
          >
            {showViewfinder ? <EyeOff size={12} /> : <Eye size={12} />}
            {showViewfinder ? 'Hide preview' : 'Show preview'}
          </button>
        )}
      </div>

      <AnimatePresence>
        {isSharing && showViewfinder && (
          <motion.div
            initial={{ height: 0, opacity: 0, marginBottom: 0 }}
            animate={{ height: 'auto', opacity: 1, marginBottom: 12 }}
            exit={{ height: 0, opacity: 0, marginBottom: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="relative w-full max-w-sm">
              <video
                ref={viewfinderRef}
                autoPlay
                muted
                playsInline
                className="w-64 h-36 rounded-lg border border-charcoal/10 bg-terminal-bg
                           object-cover shadow-[0_2px_8px_rgba(0,0,0,0.08)]"
              />

              <div className="absolute top-2 left-2 flex items-center gap-1.5
                              px-2 py-0.5 rounded-md bg-terminal-bg/80 backdrop-blur-sm">
                <span className="w-1.5 h-1.5 rounded-full bg-terminal-green pulse-soft" />
                <span className="text-[10px] font-mono text-terminal-green">
                  LIVE VIEWFINDER
                </span>
              </div>

              <AnimatePresence>
                {countdown !== null && countdown > 0 && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 rounded-lg flex items-center justify-center
                               bg-terminal-bg/70 backdrop-blur-[2px]"
                  >
                    <motion.span
                      key={countdown}
                      initial={{ scale: 0.5, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 1.5, opacity: 0 }}
                      transition={{ duration: 0.4 }}
                      className="text-4xl font-mono font-bold text-bronze-accent drop-shadow-lg"
                    >
                      {countdown}
                    </motion.span>
                  </motion.div>
                )}
              </AnimatePresence>

              <AnimatePresence>
                {countdown === 0 && (
                  <motion.div
                    initial={{ opacity: 0.9 }}
                    animate={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className="absolute inset-0 rounded-lg bg-white"
                  />
                )}
              </AnimatePresence>
            </div>

            <p className="text-[11px] font-sans text-charcoal-muted/50 mt-1.5 ml-0.5">
              {countdown !== null && countdown > 0
                ? '⚠️ Verify: is this your target tab? Switch now if not!'
                : 'Verify you\u2019re capturing the right tab \u2014 not this dashboard.'}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      <form onSubmit={handleSubmit} className="relative flex items-center gap-3">
        <button
          type="button"
          onClick={isSharing ? onStopShare : onStartShare}
          disabled={countdown !== null}
          className={`shrink-0 p-3.5 rounded-xl border transition-all duration-200
            ${isSharing
              ? 'bg-terminal-green/10 border-terminal-green/30 text-terminal-green hover:bg-terminal-green/20'
              : 'bg-white border-charcoal/8 text-charcoal-muted hover:border-slate-accent/40 hover:text-slate-accent'
            }
            ${countdown !== null ? 'opacity-50 cursor-not-allowed' : ''}`}
          title={isSharing ? 'Stop sharing screen' : 'Share screen for AI analysis'}
        >
          {isSharing ? <MonitorOff size={20} /> : <MonitorUp size={20} />}
        </button>

        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={countdown !== null ? '' : value}
            onChange={(e) => { if (countdown === null) setValue(e.target.value) }}
            disabled={isLocked}
            placeholder={getPlaceholder()}
            className={`w-full px-6 py-5 text-base font-sans text-charcoal bg-white
                       border rounded-xl
                       placeholder:font-light
                       focus:outline-none focus:border-slate-accent/40 focus:ring-1 focus:ring-slate-accent/20
                       transition-all duration-300 disabled:cursor-not-allowed
                       shadow-[0_1px_3px_rgba(0,0,0,0.02)]
                       ${countdown !== null
                         ? 'border-bronze-accent/40 bg-bronze-accent/[0.03] placeholder:text-bronze-accent/70 placeholder:font-medium disabled:opacity-90'
                         : 'border-charcoal/8 placeholder:text-charcoal-muted/50 disabled:opacity-60'
                       }`}
          />

          <AnimatePresence>
            {countdown !== null && countdown > 0 && (
              <motion.div
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
                className="absolute right-3 top-1/2 -translate-y-1/2
                           flex items-center gap-2 px-4 py-2 rounded-lg
                           bg-bronze-accent text-cream font-mono text-sm font-semibold
                           shadow-md"
              >
                <Timer size={16} className="animate-pulse" />
                {countdown}
              </motion.div>
            )}
          </AnimatePresence>

          {countdown === null && (
            <button
              type="submit"
              disabled={isProcessing || !value.trim()}
              className="absolute right-3 top-1/2 -translate-y-1/2
                         p-2.5 rounded-lg
                         bg-charcoal text-cream
                         hover:bg-charcoal-light
                         disabled:opacity-30 disabled:cursor-not-allowed
                         transition-all duration-200"
            >
              {isProcessing ? (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
                >
                  <Loader2 size={18} />
                </motion.div>
              ) : (
                <Send size={18} />
              )}
            </button>
          )}
        </div>
      </form>

      <div className="flex items-center gap-4 mt-3 text-xs font-sans text-charcoal-muted/60">
        {countdown !== null && countdown > 0 && (
          <span className="flex items-center gap-1.5 text-bronze-accent font-medium animate-pulse">
            <Timer size={12} />
            Switch to your target tab now
          </span>
        )}
        {isSharing && countdown === null && (
          <span className="flex items-center gap-1 text-terminal-green font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-terminal-green pulse-soft inline-block" />
            Screen live
          </span>
        )}
        <span>
          <kbd className="px-1.5 py-0.5 rounded bg-charcoal/5 text-charcoal-muted font-mono text-[10px]">
            Enter
          </kbd>{' '}
          to submit
        </span>
        {isSharing && countdown === null && (
          <span className="text-bronze-accent/60">
            {isPiP ? 'PiP mode — instant capture, no countdown needed' : '3s countdown on submit for tab-switching'}
          </span>
        )}
        {!isSharing && <span>Time keywords auto-schedule</span>}
        {!isSharing && <span>Share screen for visual AI analysis</span>}
      </div>
    </div>
  )
}
