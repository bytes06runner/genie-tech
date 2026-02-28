/**
 * ArchitectureDoc — Full-page interactive architecture & documentation section.
 *
 * Renders at the bottom of the site, showcasing the X10V AI Swarm system
 * architecture with animated flow diagrams, tech stack cards, API reference,
 * and a visual pipeline breakdown. Designed with EQTY Lab-inspired dark
 * aesthetic — deep blacks, emerald accents, glass-morphism cards.
 *
 * @module ArchitectureDoc
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Brain,
  Mic,
  Youtube,
  MessageSquare,
  Globe,
  Database,
  Cpu,
  FileText,
  Zap,
  Shield,
  Bot,
  ArrowRight,
  ArrowDown,
  ChevronDown,
  ChevronUp,
  Terminal,
  Layers,
  GitBranch,
  Wifi,
  Eye,
  BookOpen,
  Code2,
  Server,
  Sparkles,
} from 'lucide-react'

/* ═══════════════════════════════════════════════════════════════════
   SECTION: Constants & Data
   ═══════════════════════════════════════════════════════════════════ */

/** Architecture nodes rendered in the visual flow diagram */
const FLOW_NODES = [
  {
    id: 'input',
    label: 'Omni-Channel Input',
    sub: 'Voice · Web · Telegram · YouTube',
    icon: Globe,
    color: 'from-blue-500 to-cyan-400',
    glow: 'shadow-blue-500/20',
  },
  {
    id: 'router',
    label: 'Intent Router',
    sub: 'Groq Llama-3.1-8b classifier',
    icon: GitBranch,
    color: 'from-purple-500 to-violet-400',
    glow: 'shadow-purple-500/20',
  },
  {
    id: 'swarm',
    label: 'AI Swarm Brain',
    sub: 'Alpha → Beta → Gamma agents',
    icon: Brain,
    color: 'from-emerald-500 to-green-400',
    glow: 'shadow-emerald-500/20',
  },
  {
    id: 'execute',
    label: 'Execution Layer',
    sub: 'Headless browser · Groww mock · Doc gen',
    icon: Cpu,
    color: 'from-orange-500 to-amber-400',
    glow: 'shadow-orange-500/20',
  },
  {
    id: 'output',
    label: 'Multi-Format Output',
    sub: 'JSON · Markdown · PDF · WebSocket',
    icon: FileText,
    color: 'from-rose-500 to-pink-400',
    glow: 'shadow-rose-500/20',
  },
]

/** The five input channels */
const CHANNELS = [
  { icon: Globe, label: 'Web Dashboard', desc: 'React + Vite real-time interface with OmniInput & Swarm Terminal', color: 'text-blue-400', border: 'border-blue-500/20', bg: 'bg-blue-500/5' },
  { icon: Mic, label: 'Voice AI', desc: 'Groq Llama-3.1-8b instant intent classification from speech', color: 'text-violet-400', border: 'border-violet-500/20', bg: 'bg-violet-500/5' },
  { icon: Youtube, label: 'YouTube Research', desc: 'Transcript extraction → domain-adaptive AI analysis → export', color: 'text-red-400', border: 'border-red-500/20', bg: 'bg-red-500/5' },
  { icon: MessageSquare, label: 'Telegram Bot', desc: '6 commands + natural language rules + Groww mock execution', color: 'text-cyan-400', border: 'border-cyan-500/20', bg: 'bg-cyan-500/5' },
  { icon: Eye, label: 'Screen Capture', desc: 'Browser tab capture → Gemini 2.5 Flash vision analysis', color: 'text-amber-400', border: 'border-amber-500/20', bg: 'bg-amber-500/5' },
]

