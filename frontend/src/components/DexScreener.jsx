import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, TrendingUp, ArrowUpRight, ArrowDownRight, Loader2, RefreshCw, Bell, BellOff, ExternalLink } from 'lucide-react'

const API_BASE = 'http://localhost:8000'

function BuySellBar({ buys, sells }) {
  const total = buys + sells
  if (total === 0) return <div className="h-2 bg-charcoal/10 rounded-full" />
  const buyPct = (buys / total) * 100
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-charcoal/10 rounded-full overflow-hidden flex">
        <div className="h-full bg-emerald-500 rounded-l-full transition-all" style={{ width: `${buyPct}%` }} />
        <div className="h-full bg-red-500 rounded-r-full transition-all" style={{ width: `${100 - buyPct}%` }} />
      </div>
      <span className="text-[10px] text-charcoal-muted font-mono whitespace-nowrap">
        {buys}B / {sells}S
      </span>
    </div>
  )
}

function PriceChange({ value }) {
  if (value === 0 || value === null || value === undefined) {
    return <span className="text-charcoal-muted font-mono text-xs">0.00%</span>
  }
  const isPositive = value > 0
  return (
    <span className={`font-mono text-xs flex items-center gap-0.5 ${isPositive ? 'text-emerald-500' : 'text-red-500'}`}>
      {isPositive ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
      {Math.abs(value).toFixed(2)}%
    </span>
  )
}

function TokenCard({ token, index }) {
  const ratio = token.buy_sell_ratio_1h
  const ratioStr = ratio === Infinity ? '∞' : ratio >= 999 ? '∞' : ratio === 0 ? '0' : ratio?.toFixed(2) || '—'
  const sentiment = ratio > 1.5 ? 'Bullish' : ratio > 1.0 ? 'Neutral' : 'Bearish'
  const sentimentColor = ratio > 1.5 ? 'text-emerald-500' : ratio > 1.0 ? 'text-yellow-500' : 'text-red-500'
  const sentimentBg = ratio > 1.5 ? 'bg-emerald-500/10' : ratio > 1.0 ? 'bg-yellow-500/10' : 'bg-red-500/10'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="bg-white border border-charcoal/5 rounded-xl p-4 hover:border-charcoal/15 transition-all"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-charcoal text-sm">{token.symbol}</h3>
            <span className="text-[10px] text-charcoal-muted bg-charcoal/5 px-1.5 py-0.5 rounded">
              {token.chain}
            </span>
            <span className="text-[10px] text-charcoal-muted">
              {token.dex}
            </span>
          </div>
          <p className="text-xs text-charcoal-muted mt-0.5">{token.name} / {token.quote_symbol}</p>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${sentimentBg} ${sentimentColor}`}>
          {sentiment}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <p className="text-[10px] text-charcoal-muted uppercase tracking-wider">Price</p>
          <p className="font-mono text-sm font-medium text-charcoal">
            ${Number(token.price_usd || 0).toFixed(token.price_usd < 0.01 ? 8 : 4)}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-charcoal-muted uppercase tracking-wider">Volume 24h</p>
          <p className="font-mono text-sm font-medium text-charcoal">
            ${(token.volume_24h || 0).toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-charcoal-muted uppercase tracking-wider">Liquidity</p>
          <p className="font-mono text-sm text-charcoal">
            ${(token.liquidity_usd || 0).toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-charcoal-muted uppercase tracking-wider">Market Cap</p>
          <p className="font-mono text-sm text-charcoal">
            {token.market_cap ? `$${token.market_cap.toLocaleString()}` : 'N/A'}
          </p>
        </div>
      </div>

      {/* Price Changes */}
      <div className="flex items-center gap-3 mb-3">
        <div className="text-center">
          <p className="text-[9px] text-charcoal-muted">5m</p>
          <PriceChange value={token.price_change_5m} />
        </div>
        <div className="text-center">
          <p className="text-[9px] text-charcoal-muted">1h</p>
          <PriceChange value={token.price_change_1h} />
        </div>
        <div className="text-center">
          <p className="text-[9px] text-charcoal-muted">6h</p>
          <PriceChange value={token.price_change_6h} />
        </div>
        <div className="text-center">
          <p className="text-[9px] text-charcoal-muted">24h</p>
          <PriceChange value={token.price_change_24h} />
        </div>
      </div>

      {/* Buy/Sell Bars */}
      <div className="space-y-1.5">
        <div>
          <p className="text-[9px] text-charcoal-muted mb-0.5">1h Buyers vs Sellers</p>
          <BuySellBar buys={token.buys_1h || 0} sells={token.sells_1h || 0} />
        </div>
        <div>
          <p className="text-[9px] text-charcoal-muted mb-0.5">24h Buyers vs Sellers</p>
          <BuySellBar buys={token.buys_24h || 0} sells={token.sells_24h || 0} />
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-charcoal/5 flex items-center justify-between">
        <span className="text-[10px] text-charcoal-muted font-mono">
          B/S Ratio: {ratioStr} | TXNs: {(token.total_txns_24h || 0).toLocaleString()}
        </span>
        {token.url && (
          <a
            href={token.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-terminal-cyan hover:underline flex items-center gap-0.5"
          >
            DEX Screener <ExternalLink size={8} />
          </a>
        )}
      </div>
    </motion.div>
  )
}

export default function DexScreener() {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [trendingTokens, setTrendingTokens] = useState([])
  const [aiAnalysis, setAiAnalysis] = useState(null)
  const [isSearching, setIsSearching] = useState(false)
  const [isTrendingLoading, setIsTrendingLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('trending')
  const [error, setError] = useState(null)

  const fetchTrending = useCallback(async () => {
    setIsTrendingLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/dex/trending`)
      if (!res.ok) throw new Error('Failed to fetch trending')
      const data = await res.json()
      setTrendingTokens(data.tokens || [])
      setAiAnalysis(data.analysis || null)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsTrendingLoading(false)
    }
  }, [])

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setIsSearching(true)
    setError(null)
    setActiveTab('search')
    try {
      const res = await fetch(`${API_BASE}/api/dex/search?q=${encodeURIComponent(searchQuery)}`)
      if (!res.ok) throw new Error('Search failed')
      const data = await res.json()
      setSearchResults(data.pairs || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSearching(false)
    }
  }

  useEffect(() => {
    fetchTrending()
  }, [fetchTrending])

  const tokens = activeTab === 'search' ? searchResults : trendingTokens
  const isLoading = activeTab === 'search' ? isSearching : isTrendingLoading

  return (
    <div className="bg-white border border-charcoal/5 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-charcoal/5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 flex items-center justify-center">
              <TrendingUp size={16} className="text-emerald-600" />
            </div>
            <div>
              <h2 className="font-serif text-lg font-semibold text-charcoal">DEX Screener</h2>
              <p className="text-[10px] text-charcoal-muted">Real-time on-chain token intelligence</p>
            </div>
          </div>
          <button
            onClick={fetchTrending}
            disabled={isTrendingLoading}
            className="p-2 rounded-lg hover:bg-charcoal/5 transition-colors"
          >
            <RefreshCw size={14} className={`text-charcoal-muted ${isTrendingLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Search Bar */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="flex-1 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-charcoal-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search any token (PEPE, BONK, SOL/USDC…)"
              className="w-full pl-9 pr-3 py-2 text-sm bg-cream border border-charcoal/10 rounded-lg focus:outline-none focus:border-terminal-cyan focus:ring-1 focus:ring-terminal-cyan/20 text-charcoal placeholder:text-charcoal-muted/50"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching || !searchQuery.trim()}
            className="px-4 py-2 bg-charcoal text-cream text-sm font-medium rounded-lg hover:bg-charcoal/90 transition-colors disabled:opacity-50"
          >
            {isSearching ? <Loader2 size={14} className="animate-spin" /> : 'Search'}
          </button>
        </form>

        {/* Tabs */}
        <div className="flex gap-4 mt-3">
          <button
            onClick={() => setActiveTab('trending')}
            className={`text-xs font-medium pb-1 border-b-2 transition-colors ${activeTab === 'trending' ? 'border-terminal-cyan text-charcoal' : 'border-transparent text-charcoal-muted hover:text-charcoal'}`}
          >
            🔥 Trending
          </button>
          <button
            onClick={() => setActiveTab('search')}
            className={`text-xs font-medium pb-1 border-b-2 transition-colors ${activeTab === 'search' ? 'border-terminal-cyan text-charcoal' : 'border-transparent text-charcoal-muted hover:text-charcoal'}`}
          >
            🔍 Search Results {searchResults.length > 0 && `(${searchResults.length})`}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-xs text-red-700">
            ⚠️ {error}
          </div>
        )}

        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-12 text-charcoal-muted">
            <Loader2 size={24} className="animate-spin mb-2" />
            <p className="text-sm">
              {activeTab === 'search' ? 'Searching DEX Screener…' : 'Fetching trending tokens + AI analysis…'}
            </p>
          </div>
        ) : tokens.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-charcoal-muted">
            <Search size={24} className="mb-2 opacity-50" />
            <p className="text-sm">
              {activeTab === 'search' ? 'Search for any token to see buyer/seller data' : 'No trending tokens available'}
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {tokens.map((token, i) => (
                <TokenCard key={`${token.symbol}-${token.chain}-${token.pair_address}-${i}`} token={token} index={i} />
              ))}
            </div>

            {/* AI Analysis Panel */}
            {aiAnalysis && activeTab === 'trending' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 bg-gradient-to-br from-terminal-cyan/5 to-emerald-50 border border-terminal-cyan/20 rounded-xl p-4"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm">🧠</span>
                  <h3 className="font-semibold text-sm text-charcoal">AI Swarm Analysis</h3>
                  <span className="text-[10px] bg-terminal-cyan/10 text-terminal-cyan px-2 py-0.5 rounded-full">
                    3-LLM Verdict
                  </span>
                </div>
                {aiAnalysis.structured_data?.summary && (
                  <p className="text-xs text-charcoal-muted leading-relaxed">
                    {aiAnalysis.structured_data.summary}
                  </p>
                )}
                {aiAnalysis.structured_data?.timeline_or_metrics?.length > 0 && (
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {aiAnalysis.structured_data.timeline_or_metrics.slice(0, 6).map((m, i) => (
                      <div key={i} className="bg-white/60 rounded-lg px-3 py-2">
                        <p className="text-[10px] text-charcoal-muted">{m.key}</p>
                        <p className="text-xs font-medium text-charcoal">{m.value}</p>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="px-6 py-3 border-t border-charcoal/5 bg-cream/50 flex items-center justify-between">
        <span className="text-[10px] text-charcoal-muted">
          Powered by DEX Screener API · Free, no API key
        </span>
        <a
          href="https://dexscreener.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] text-terminal-cyan hover:underline flex items-center gap-1"
        >
          dexscreener.com <ExternalLink size={8} />
        </a>
      </div>
    </div>
  )
}
