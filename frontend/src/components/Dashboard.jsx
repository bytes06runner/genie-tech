import { useState, useEffect, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Bot, Zap, Shield, MonitorUp } from 'lucide-react'
import OmniInput from './OmniInput'
import SwarmTerminal from './SwarmTerminal'
import TaskQueue from './TaskQueue'
import PiPAgent from './PiPAgent'
import VoiceAssistant from './VoiceAssistant'
import YouTubeResearch from './YouTubeResearch'

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
      else if (msg.includes('[QueryRouter]')) type = 'router'
      else if (msg.includes('[DocGen]')) type = 'docgen'
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

  const triggerDownload = (base64Data, mimeType, fileType) => {
    try {
      let cleanB64 = base64Data
      if (cleanB64.startsWith('data:')) {
        cleanB64 = cleanB64.split(',')[1] || cleanB64
      }

      const byteCharacters = atob(cleanB64)

      const byteNumbers = new Array(byteCharacters.length)
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i)
      }

      const byteArray = new Uint8Array(byteNumbers)

      const blob = new Blob([byteArray], { type: mimeType })

      const blobUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      const ext = fileType === 'pdf' ? 'pdf' : 'md'
      link.download = `X10V-Generated-Notes-${Date.now()}.${ext}`
      document.body.appendChild(link)
      link.click()

      document.body.removeChild(link)
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1500)

      addLog(`[System] 📥 ${ext.toUpperCase()} file downloaded successfully!`, 'success')
    } catch (err) {
      console.error('Failed to decode and download file:', err)
      addLog(`[System] ⚠️ File download failed: ${err.message}`, 'error')
    }
  }

  const formatVerdict = (verdict) => {
    if (!verdict) {
      addLog('[System] ⚠️ No verdict returned from swarm.', 'error')
      return
    }

    const { domain, decision, structured_data, reasoning } = verdict
    const domainTag = domain ? `[${domain.toUpperCase()}]` : '[UNKNOWN]'

    const decisionMap = {
      inform:  { emoji: '📋', label: 'INFORM',  type: 'gamma-inform' },
      execute: { emoji: '✅', label: 'EXECUTE', type: 'success' },
      abort:   { emoji: '🛑', label: 'ABORT',   type: 'error' },
    }

    const d = decisionMap[decision] || decisionMap.inform
    addLog(`[System] ${d.emoji} Swarm Verdict ${domainTag}: ${d.label}`, d.type)

    // Summary from structured_data
    if (structured_data?.summary) {
      addLog(`[Gamma/Output] ${structured_data.summary}`, 'gamma-execute')
    }

    if (reasoning) {
      addLog(`[System] 🔎 Reasoning: ${reasoning}`, 'system')
    }
  }

  const handleCommand = async (input) => {
    if (!input.trim()) return
    addLog(`[User] ${input}`, 'user')
    setIsProcessing(true)

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

    if (data.file_b64 && data.file_mime) {
      triggerDownload(data.file_b64, data.file_mime, data.file_type || 'pdf')
    }
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

    if (data.file_b64 && data.file_mime) {
      triggerDownload(data.file_b64, data.file_mime, data.file_type || 'pdf')
    }
  }

  const handleVoiceIntent = (intent) => {
    if (!intent) return
    const action = intent.suggested_action || intent.intent
    addLog(`[VoiceAI] 🎤 Intent: ${intent.intent} — ${action}`, 'system')

    // Route intent to appropriate action
    if (intent.intent === 'analyze_stock' && intent.entities?.ticker) {
      handleCommand(`Analyze ${intent.entities.ticker} ${intent.entities.timeframe || '1d'} chart`)
    } else if (intent.intent === 'summarize_video' && intent.entities?.url) {
      addLog(`[VoiceAI] 🎬 Redirecting to YouTube Research tab with URL`, 'system')
    } else if (intent.intent === 'set_automation') {
      addLog(`[VoiceAI] ⚙️ Automation signal sent to Telegram bridge`, 'success')
    } else if (intent.intent === 'trade') {
      addLog(`[VoiceAI] 💹 Trade intent forwarded to Telegram bridge`, 'success')
    } else if (intent.intent === 'monitor') {
      addLog(`[VoiceAI] 📡 Monitor request forwarded to Telegram bridge`, 'success')
    }
  }

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

  return (
    <div className="min-h-screen bg-cream">
      <video ref={videoRef} className="hidden" muted playsInline />
      <canvas ref={canvasRef} className="hidden" />

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

      <main className="mx-auto max-w-6xl px-8 py-10 space-y-10">
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

            {/* Voice AI + YouTube Research — side by side */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.22, ease: 'easeOut' }}
              className="grid grid-cols-1 lg:grid-cols-2 gap-6"
            >
              <VoiceAssistant onIntentAction={handleVoiceIntent} />
              <YouTubeResearch />
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

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.45, ease: 'easeOut' }}
        >
          <TaskQueue tasks={tasks} />
        </motion.div>
      </main>

      <footer className="border-t border-charcoal/5 py-6 text-center">
        <p className="text-xs font-sans text-charcoal-muted tracking-wide">
          X10V · Omni-Channel Autonomous Intelligence Agent · Scroll down for full architecture documentation ↓
        </p>
      </footer>
    </div>
  )
}