/** The three swarm agents */
const AGENTS = [
  { icon: Zap, name: 'Alpha', role: 'Analyst', desc: 'Breaks down complex queries, identifies data requirements, and creates execution plans.', color: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30' },
  { icon: Shield, name: 'Beta', role: 'Critic', desc: 'Validates Alpha\'s analysis, checks for errors, assesses risk, and refines the plan.', color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30' },
  { icon: Bot, name: 'Gamma', role: 'Executor', desc: 'Synthesizes final output, triggers browser actions, document generation, or trade execution.', color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30' },
]

/** Backend modules reference */
const MODULES = [
  { name: 'server.py', desc: 'FastAPI router — 14 endpoints + WebSocket', icon: Server },
  { name: 'swarm_brain.py', desc: 'Gemini 2.5 Flash multi-agent orchestration', icon: Brain },
  { name: 'query_engine.py', desc: 'Semantic intent routing & query decomposition', icon: GitBranch },
  { name: 'yt_research.py', desc: 'YouTube transcript → Groq domain-adaptive summary', icon: Youtube },
  { name: 'voice_intent.py', desc: 'Groq speech intent classifier (8 intents)', icon: Mic },
  { name: 'rule_engine.py', desc: 'Dynamic rules + Groww mock executor + suggestions', icon: Layers },
  { name: 'memory_manager.py', desc: 'ChromaDB vector memory for context persistence', icon: Database },
  { name: 'headless_executor.py', desc: 'Playwright headless browser automation', icon: Terminal },
  { name: 'doc_generator.py', desc: 'Markdown/PDF/DOCX document pipeline', icon: FileText },
  { name: 'deep_scraper.py', desc: 'Multi-page web scraping with content extraction', icon: Globe },
  { name: 'scheduler_node.py', desc: 'APScheduler for deferred task execution', icon: Cpu },
  { name: 'tg_bot.py', desc: 'Telegram bot — 6 commands + NL rule parsing', icon: MessageSquare },
]

/** Tech stack items */
const TECH_STACK = [
  { category: 'AI / LLM', items: ['Gemini 2.5 Flash', 'Groq Llama-3.1-8b', 'ChromaDB Vectors'] },
  { category: 'Backend', items: ['FastAPI', 'Uvicorn', 'APScheduler', 'Playwright'] },
  { category: 'Frontend', items: ['React 18', 'Vite 6', 'Tailwind CSS', 'Framer Motion'] },
  { category: 'Integrations', items: ['Telegram Bot API', 'YouTube Transcript API', 'Groww Mock'] },
]

/** API endpoints reference */
const API_ENDPOINTS = [
  { method: 'POST', path: '/api/swarm', desc: 'Submit natural language command to the AI swarm' },
  { method: 'POST', path: '/api/youtube-research', desc: 'Analyze a YouTube video URL' },
  { method: 'POST', path: '/api/youtube-pdf', desc: 'Generate PDF export from summary' },
  { method: 'POST', path: '/api/voice-intent', desc: 'Classify voice/text intent via Groq' },
  { method: 'POST', path: '/api/rules', desc: 'Create a dynamic trading rule' },
  { method: 'GET', path: '/api/rules/:id', desc: 'List rules for a Telegram user' },
  { method: 'GET', path: '/api/trades/:id', desc: 'Get trade execution history' },
  { method: 'POST', path: '/api/bridge/signal', desc: 'Bridge signal from web → Telegram' },
  { method: 'POST', path: '/api/analyze-screen', desc: 'Send screen capture for Gemini vision' },
  { method: 'WS', path: '/ws', desc: 'Real-time swarm terminal log stream' },
]

/* ═══════════════════════════════════════════════════════════════════
   SECTION: Sub-Components
   ═══════════════════════════════════════════════════════════════════ */

/**
 * Section heading with animated emerald underline.
 * @param {{ label: string, title: string, subtitle?: string }} props
 */
function SectionHeading({ label, title, subtitle }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.6 }}
      className="text-center mb-16"
    >
      <span className="inline-block px-4 py-1.5 rounded-full border border-emerald-500/30 text-emerald-400 text-xs font-medium tracking-wider uppercase mb-4">
        {label}
      </span>
      <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-white tracking-tight mb-4">
        {title.split(' ').map((word, i) => (
          <span key={i}>
            {i === title.split(' ').length - 1 ? (
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-green-300">
                {word}
              </span>
            ) : (
              word + ' '
            )}
          </span>
        ))}
      </h2>
      {subtitle && (
        <p className="text-gray-400 max-w-2xl mx-auto text-base md:text-lg leading-relaxed">
          {subtitle}
        </p>
      )}
    </motion.div>
  )
}

