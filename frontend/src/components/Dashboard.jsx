import { useState, useEffect, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Bot, Zap, Shield, MonitorUp } from 'lucide-react'
import OmniInput from './OmniInput'
import SwarmTerminal from './SwarmTerminal'
import TaskQueue from './TaskQueue'
import PiPAgent from './PiPAgent'

const WS_URL = 'ws://localhost:8000/ws'
const API_BASE = 'http://localhost:8000'

export default function Dashboard() {
  const [logs, setLogs] = useState([])
  const [tasks, setTasks] = useState([])
  const [isConnected, setIsConnected] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isSharing, setIsSharing] = useState(false)
  const [isPiP, setIsPiP] = useState(false)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)

  // ------------------------------------------------------------------
  // WebSocket connection with auto-reconnect
  // ------------------------------------------------------------------
  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      setIsConnected(true)
      addLog('[System] Connected to X10V Swarm Terminal ✓', 'system')
    }

    ws.onmessage = (event) => {
      const msg = event.data
      let type = 'system'
      if (msg.includes('[Alpha')) type = 'alpha'
      else if (msg.includes('[Beta')) type = 'beta'
      else if (msg.includes('[Gamma') && msg.includes('|green')) type = 'gamma-execute'
      else if (msg.includes('[Gamma') && msg.includes('|red')) type = 'gamma-abort'
      else if (msg.includes('[Gamma') && msg.includes('|cyan')) type = 'gamma-inform'
      else if (msg.includes('[Gamma') && msg.includes('|yellow')) type = 'gamma-research'
      else if (msg.includes('[Gamma')) type = 'gamma-execute'
      else if (msg.includes('[DeepScraper]')) type = 'scraper'
      else if (msg.includes('[RAG]')) type = 'rag'
      else if (msg.includes('[Scheduler|red') || msg.includes('[Scheduler] ❌')) type = 'error'
      else if (msg.includes('[Scheduler|green') || msg.includes('[Scheduler] ✅')) type = 'success'
      else if (msg.includes('[Scheduler')) type = 'scheduler'
      else if (msg.includes('[Swarm]')) type = 'swarm'
      addLog(msg, type)
    }

    ws.onclose = () => {
      setIsConnected(false)
      addLog('[System] Disconnected — reconnecting …', 'error')
      reconnectTimer.current = setTimeout(connectWs, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connectWs()
    fetchTasks()
    const interval = setInterval(fetchTasks, 5000)
    return () => {
      clearInterval(interval)
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connectWs])

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  const addLog = (text, type = 'system') => {
    setLogs((prev) => [
      ...prev,
      { id: Date.now() + Math.random(), text, type, time: new Date() },
    ])
  }

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/tasks`)
      if (res.ok) {
        const data = await res.json()
        setTasks(data)
      }
    } catch {
      // Backend not available yet — silent
    }
  }

  // ------------------------------------------------------------------
  // Screen capture
  // ------------------------------------------------------------------
  const startScreenShare = async () => {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { displaySurface: "browser" },  // Force tab-only selection
        audio: false,
        preferCurrentTab: false,                // Never capture our own tab
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.play()
      }
      setIsSharing(true)
      addLog('[System] 📸 Screen sharing started — AI can now see your screen.', 'success')

      // Stop sharing if user clicks browser "Stop sharing"
      stream.getVideoTracks()[0].onended = () => {
        stopScreenShare()
      }
    } catch (err) {
      addLog(`[System] Screen share denied or failed: ${err.message}`, 'error')
    }
  }

  const stopScreenShare = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (videoRef.current) videoRef.current.srcObject = null
    setIsSharing(false)
    addLog('[System] Screen sharing stopped.', 'system')
  }

  const captureFrame = () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || !video.videoWidth) return null

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0)
    // Return base64 JPEG without the data:image/jpeg;base64, prefix
    const dataUrl = canvas.toDataURL('image/jpeg', 0.8)
    return dataUrl.split(',')[1]
  }

  // ------------------------------------------------------------------
  // Command handlers
  // ------------------------------------------------------------------
  // Universal verdict display for 4-key schema
  // ------------------------------------------------------------------
  const formatVerdict = (verdict) => {
    if (!verdict) {
      addLog('[System] ⚠️ No verdict returned from swarm.', 'error')
      return
    }

    const { domain, decision, rag_context_used, reasoning } = verdict
    const domainTag = domain ? `[${domain.toUpperCase()}]` : '[UNKNOWN]'

    const decisionMap = {
      execute:  { emoji: '✅', label: 'EXECUTE',  type: 'success' },
      abort:    { emoji: '🛑', label: 'ABORT',    type: 'error' },
      inform:   { emoji: '📋', label: 'INFORM',   type: 'gamma-inform' },
      research: { emoji: '🔍', label: 'RESEARCH', type: 'gamma-research' },
    }

    const d = decisionMap[decision] || decisionMap.inform
    addLog(`[System] ${d.emoji} Swarm Verdict ${domainTag}: ${d.label} — ${reasoning || 'No reasoning provided'}`, d.type)

    if (rag_context_used && rag_context_used !== 'none') {
      addLog(`[RAG] 🌐 Context used: ${rag_context_used}`, 'rag')
    }
  }

  // ------------------------------------------------------------------
  const handleCommand = async (input) => {
    if (!input.trim()) return
    addLog(`[User] ${input}`, 'user')
    setIsProcessing(true)

    // Detect time context → schedule, otherwise instant/vision
    const timePatterns = /\b(at\s+\d{1,2}[:.]\d{2}|at\s+\d{1,2}\s*(am|pm)|tomorrow|tonight|schedule)\b/i
    const hasTimeContext = timePatterns.test(input)

    try {
      if (hasTimeContext) {
        await handleScheduleTask(input)
      } else if (isSharing) {
        await handleScreenAnalysis(input)
      } else {
        await handleInstantAnalyze(input)
      }
    } catch (err) {
      addLog(`[System] Error: ${err.message}`, 'error')
    } finally {
      setIsProcessing(false)
      fetchTasks()
    }
  }

  const handleScreenAnalysis = async (input) => {
    const frame = captureFrame()
    if (!frame) {
      addLog('[System] ⚠️ Could not capture screen frame — falling back to text analysis.', 'error')
      return handleInstantAnalyze(input)
    }

    addLog('[System] 📸 Screen frame captured — sending to Gemini Vision + Deep Scraper swarm …', 'swarm')

    const res = await fetch(`${API_BASE}/api/analyze-screen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: input, image_base64: frame }),
    })
    const data = await res.json()
    formatVerdict(data.verdict)
  }

  const handleScheduleTask = async (input) => {
    addLog('[System] Time context detected — scheduling task …', 'scheduler')

    // Try to extract time from input; default to +5 mins
    let runAt = new Date(Date.now() + 5 * 60000)
    const timeMatch = input.match(/at\s+(\d{1,2})[:.:](\d{2})\s*(am|pm)?/i)
    if (timeMatch) {
      let hours = parseInt(timeMatch[1], 10)
      const mins = parseInt(timeMatch[2], 10)
      const meridiem = timeMatch[3]?.toLowerCase()
      if (meridiem === 'pm' && hours < 12) hours += 12
      if (meridiem === 'am' && hours === 12) hours = 0
      runAt = new Date()
      runAt.setHours(hours, mins, 0, 0)
      if (runAt < new Date()) runAt.setDate(runAt.getDate() + 1)
    }

    const body = {
      description: input,
      run_at: runAt.toISOString(),
      scrape_url: 'https://www.google.com/finance',
      scrape_selector: 'body',
    }

    const res = await fetch(`${API_BASE}/schedule_task`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    addLog(`[System] Task scheduled: ${data.task?.id || 'OK'}`, 'success')
  }

  const handleInstantAnalyze = async (input) => {
    addLog('[System] Running instant swarm analysis …', 'swarm')

    const body = {
      text_data: input,
      force_vision: false,
    }

    const res = await fetch(`${API_BASE}/instant_analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    formatVerdict(data.verdict)
  }

  // ------------------------------------------------------------------
  // Shared OmniInput + SwarmTerminal for both inline and PiP rendering
  // ------------------------------------------------------------------
  const commandCenter = (
    <div className="space-y-6">
      <OmniInput
        onSubmit={handleCommand}
        isProcessing={isProcessing}
        isSharing={isSharing}
        isPiP={isPiP}
        onStartShare={startScreenShare}
        onStopShare={stopScreenShare}
        videoRef={videoRef}
      />
      <SwarmTerminal logs={logs} />
    </div>
  )

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-cream">
      {/* Hidden canvas for screen capture (video is now visible via OmniInput viewfinder) */}
      <video ref={videoRef} className="hidden" muted playsInline />
      <canvas ref={canvasRef} className="hidden" />

      {/* Header */}
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="border-b border-charcoal/5 px-8 py-6"
      >
        <div className="mx-auto max-w-6xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-slate-accent" />
              <div className="w-2 h-2 rounded-full bg-bronze-accent" />
              <div className="w-2 h-2 rounded-full bg-charcoal/20" />
            </div>
            <h1 className="font-serif text-2xl font-semibold tracking-tight text-charcoal">
              X10V
            </h1>
            <span className="text-xs font-sans text-charcoal-muted tracking-widest uppercase ml-2">
              Headless Semantic Automation
            </span>
          </div>

          <div className="flex items-center gap-4">
            {/* PiP Pop-Out Button */}
            <PiPAgent
              isOpen={isPiP}
              onOpen={() => setIsPiP(true)}
              onClose={() => setIsPiP(false)}
            >
              {commandCenter}
            </PiPAgent>

            <div className="flex items-center gap-3 text-xs font-sans text-charcoal-muted">
              <div className="flex items-center gap-1.5">
                <Zap size={12} className="text-terminal-cyan" />
                <span>Alpha</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Shield size={12} className="text-terminal-yellow" />
                <span>Beta</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Bot size={12} className="text-terminal-green" />
                <span>Gamma</span>
              </div>
            </div>
            <div
              className={`flex items-center gap-1.5 text-xs font-sans ${
                isConnected ? 'text-terminal-green' : 'text-terminal-red'
              }`}
            >
              <div
                className={`w-1.5 h-1.5 rounded-full ${
                  isConnected ? 'bg-terminal-green pulse-soft' : 'bg-terminal-red'
                }`}
              />
              {isConnected ? 'Live' : 'Offline'}
            </div>
          </div>
        </div>
      </motion.header>

      {/* Main content */}
      <main className="mx-auto max-w-6xl px-8 py-10 space-y-10">
        {/* Omni-Input + Terminal — only shown inline when PiP is NOT active */}
        {!isPiP ? (
          <>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15, ease: 'easeOut' }}
            >
              <OmniInput
                onSubmit={handleCommand}
                isProcessing={isProcessing}
                isSharing={isSharing}
                isPiP={false}
                onStartShare={startScreenShare}
                onStopShare={stopScreenShare}
                videoRef={videoRef}
              />
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3, ease: 'easeOut' }}
            >
              <SwarmTerminal logs={logs} />
            </motion.div>
          </>
        ) : (
          /* PiP active — show a placeholder in the main dashboard */
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-20 text-center"
          >
            <div className="w-16 h-16 rounded-2xl bg-terminal-cyan/10 flex items-center justify-center mb-4">
              <MonitorUp size={28} className="text-terminal-cyan" />
            </div>
            <h3 className="font-serif text-xl font-medium text-charcoal mb-2">
              Command Center is floating
            </h3>
            <p className="text-sm text-charcoal-muted max-w-md">
              The Agent Command Center and Swarm Terminal are running in the
              floating PiP window. Switch to your target tab — the AI will
              capture that tab instead of this dashboard.
            </p>
            <p className="text-xs text-charcoal-muted/50 mt-3">
              Screen capture is locked to the selected browser tab only.
            </p>
          </motion.div>
        )}

        {/* Task Queue */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.45, ease: 'easeOut' }}
        >
          <TaskQueue tasks={tasks} />
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="border-t border-charcoal/5 py-6 text-center">
        <p className="text-xs font-sans text-charcoal-muted tracking-wide">
          X10V · Built with FastAPI, Playwright, APScheduler · Multi-Agent Swarm Consensus
        </p>
      </footer>
    </div>
  )
}
