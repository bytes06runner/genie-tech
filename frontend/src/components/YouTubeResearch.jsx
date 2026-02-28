import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Youtube,
  Loader2,
  FileJson,
  FileText,
  FileDown,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Lightbulb,
  BarChart3,
  Download,
  BookOpen,
  Sparkles,
  Tag,
} from 'lucide-react'

const API_BASE = 'http://localhost:8000'

const TONE_CONFIG = {
  informative: { color: 'text-blue-500', bg: 'bg-blue-500/10', border: 'border-blue-500/30', icon: BookOpen },
  educational: { color: 'text-indigo-500', bg: 'bg-indigo-500/10', border: 'border-indigo-500/30', icon: BookOpen },
  analytical: { color: 'text-cyan-500', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30', icon: BarChart3 },
  persuasive: { color: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/30', icon: TrendingUp },
  entertaining: { color: 'text-pink-500', bg: 'bg-pink-500/10', border: 'border-pink-500/30', icon: Sparkles },
  inspirational: { color: 'text-terminal-green', bg: 'bg-green-500/10', border: 'border-green-500/30', icon: TrendingUp },
  neutral: { color: 'text-terminal-yellow', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', icon: Minus },
}

const DOMAIN_COLORS = {
  science: 'bg-purple-100 text-purple-700 border-purple-200',
  technology: 'bg-cyan-100 text-cyan-700 border-cyan-200',
  finance: 'bg-green-100 text-green-700 border-green-200',
  education: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  history: 'bg-amber-100 text-amber-700 border-amber-200',
  health: 'bg-rose-100 text-rose-700 border-rose-200',
  entertainment: 'bg-pink-100 text-pink-700 border-pink-200',
  philosophy: 'bg-violet-100 text-violet-700 border-violet-200',
  engineering: 'bg-slate-100 text-slate-700 border-slate-200',
  other: 'bg-gray-100 text-gray-700 border-gray-200',
}

export default function YouTubeResearch() {
  const [url, setUrl] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!url.trim()) return

    setIsLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await fetch(`${API_BASE}/api/youtube-research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      })

      const data = await res.json()

      if (data.status === 'error' || data.error) {
        setError(data.error || 'Unknown error')
      } else {
        setResult(data)
      }
    } catch (err) {
      setError(`Network error: ${err.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const downloadJSON = () => {
    if (!result?.exports?.json) return
    const blob = new Blob([result.exports.json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `x10v-yt-research-${result.video_id || 'summary'}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadMarkdown = () => {
    if (!result?.exports?.markdown) return
    const blob = new Blob([result.exports.markdown], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `x10v-yt-research-${result.video_id || 'summary'}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadPDF = async () => {
    if (!result?.summary) return
    setIsGeneratingPDF(true)
    try {
      const res = await fetch(`${API_BASE}/api/youtube-pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summary: result.summary }),
      })
      const data = await res.json()
      if (data.file_b64) {
        const byteChars = atob(data.file_b64)
        const byteNumbers = new Uint8Array(byteChars.length)
        for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i)
        const blob = new Blob([byteNumbers], { type: data.file_mime || 'application/pdf' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `x10v-yt-research-${result.video_id || 'summary'}.pdf`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (err) {
      setError(`PDF generation failed: ${err.message}`)
    } finally {
      setIsGeneratingPDF(false)
    }
  }

  const summary = result?.summary
  const toneKey = summary?.tone?.toLowerCase() || 'neutral'
  const toneStyle = TONE_CONFIG[toneKey] || TONE_CONFIG.neutral
  const ToneIcon = toneStyle.icon
  const domainKey = summary?.domain?.toLowerCase() || 'other'
  const domainStyle = DOMAIN_COLORS[domainKey] || DOMAIN_COLORS.other

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Youtube size={14} className="text-terminal-red" />
        <h2 className="font-serif text-lg font-medium text-charcoal">
          YouTube Deep Research
        </h2>
        <span className="text-xs font-sans text-charcoal-muted ml-1">
          Transcript → Groq AI → Deep Research Summary
        </span>
      </div>

      <div className="rounded-xl border border-charcoal/8 bg-white shadow-sm overflow-hidden">
        {/* URL Input */}
        <form onSubmit={handleSubmit} className="p-4 border-b border-charcoal/5">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Youtube size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-terminal-red/50" />
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Paste YouTube URL — e.g. https://youtube.com/watch?v=..."
                disabled={isLoading}
                className="w-full pl-10 pr-4 py-3 text-sm font-sans text-charcoal bg-cream/50
                           border border-charcoal/8 rounded-xl
                           placeholder:text-charcoal-muted/50
                           focus:outline-none focus:border-terminal-red/30 focus:ring-1 focus:ring-terminal-red/10
                           disabled:opacity-50 transition-all"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || !url.trim()}
              className="px-5 py-3 rounded-xl bg-charcoal text-cream text-sm font-medium
                         hover:bg-charcoal-light disabled:opacity-30 disabled:cursor-not-allowed
                         transition-all flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                    <Loader2 size={16} />
                  </motion.div>
                  Analyzing…
                </>
              ) : (
                <>
                  <BarChart3 size={16} />
                  Research
                </>
              )}
            </button>
          </div>
        </form>

        {/* Error */}
        {error && (
          <div className="mx-4 my-3 text-sm text-terminal-red bg-terminal-red/5 rounded-lg px-4 py-3 border border-terminal-red/20 flex items-start gap-2">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Results */}
        <AnimatePresence>
          {result && summary && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="p-5 space-y-5"
            >
              {/* Header: title + sentiment + export buttons */}
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <h3 className="font-serif text-base font-semibold text-charcoal leading-snug">
                    {summary.title_inferred || 'YouTube Research Summary'}
                  </h3>
                  <div className="flex items-center gap-3 mt-2">
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${domainStyle}`}>
                      <Tag size={10} />
                      {summary.domain?.charAt(0).toUpperCase() + summary.domain?.slice(1)}
                    </span>
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
                                     ${toneStyle.color} ${toneStyle.bg} border ${toneStyle.border}`}>
                      <ToneIcon size={12} />
                      {summary.tone?.charAt(0).toUpperCase() + summary.tone?.slice(1)}
                      {summary.complexity_score != null && (
                        <span className="ml-1 opacity-70">({(summary.complexity_score * 100).toFixed(0)}% complex)</span>
                      )}
                    </span>
                    <span className="text-xs text-charcoal-muted">
                      {summary.content_type?.replace(/_/g, ' ')} · {result.transcript_length?.toLocaleString()} chars
                      {result.duration_seconds > 0 && ` · ${Math.floor(result.duration_seconds / 60)}m`}
                    </span>
                  </div>
                </div>

                {/* Export buttons */}
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={downloadJSON}
                    title="Download JSON"
                    className="p-2 rounded-lg border border-charcoal/8 text-charcoal-muted hover:text-blue-500 hover:border-blue-500/30 transition-colors"
                  >
                    <FileJson size={16} />
                  </button>
                  <button
                    onClick={downloadMarkdown}
                    title="Download Markdown"
                    className="p-2 rounded-lg border border-charcoal/8 text-charcoal-muted hover:text-green-500 hover:border-green-500/30 transition-colors"
                  >
                    <FileText size={16} />
                  </button>
                  <button
                    onClick={downloadPDF}
                    disabled={isGeneratingPDF}
                    title="Download PDF"
                    className="p-2 rounded-lg border border-charcoal/8 text-charcoal-muted hover:text-red-500 hover:border-red-500/30 disabled:opacity-50 transition-colors"
                  >
                    {isGeneratingPDF ? (
                      <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                        <Loader2 size={16} />
                      </motion.div>
                    ) : (
                      <FileDown size={16} />
                    )}
                  </button>
                </div>
              </div>

              {/* Summary */}
              <div>
                <h4 className="text-xs font-sans text-charcoal-muted/60 uppercase tracking-wider mb-2">Summary</h4>
                <p className="text-sm leading-relaxed text-charcoal/90">{summary.summary}</p>
              </div>

              {/* Key Points */}
              {summary.key_points?.length > 0 && (
                <div>
                  <h4 className="text-xs font-sans text-charcoal-muted/60 uppercase tracking-wider mb-2">Key Points</h4>
                  <div className="space-y-1.5">
                    {summary.key_points.map((point, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm text-charcoal/80">
                        <span className="text-bronze-accent mt-0.5 shrink-0">{i + 1}.</span>
                        <span>{point}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Two-column: Deep Insights + Caveats */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {summary.deep_insights?.length > 0 && (
                  <div className="rounded-lg bg-emerald-50/50 border border-emerald-200/50 p-3">
                    <h4 className="text-xs font-sans text-emerald-700/70 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <Lightbulb size={12} />
                      Deep Insights
                    </h4>
                    {summary.deep_insights.map((insight, i) => (
                      <p key={i} className="text-xs text-emerald-800/80 mb-1">💡 {insight}</p>
                    ))}
                  </div>
                )}

                {summary.important_warnings?.length > 0 && (
                  <div className="rounded-lg bg-amber-50/50 border border-amber-200/50 p-3">
                    <h4 className="text-xs font-sans text-amber-700/70 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <AlertTriangle size={12} />
                      Caveats & Limitations
                    </h4>
                    {summary.important_warnings.map((warning, i) => (
                      <p key={i} className="text-xs text-amber-800/80 mb-1">⚠️ {warning}</p>
                    ))}
                  </div>
                )}
              </div>

              {/* Key Topics */}
              {summary.mentioned_topics?.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-charcoal-muted/60">Topics:</span>
                  {summary.mentioned_topics.map((topic, i) => (
                    <span key={i} className="px-2 py-0.5 rounded-md bg-charcoal/5 border border-charcoal/8 text-xs font-mono font-semibold text-charcoal">
                      {topic}
                    </span>
                  ))}
                </div>
              )}

              {/* Actionable Takeaways */}
              {summary.actionable_takeaways?.length > 0 && (
                <div className="rounded-lg bg-blue-50/50 border border-blue-200/50 p-3">
                  <h4 className="text-xs font-sans text-blue-700/70 uppercase tracking-wider mb-2">
                    ✅ Actionable Takeaways
                  </h4>
                  {summary.actionable_takeaways.map((action, i) => (
                    <p key={i} className="text-xs text-blue-800/80 mb-1">→ {action}</p>
                  ))}
                </div>
              )}

              {/* Download bar */}
              <div className="flex items-center gap-3 pt-3 border-t border-charcoal/5">
                <Download size={12} className="text-charcoal-muted/50" />
                <span className="text-xs text-charcoal-muted/50">
                  Export as
                </span>
                <button onClick={downloadJSON} className="text-xs text-blue-500 hover:underline font-medium">JSON</button>
                <span className="text-charcoal-muted/30">·</span>
                <button onClick={downloadMarkdown} className="text-xs text-green-500 hover:underline font-medium">Markdown</button>
                <span className="text-charcoal-muted/30">·</span>
                <button onClick={downloadPDF} disabled={isGeneratingPDF} className="text-xs text-red-500 hover:underline font-medium disabled:opacity-50">
                  {isGeneratingPDF ? 'Generating…' : 'PDF'}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Empty state */}
        {!result && !isLoading && !error && (
          <div className="p-6 text-center">
            <Youtube size={32} className="mx-auto text-charcoal-muted/20 mb-2" />
            <p className="text-sm text-charcoal-muted/50">
              Paste any YouTube URL to get an AI-powered deep research summary
            </p>
            <p className="text-xs text-charcoal-muted/30 mt-1">
              Transcript extraction → Groq Llama-3.1-8b → Domain-adaptive analysis → JSON / Markdown / PDF export
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