/**
 * Animated connector arrow between flow nodes.
 * @param {{ vertical?: boolean }} props
 */
function FlowArrow({ vertical = false }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.5 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4 }}
      className={`flex items-center justify-center ${vertical ? 'py-2' : 'px-1'}`}
    >
      {vertical ? (
        <ArrowDown size={20} className="text-emerald-500/50" />
      ) : (
        <ArrowRight size={20} className="text-emerald-500/50 hidden md:block" />
      )}
    </motion.div>
  )
}

/**
 * Expandable API endpoint row.
 */
function ApiRow({ method, path, desc, index }) {
  const methodColors = {
    POST: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    GET: 'bg-green-500/20 text-green-400 border-green-500/30',
    WS: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.05, duration: 0.4 }}
      className="flex items-center gap-3 py-3 px-4 rounded-lg hover:bg-white/[0.02] transition-colors group"
    >
      <span className={`px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider border ${methodColors[method] || methodColors.POST}`}>
        {method}
      </span>
      <code className="text-sm font-mono text-emerald-400/80 group-hover:text-emerald-300 transition-colors min-w-[200px]">
        {path}
      </code>
      <span className="text-sm text-gray-500 group-hover:text-gray-400 transition-colors">
        {desc}
      </span>
    </motion.div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   SECTION: Main Export
   ═══════════════════════════════════════════════════════════════════ */

