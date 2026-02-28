import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, Loader2, Zap, Brain, Volume2, ChevronRight } from 'lucide-react'

const API_BASE = 'http://localhost:8000'

const INTENT_COLORS = {
  analyze_stock: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', emoji: '📊' },
  summarize_video: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', emoji: '🎬' },
  set_automation: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', emoji: '⚙️' },
  trade: { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400', emoji: '💹' },
  monitor: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/30', text: 'text-cyan-400', emoji: '📡' },
  portfolio: { bg: 'bg-indigo-500/10', border: 'border-indigo-500/30', text: 'text-indigo-400', emoji: '💼' },
  general_query: { bg: 'bg-gray-500/10', border: 'border-gray-500/30', text: 'text-gray-400', emoji: '💬' },
}

export default function VoiceAssistant({ onIntentAction, onBroadcast }) {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [interimTranscript, setInterimTranscript] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [intentResult, setIntentResult] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const recognitionRef = useRef(null)

  // Initialize Web Speech API
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setError('Web Speech API not supported. Use Chrome or Edge.')
      return
    }

    const recognition = new SpeechRecognition()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = 'en-US'
    recognition.maxAlternatives = 1

    recognition.onresult = (event) => {
      let interim = ''
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          final += t
        } else {
          interim += t
        }
      }
      if (final) setTranscript((prev) => (prev + ' ' + final).trim())
      setInterimTranscript(interim)
    }

    recognition.onerror = (event) => {
      if (event.error !== 'no-speech') {
        setError(`Speech recognition error: ${event.error}`)
      }
      setIsListening(false)
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    recognitionRef.current = recognition

    return () => {
      recognition.abort()
    }
  }, [])

  const toggleListening = useCallback(() => {
    if (!recognitionRef.current) return

    if (isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
      // Auto-process if we have transcript
      if (transcript.trim()) {
        processTranscript(transcript.trim())
      }
    } else {
      setTranscript('')
      setInterimTranscript('')
      setIntentResult(null)
      setError(null)
      recognitionRef.current.start()
      setIsListening(true)
    }
  }, [isListening, transcript])

  const processTranscript = async (text) => {
    if (!text) return
    setIsProcessing(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/api/voice-intent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: text }),
      })

      if (!res.ok) throw new Error(`Server error: ${res.status}`)

      const data = await res.json()
      const intent = data.intent

      setIntentResult(intent)
      setHistory((prev) => [{ text, intent, timestamp: new Date() }, ...prev].slice(0, 10))

      // Execute the intent action if callback provided
      if (onIntentAction) {
        onIntentAction(intent)
      }

      // Send to Telegram bridge if it's an automation/trade intent
      if (['set_automation', 'trade', 'monitor'].includes(intent.intent)) {
        try {
          await fetch(`${API_BASE}/api/bridge/signal`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              tg_user_id: 0,
              signal_type: 'voice_command',
              payload: { command: text, intent: intent.intent, entities: intent.entities },
            }),
          })
        } catch {
          // Bridge signal is best-effort
        }
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setIsProcessing(false)
    }
  }

  const confidenceColor = (score) => {
    if (score >= 0.8) return 'text-terminal-green'
    if (score >= 0.5) return 'text-terminal-yellow'
    return 'text-terminal-red'
  }

  const intentStyle = intentResult
    ? INTENT_COLORS[intentResult.intent] || INTENT_COLORS.general_query
    : null

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Brain size={14} className="text-purple-400" />
          <h2 className="font-serif text-lg font-medium text-charcoal">
            Voice AI
          </h2>
          <span className="text-xs font-sans text-charcoal-muted ml-1">
            RNN-style intent classifier
          </span>
        </div>
        {isListening && (
          <span className="flex items-center gap-1.5 text-xs text-terminal-red font-medium animate-pulse">
            <span className="w-2 h-2 rounded-full bg-terminal-red" />
            RECORDING
          </span>
        )}
      </div>

      <div className="rounded-xl border border-charcoal/8 bg-white p-5 shadow-sm space-y-4">
        {/* Mic Button */}
        <div className="flex items-center gap-4">
          <motion.button
            onClick={toggleListening}
            disabled={isProcessing}
            whileTap={{ scale: 0.95 }}
            className={`relative p-5 rounded-2xl transition-all duration-300 ${
              isListening
                ? 'bg-terminal-red/10 border-2 border-terminal-red/40 text-terminal-red shadow-lg shadow-red-500/10'
                : 'bg-charcoal/5 border-2 border-charcoal/10 text-charcoal-muted hover:border-purple-400/40 hover:text-purple-500'
            } ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isListening ? (
              <>
                <MicOff size={28} />
                {/* Pulse rings */}
                <motion.div
                  className="absolute inset-0 rounded-2xl border-2 border-terminal-red/30"
                  animate={{ scale: [1, 1.3, 1], opacity: [0.5, 0, 0.5] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                />
              </>
            ) : isProcessing ? (
              <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                <Loader2 size={28} />
              </motion.div>
            ) : (
              <Mic size={28} />
            )}
          </motion.button>

          <div className="flex-1">
            <div className="text-sm font-sans text-charcoal min-h-[2.5rem]">
              {isListening ? (
                <span className="text-charcoal-muted">
                  {transcript || interimTranscript || 'Listening…'}
                  {interimTranscript && (
                    <span className="text-charcoal-muted/50 italic"> {interimTranscript}</span>
                  )}
                </span>
              ) : transcript ? (
                <span>"{transcript}"</span>
              ) : (
                <span className="text-charcoal-muted/60">
                  Tap the mic and speak a command like "Analyze Apple stock" or "Set automation for gold"
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1 text-xs text-charcoal-muted/50">
              <Volume2 size={10} />
              <span>Web Speech API → Groq Llama-3.1-8b → Structured Intent</span>
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="text-sm text-terminal-red bg-terminal-red/5 rounded-lg px-3 py-2 border border-terminal-red/20">
            ⚠️ {error}
          </div>
        )}

        {/* Intent Result Card */}
        <AnimatePresence>
          {intentResult && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className={`rounded-xl border ${intentStyle.border} ${intentStyle.bg} p-4 space-y-3`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{intentStyle.emoji}</span>
                  <span className={`text-sm font-semibold uppercase tracking-wide ${intentStyle.text}`}>
                    {intentResult.intent?.replace(/_/g, ' ')}
                  </span>
                </div>
                <span className={`text-xs font-mono font-bold ${confidenceColor(intentResult.confidence_score)}`}>
                  {(intentResult.confidence_score * 100).toFixed(0)}% confidence
                </span>
              </div>

              {/* Entities */}
              {intentResult.entities && Object.keys(intentResult.entities).length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(intentResult.entities).map(([key, val]) => (
                    <span key={key} className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-white/60 border border-charcoal/5 text-xs font-mono">
                      <span className="text-charcoal-muted">{key}:</span>
                      <span className="font-semibold text-charcoal">{String(val)}</span>
                    </span>
                  ))}
                </div>
              )}

              {/* Suggested Action */}
              {intentResult.suggested_action && (
                <div className="flex items-start gap-2 text-xs text-charcoal-muted">
                  <Zap size={12} className="mt-0.5 text-bronze-accent shrink-0" />
                  <span>{intentResult.suggested_action}</span>
                </div>
              )}

              {/* Action button */}
              {onIntentAction && (
                <button
                  onClick={() => onIntentAction(intentResult)}
                  className="w-full py-2 rounded-lg bg-charcoal text-cream text-sm font-medium
                             hover:bg-charcoal-light transition-colors"
                >
                  <Zap size={14} className="inline mr-1.5" />
                  Execute: {intentResult.suggested_action?.slice(0, 50) || 'Process command'}
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* History */}
        {history.length > 0 && (
          <div className="border-t border-charcoal/5 pt-3">
            <span className="text-xs font-sans text-charcoal-muted/50 uppercase tracking-wider">
              Recent Commands
            </span>
            <div className="mt-2 space-y-1.5">
              {history.slice(0, 3).map((h, i) => {
                const style = INTENT_COLORS[h.intent?.intent] || INTENT_COLORS.general_query
                return (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span>{style.emoji}</span>
                    <span className="text-charcoal-muted truncate flex-1">"{h.text}"</span>
                    <span className={`${style.text} font-mono`}>
                      {h.intent?.intent?.replace(/_/g, ' ')}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