export default function ArchitectureDoc() {
  const [expandedModule, setExpandedModule] = useState(null)

  return (
    <section className="relative bg-[#0a0a0a] overflow-hidden">
      {/* Top gradient divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent" />
      <div className="h-32 bg-gradient-to-b from-[#0a0a0a] to-transparent pointer-events-none" />

      <div className="max-w-6xl mx-auto px-6 md:px-8 pb-24 space-y-32">

        {/* ═══════ 1. ARCHITECTURE FLOW ═══════ */}
        <div>
          <SectionHeading
            label="Architecture"
            title="System Architecture Flow"
            subtitle="End-to-end pipeline from omni-channel input to multi-format output, powered by a three-agent AI swarm."
          />

          {/* Flow diagram — horizontal on desktop, vertical on mobile */}
          <div className="flex flex-col md:flex-row items-center justify-center gap-2 md:gap-0">
            {FLOW_NODES.map((node, i) => (
              <div key={node.id} className="contents">
                <motion.div
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.12, duration: 0.5 }}
                  className={`relative group flex flex-col items-center p-5 rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm hover:bg-white/[0.04] transition-all duration-300 w-full md:w-40 shadow-lg ${node.glow}`}
                >
                  <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${node.color} flex items-center justify-center mb-3 shadow-lg group-hover:scale-110 transition-transform duration-300`}>
                    <node.icon size={22} className="text-white" />
                  </div>
                  <span className="text-sm font-semibold text-white text-center leading-tight">{node.label}</span>
                  <span className="text-[10px] text-gray-500 text-center mt-1 leading-snug">{node.sub}</span>
                </motion.div>
                {i < FLOW_NODES.length - 1 && <FlowArrow />}
                {i < FLOW_NODES.length - 1 && (
                  <div className="md:hidden">
                    <FlowArrow vertical />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* ═══════ 2. INPUT CHANNELS ═══════ */}
        <div>
          <SectionHeading
            label="Input Layer"
            title="Five Omni-Channel Inputs"
            subtitle="Users interact through any channel — the AI Swarm unifies intent and context across all of them."
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {CHANNELS.map((ch, i) => (
              <motion.div
                key={ch.label}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08, duration: 0.5 }}
                className={`group p-5 rounded-2xl border ${ch.border} ${ch.bg} backdrop-blur-sm hover:scale-[1.02] transition-all duration-300 cursor-default`}
              >
                <ch.icon size={28} className={`${ch.color} mb-3 group-hover:scale-110 transition-transform`} />
                <h4 className="text-sm font-semibold text-white mb-1">{ch.label}</h4>
                <p className="text-xs text-gray-500 leading-relaxed">{ch.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* ═══════ 3. THREE-AGENT SWARM ═══════ */}
        <div>
          <SectionHeading
            label="AI Core"
            title="Three-Agent Swarm Intelligence"
            subtitle="Inspired by adversarial collaboration — Analyst proposes, Critic validates, Executor delivers."
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {AGENTS.map((agent, i) => (
              <motion.div
                key={agent.name}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.15, duration: 0.6 }}
                className={`relative p-6 rounded-2xl border ${agent.border} ${agent.bg} backdrop-blur-sm overflow-hidden group`}
              >
                {/* Glow effect */}
                <div className={`absolute -top-20 -right-20 w-40 h-40 rounded-full ${agent.bg} blur-3xl opacity-0 group-hover:opacity-60 transition-opacity duration-500`} />
                
                <div className="relative z-10">
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`w-10 h-10 rounded-xl ${agent.bg} border ${agent.border} flex items-center justify-center`}>
                      <agent.icon size={20} className={agent.color} />
                    </div>
                    <div>
                      <h4 className={`text-lg font-bold ${agent.color}`}>{agent.name}</h4>
                      <span className="text-xs text-gray-500 uppercase tracking-wider">{agent.role}</span>
                    </div>
                  </div>
                  <p className="text-sm text-gray-400 leading-relaxed">{agent.desc}</p>
                </div>

                {/* Connector arrows between agents */}
                {i < AGENTS.length - 1 && (
                  <div className="hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2 z-20">
                    <ArrowRight size={16} className="text-emerald-500/30" />
                  </div>
                )}
              </motion.div>
            ))}
          </div>

          {/* Agent flow summary */}
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.5, duration: 0.6 }}
            className="mt-8 text-center"
          >
            <div className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-emerald-500/20 bg-emerald-500/5">
              <Sparkles size={14} className="text-emerald-400" />
              <span className="text-xs text-emerald-400/80 font-medium">
                Alpha analyzes → Beta validates → Gamma executes — all powered by Gemini 2.5 Flash
              </span>
            </div>
          </motion.div>
        </div>

        {/* ═══════ 4. BACKEND MODULES ═══════ */}
        <div>
          <SectionHeading
            label="Backend"
            title="Modular Backend Architecture"
            subtitle="12 independent Python modules orchestrated by FastAPI — each module owns a single responsibility."
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {MODULES.map((mod, i) => (
              <motion.div
                key={mod.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.04, duration: 0.4 }}
                className="group flex items-start gap-3 p-4 rounded-xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] hover:border-emerald-500/20 transition-all duration-300 cursor-default"
              >
                <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                  <mod.icon size={16} className="text-emerald-400" />
                </div>
                <div>
                  <code className="text-sm font-mono text-white/90 group-hover:text-emerald-300 transition-colors">
                    {mod.name}
                  </code>
                  <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{mod.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* ═══════ 5. TECH STACK ═══════ */}
        <div>
          <SectionHeading
            label="Stack"
            title="Technology Stack"
            subtitle="Production-grade tools chosen for speed, reliability, and developer experience."
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {TECH_STACK.map((group, i) => (
              <motion.div
                key={group.category}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1, duration: 0.5 }}
                className="p-5 rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm"
              >
                <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-3">
                  {group.category}
                </h4>
                <div className="space-y-2">
                  {group.items.map((item) => (
                    <div key={item} className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/50" />
                      <span className="text-sm text-gray-300">{item}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* ═══════ 6. API REFERENCE ═══════ */}
        <div>
          <SectionHeading
            label="API"
            title="API Endpoints Reference"
            subtitle="14 RESTful endpoints + 1 WebSocket channel — all served by FastAPI on port 8000."
          />

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-5 py-3 border-b border-white/[0.06] bg-white/[0.01]">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
              </div>
              <code className="text-xs text-gray-500 font-mono">http://localhost:8000</code>
            </div>

            {/* Endpoints list */}
            <div className="divide-y divide-white/[0.04]">
              {API_ENDPOINTS.map((ep, i) => (
                <ApiRow key={ep.path} {...ep} index={i} />
              ))}
            </div>
          </motion.div>
        </div>

        {/* ═══════ 7. DATA FLOW PIPELINE ═══════ */}
        <div>
          <SectionHeading
            label="Pipeline"
            title="End-to-End Data Pipeline"
            subtitle="Every user query travels through this pipeline — from raw input to polished output."
          />

          <div className="relative">
            {/* Vertical timeline line */}
            <div className="absolute left-6 md:left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-emerald-500/40 via-emerald-500/20 to-transparent" />

            {[
              { step: '01', title: 'Input Capture', desc: 'Voice, text, URL, or screen capture is received from any channel.', icon: Globe, side: 'left' },
              { step: '02', title: 'Intent Classification', desc: 'Groq Llama-3.1-8b classifies intent in <100ms — analyze_stock, youtube_research, create_rule, etc.', icon: GitBranch, side: 'right' },
              { step: '03', title: 'Context Enrichment', desc: 'ChromaDB vector memory retrieves relevant past interactions. Live RAG pulls fresh data.', icon: Database, side: 'left' },
              { step: '04', title: 'Swarm Processing', desc: 'Alpha analyzes → Beta critiques → Gamma synthesizes. Three Gemini 2.5 Flash calls in sequence.', icon: Brain, side: 'right' },
              { step: '05', title: 'Execution', desc: 'Headless browser actions, Groww mock trades, document generation, or Telegram notifications.', icon: Cpu, side: 'left' },
              { step: '06', title: 'Output Delivery', desc: 'Results streamed via WebSocket, exported as JSON/Markdown/PDF, or forwarded to Telegram.', icon: Zap, side: 'right' },
            ].map((item, i) => (
              <motion.div
                key={item.step}
                initial={{ opacity: 0, x: item.side === 'left' ? -40 : 40 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ delay: i * 0.1, duration: 0.5 }}
                className={`relative flex items-start gap-6 mb-12 ${
                  item.side === 'right' ? 'md:flex-row-reverse md:text-right' : ''
                }`}
              >
                {/* Timeline dot */}
                <div className="absolute left-6 md:left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-emerald-500 border-2 border-[#0a0a0a] z-10 shadow-lg shadow-emerald-500/30" />

                {/* Content card */}
                <div className={`ml-14 md:ml-0 md:w-5/12 ${item.side === 'right' ? 'md:mr-auto md:pl-10' : 'md:ml-auto md:pr-10'}`}>
                  <div className="p-5 rounded-xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] transition-colors group">
                    <div className={`flex items-center gap-3 mb-2 ${item.side === 'right' ? 'md:flex-row-reverse' : ''}`}>
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                        <item.icon size={16} className="text-emerald-400" />
                      </div>
                      <div>
                        <span className="text-[10px] text-emerald-500/60 font-mono font-bold">STEP {item.step}</span>
                        <h4 className="text-sm font-semibold text-white">{item.title}</h4>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500 leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

      </div>

      {/* ═══════ FOOTER ═══════ */}
      <div className="border-t border-white/[0.06]">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-12">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-emerald-500" />
                <div className="w-2 h-2 rounded-full bg-emerald-500/50" />
                <div className="w-2 h-2 rounded-full bg-emerald-500/20" />
              </div>
              <span className="text-xl font-bold text-white tracking-tight">X10V</span>
              <span className="text-xs text-gray-600 uppercase tracking-widest">AI Swarm</span>
            </div>

            <div className="flex items-center gap-6 text-xs text-gray-600">
              <span>React 18 + Vite 6</span>
              <span className="text-gray-800">·</span>
              <span>FastAPI + Gemini 2.5 Flash</span>
              <span className="text-gray-800">·</span>
              <span>Groq Llama-3.1-8b</span>
            </div>

            <div className="flex items-center gap-2">
              <a
                href="https://github.com/bytes06runner/genie-tech"
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 rounded-lg border border-white/[0.08] bg-white/[0.02] text-xs text-gray-400 hover:text-white hover:border-emerald-500/30 transition-all"
              >
                <Code2 size={12} className="inline mr-1.5" />
                GitHub
              </a>
              <span className="text-xs text-gray-700">
                © 2026 X10V · Omni-Channel Autonomous Intelligence
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
