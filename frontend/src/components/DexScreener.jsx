import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, TrendingUp, ArrowUpRight, ArrowDownRight, Loader2, RefreshCw,
  ExternalLink, Wallet, Bot, ShoppingCart, X, ChevronDown, ChevronUp,
  Zap, Target, Shield, Clock, CheckCircle, XCircle, AlertTriangle,
  Activity, BarChart3, Settings
} from 'lucide-react'

const API_BASE = 'http://localhost:8000'

function BuySellBar({ buys, sells }) {
  const total = buys + sells
  if (total === 0) return <div className="h-2 bg-charcoal/10 rounded-full" />
  const buyPct = (buys / total) * 100
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-charcoal/10 rounded-full overflow-hidden flex">
        <div className="h-full bg-emerald-500 rounded-l-full transition-all" style={{ width: buyPct + '%' }} />
        <div className="h-full bg-red-500 rounded-r-full transition-all" style={{ width: (100 - buyPct) + '%' }} />
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
    <span className={'font-mono text-xs flex items-center gap-0.5 ' + (isPositive ? 'text-emerald-500' : 'text-red-500')}>
      {isPositive ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
      {Math.abs(value).toFixed(2)}%
    </span>
  )
}

function formatPrice(price) {
  const p = Number(price || 0)
  if (p >= 1) return '$' + p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (p >= 0.001) return '$' + p.toFixed(4)
  if (p >= 0.0000001) return '$' + p.toFixed(8)
  return '$' + p.toExponential(4)
}

function formatUsd(value) {
  const v = Number(value || 0)
  if (v >= 1000000) return '$' + (v / 1000000).toFixed(2) + 'M'
  if (v >= 1000) return '$' + (v / 1000).toFixed(1) + 'K'
  return '$' + v.toFixed(0)
}

function StatusBadge({ status }) {
  const colors = {
    active: 'bg-blue-500/10 text-blue-600 border-blue-200',
    executed: 'bg-emerald-500/10 text-emerald-600 border-emerald-200',
    cancelled: 'bg-charcoal/5 text-charcoal-muted border-charcoal/10',
  }
  const icons = {
    active: <Clock size={10} />,
    executed: <CheckCircle size={10} />,
    cancelled: <XCircle size={10} />,
  }
  return (
    <span className={'inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border ' + (colors[status] || colors.active)}>
      {icons[status]} {status}
    </span>
  )
}

function WalletPanel({ walletAddress, setWalletAddress, walletBalance, setWalletBalance }) {
  const [input, setInput] = useState('')
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')

  const connectWallet = async () => {
    const addr = input.trim()
    if (!addr || addr.length !== 58) {
      setError('Invalid Algorand address (58 chars)')
      return
    }
    setChecking(true)
    setError('')
    try {
      const res = await fetch(API_BASE + '/api/dex/wallet/balance?address=' + addr)
      if (!res.ok) throw new Error('Could not verify address on TestNet')
      const data = await res.json()
      setWalletAddress(addr)
      setWalletBalance(data)
      localStorage.setItem('x10v_wallet', addr)
    } catch (err) {
      setError(err.message)
    } finally {
      setChecking(false)
    }
  }

  const disconnectWallet = () => {
    setWalletAddress('')
    setWalletBalance(null)
    localStorage.removeItem('x10v_wallet')
  }

  if (walletAddress) {
    return (
      <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3">
        <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0">
          <Wallet size={14} className="text-emerald-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-emerald-700 truncate font-mono">
            {walletAddress.slice(0, 8)}...{walletAddress.slice(-6)}
          </p>
          {walletBalance && (
            <p className="text-[10px] text-emerald-600/70">
              {walletBalance.balance_algo?.toFixed(4)} ALGO | {walletBalance.available_algo?.toFixed(4)} available
            </p>
          )}
        </div>
        <span className="text-[9px] bg-emerald-500/20 text-emerald-700 px-2 py-0.5 rounded-full shrink-0">On-Chain</span>
        <button onClick={disconnectWallet} className="p-1 hover:bg-emerald-200 rounded-lg transition shrink-0">
          <X size={14} className="text-emerald-600" />
        </button>
      </div>
    )
  }

  return (
    <div className="bg-charcoal/[0.02] border border-charcoal/10 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Wallet size={14} className="text-charcoal-muted" />
        <p className="text-xs font-medium text-charcoal">Connect Algorand Wallet <span className="text-charcoal-muted font-normal">(optional - enables on-chain auto-trades)</span></p>
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => { setInput(e.target.value); setError('') }}
          placeholder="Paste Algorand TestNet address..."
          className="flex-1 px-3 py-2 text-xs bg-white border border-charcoal/10 rounded-lg focus:outline-none focus:border-terminal-cyan font-mono"
        />
        <button
          onClick={connectWallet}
          disabled={checking || !input.trim()}
          className="px-4 py-2 bg-charcoal text-cream text-xs font-medium rounded-lg hover:bg-charcoal/90 transition disabled:opacity-50"
        >
          {checking ? <Loader2 size={12} className="animate-spin" /> : 'Connect'}
        </button>
      </div>
      {error && <p className="text-[10px] text-red-500 mt-2">{error}</p>}
      <p className="text-[10px] text-charcoal-muted mt-2">
        Without wallet: Paper trades ($1,000 demo). With wallet: Creates on-chain Algorand transactions.
      </p>
    </div>
  )
}

function AiAnalysisPanel({ symbol, chain, onCreateOrder, walletAddress }) {
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const runAnalysis = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(API_BASE + '/api/dex/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: symbol, chain: chain }),
      })
      if (!res.ok) throw new Error('Analysis failed')
      setAnalysis(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleOneClickOrder = () => {
    if (!analysis) return
    onCreateOrder({
      symbol: symbol,
      chain: chain,
      side: analysis.recommendation === 'sell' ? 'sell' : 'buy',
      target_price: analysis.entry_price,
      stop_loss: analysis.stop_loss || 0,
      take_profit: analysis.target_price || 0,
      wallet_address: walletAddress,
      search_query: symbol,
    })
  }

  const recColors = {
    buy: 'text-emerald-600 bg-emerald-50 border-emerald-200',
    sell: 'text-red-600 bg-red-50 border-red-200',
    hold: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  }

  return (
    <div className="mt-3 border-t border-charcoal/5 pt-3">
      {!analysis && !loading && (
        <button
          onClick={runAnalysis}
          className="w-full flex items-center justify-center gap-2 py-2 bg-gradient-to-r from-terminal-cyan/10 to-emerald-50 border border-terminal-cyan/20 rounded-lg text-xs font-medium text-terminal-cyan hover:from-terminal-cyan/20 hover:to-emerald-100 transition"
        >
          <Bot size={14} /> Ask AI: Should I trade {symbol}?
        </button>
      )}

      {loading && (
        <div className="flex items-center justify-center gap-2 py-4 text-charcoal-muted">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-xs">3-LLM Swarm analyzing {symbol}...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-2 text-xs text-red-600 flex items-center gap-1">
          <AlertTriangle size={12} /> {error}
        </div>
      )}

      {analysis && (
        <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
          <div className="flex items-center justify-between">
            <div className={'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold ' + (recColors[analysis.recommendation] || recColors.hold)}>
              {analysis.recommendation === 'buy' && <ArrowUpRight size={14} />}
              {analysis.recommendation === 'sell' && <ArrowDownRight size={14} />}
              {analysis.recommendation === 'hold' && <Activity size={14} />}
              AI: {analysis.recommendation?.toUpperCase()}
              <span className="opacity-60">({((analysis.confidence || 0) * 100).toFixed(0)}%)</span>
            </div>
            <button onClick={runAnalysis} className="p-1 hover:bg-charcoal/5 rounded">
              <RefreshCw size={12} className="text-charcoal-muted" />
            </button>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="bg-charcoal/[0.03] rounded-lg px-2 py-1.5">
              <p className="text-[9px] text-charcoal-muted">Entry</p>
              <p className="text-xs font-mono font-medium">{formatPrice(analysis.entry_price)}</p>
            </div>
            <div className="bg-emerald-50 rounded-lg px-2 py-1.5">
              <p className="text-[9px] text-emerald-600">Target</p>
              <p className="text-xs font-mono font-medium text-emerald-700">{formatPrice(analysis.target_price)}</p>
            </div>
            <div className="bg-red-50 rounded-lg px-2 py-1.5">
              <p className="text-[9px] text-red-500">Stop Loss</p>
              <p className="text-xs font-mono font-medium text-red-600">{formatPrice(analysis.stop_loss)}</p>
            </div>
          </div>

          {analysis.reason && (
            <p className="text-[11px] text-charcoal-muted leading-relaxed bg-charcoal/[0.02] rounded-lg p-2 italic">
              {analysis.reason.slice(0, 300)}
            </p>
          )}

          {analysis.recommendation !== 'hold' && (
            <button
              onClick={handleOneClickOrder}
              className={'w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-semibold text-white transition ' + (analysis.recommendation === 'buy' ? 'bg-emerald-500 hover:bg-emerald-600' : 'bg-red-500 hover:bg-red-600')}
            >
              <Zap size={14} />
              Auto-{analysis.recommendation?.toUpperCase()} {symbol}
              {walletAddress ? ' (On-Chain)' : ' (Paper)'}
            </button>
          )}
        </motion.div>
      )}
    </div>
  )
}

function TokenCard({ token, index, onCreateOrder, walletAddress }) {
  const [expanded, setExpanded] = useState(false)
  const [showOrderForm, setShowOrderForm] = useState(false)

  const ratio = token.buy_sell_ratio_1h
  const ratioStr = ratio === Infinity ? '\u221E' : ratio >= 999 ? '\u221E' : ratio === 0 ? '0' : ratio?.toFixed(2) || '\u2014'
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
            <span className="text-[10px] text-charcoal-muted bg-charcoal/5 px-1.5 py-0.5 rounded">{token.chain}</span>
            <span className="text-[10px] text-charcoal-muted">{token.dex}</span>
          </div>
          <p className="text-xs text-charcoal-muted mt-0.5">{token.name} / {token.quote_symbol}</p>
        </div>
        <span className={'text-[10px] px-2 py-0.5 rounded-full font-medium ' + sentimentBg + ' ' + sentimentColor}>
          {sentiment}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <p className="text-[10px] text-charcoal-muted uppercase tracking-wider">Price</p>
          <p className="font-mono text-sm font-medium text-charcoal">{formatPrice(token.price_usd)}</p>
        </div>
        <div>
          <p className="text-[10px] text-charcoal-muted uppercase tracking-wider">Volume 24h</p>
          <p className="font-mono text-sm font-medium text-charcoal">{formatUsd(token.volume_24h)}</p>
        </div>
        <div>
          <p className="text-[10px] text-charcoal-muted uppercase tracking-wider">Liquidity</p>
          <p className="font-mono text-sm text-charcoal">{formatUsd(token.liquidity_usd)}</p>
        </div>
        <div>
          <p className="text-[10px] text-charcoal-muted uppercase tracking-wider">Market Cap</p>
          <p className="font-mono text-sm text-charcoal">{token.market_cap ? formatUsd(token.market_cap) : 'N/A'}</p>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-3">
        {[['5m', token.price_change_5m], ['1h', token.price_change_1h], ['6h', token.price_change_6h], ['24h', token.price_change_24h]].map(function(item) {
          return (
            <div key={item[0]} className="text-center">
              <p className="text-[9px] text-charcoal-muted">{item[0]}</p>
              <PriceChange value={item[1]} />
            </div>
          )
        })}
      </div>

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
          B/S: {ratioStr} | TXNs: {(token.total_txns_24h || 0).toLocaleString()}
        </span>
        <div className="flex items-center gap-2">
          {token.url && (
            <a href={token.url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-terminal-cyan hover:underline flex items-center gap-0.5">
              DEX Screener <ExternalLink size={8} />
            </a>
          )}
          <button onClick={function() { setExpanded(!expanded) }} className="p-1 hover:bg-charcoal/5 rounded transition">
            {expanded ? <ChevronUp size={12} className="text-charcoal-muted" /> : <ChevronDown size={12} className="text-charcoal-muted" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <AiAnalysisPanel
              symbol={token.symbol}
              chain={token.chain}
              onCreateOrder={onCreateOrder}
              walletAddress={walletAddress}
            />
            <div className="mt-3 border-t border-charcoal/5 pt-3">
              {!showOrderForm ? (
                <button
                  onClick={function() { setShowOrderForm(true) }}
                  className="w-full flex items-center justify-center gap-2 py-2 border border-dashed border-charcoal/20 rounded-lg text-xs text-charcoal-muted hover:border-charcoal/40 hover:text-charcoal transition"
                >
                  <Settings size={12} /> Custom Auto-Trade Order
                </button>
              ) : (
                <OrderForm
                  token={token}
                  walletAddress={walletAddress}
                  onSubmit={onCreateOrder}
                  onCancel={function() { setShowOrderForm(false) }}
                />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function OrderForm({ token, walletAddress, onSubmit, onCancel }) {
  const price = Number(token.price_usd || 0)
  const defaultPrice = price >= 1 ? price.toFixed(2) : price >= 0.001 ? price.toFixed(6) : price.toFixed(10)
  const [side, setSide] = useState('buy')
  const [targetPrice, setTargetPrice] = useState(defaultPrice)
  const [amountUsd, setAmountUsd] = useState('100')
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfit, setTakeProfit] = useState('')

  const handleSubmit = function() {
    var tp = parseFloat(targetPrice)
    if (!tp || tp <= 0) return
    onSubmit({
      symbol: token.symbol,
      chain: token.chain,
      dex: token.dex,
      side: side,
      target_price: tp,
      amount_usd: parseFloat(amountUsd) || 100,
      stop_loss: parseFloat(stopLoss) || 0,
      take_profit: parseFloat(takeProfit) || 0,
      wallet_address: walletAddress,
      pair_address: token.pair_address || '',
      search_query: token.symbol,
    })
    onCancel()
  }

  return (
    <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-charcoal flex items-center gap-1.5">
          <Target size={12} /> Set Auto-Trade for {token.symbol}
        </h4>
        <button onClick={onCancel} className="p-1 hover:bg-charcoal/5 rounded">
          <X size={12} className="text-charcoal-muted" />
        </button>
      </div>

      <div className="flex rounded-lg border border-charcoal/10 overflow-hidden">
        <button
          onClick={function() { setSide('buy') }}
          className={'flex-1 py-2 text-xs font-semibold transition ' + (side === 'buy' ? 'bg-emerald-500 text-white' : 'bg-white text-charcoal-muted hover:bg-charcoal/5')}
        >
          BUY when price drops
        </button>
        <button
          onClick={function() { setSide('sell') }}
          className={'flex-1 py-2 text-xs font-semibold transition ' + (side === 'sell' ? 'bg-red-500 text-white' : 'bg-white text-charcoal-muted hover:bg-charcoal/5')}
        >
          SELL when price rises
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-charcoal-muted">Target Price ($)</label>
          <input type="text" value={targetPrice} onChange={function(e) { setTargetPrice(e.target.value) }}
            className="w-full mt-0.5 px-2 py-1.5 text-xs font-mono bg-cream border border-charcoal/10 rounded-lg focus:outline-none focus:border-terminal-cyan" />
        </div>
        <div>
          <label className="text-[10px] text-charcoal-muted">Amount (USD)</label>
          <input type="text" value={amountUsd} onChange={function(e) { setAmountUsd(e.target.value) }}
            className="w-full mt-0.5 px-2 py-1.5 text-xs font-mono bg-cream border border-charcoal/10 rounded-lg focus:outline-none focus:border-terminal-cyan" />
        </div>
        <div>
          <label className="text-[10px] text-charcoal-muted">Stop Loss ($)</label>
          <input type="text" value={stopLoss} onChange={function(e) { setStopLoss(e.target.value) }} placeholder="Optional"
            className="w-full mt-0.5 px-2 py-1.5 text-xs font-mono bg-cream border border-charcoal/10 rounded-lg focus:outline-none focus:border-terminal-cyan placeholder:text-charcoal-muted/30" />
        </div>
        <div>
          <label className="text-[10px] text-charcoal-muted">Take Profit ($)</label>
          <input type="text" value={takeProfit} onChange={function(e) { setTakeProfit(e.target.value) }} placeholder="Optional"
            className="w-full mt-0.5 px-2 py-1.5 text-xs font-mono bg-cream border border-charcoal/10 rounded-lg focus:outline-none focus:border-terminal-cyan placeholder:text-charcoal-muted/30" />
        </div>
      </div>

      <div className="flex items-center gap-2 text-[10px] text-charcoal-muted bg-charcoal/[0.02] rounded-lg px-3 py-2">
        <Shield size={10} />
        <span>AI Swarm re-analyzes before executing. {walletAddress ? 'On-chain mode active.' : 'Paper trading mode.'}</span>
      </div>

      <button
        onClick={handleSubmit}
        className={'w-full py-2.5 rounded-lg text-xs font-semibold text-white transition flex items-center justify-center gap-2 ' + (side === 'buy' ? 'bg-emerald-500 hover:bg-emerald-600' : 'bg-red-500 hover:bg-red-600')}
      >
        <Zap size={14} /> Set Auto-{side.toUpperCase()} Order
      </button>
    </motion.div>
  )
}

function OrdersPanel({ orders, onCancel }) {
  var activeOrders = orders.filter(function(o) { return o.status === 'active' })
  var historyOrders = orders.filter(function(o) { return o.status !== 'active' })

  if (orders.length === 0) {
    return (
      <div className="text-center py-8 text-charcoal-muted">
        <ShoppingCart size={24} className="mx-auto mb-2 opacity-40" />
        <p className="text-xs">No orders yet. Expand any token card, ask AI or set a custom auto-trade.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {activeOrders.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-charcoal mb-2 flex items-center gap-1.5">
            <Activity size={12} className="text-blue-500" /> Active Orders ({activeOrders.length})
          </h4>
          <div className="space-y-2">
            {activeOrders.map(function(order) {
              return (
                <div key={order.id} className="bg-blue-50/50 border border-blue-200/50 rounded-lg p-3">
                  <div className="flex items-start justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className={'text-[10px] font-bold px-1.5 py-0.5 rounded ' + (order.side === 'buy' ? 'bg-emerald-500/20 text-emerald-700' : 'bg-red-500/20 text-red-700')}>
                        {order.side?.toUpperCase()}
                      </span>
                      <span className="text-xs font-semibold text-charcoal">{order.symbol}</span>
                      {order.chain && <span className="text-[9px] text-charcoal-muted bg-charcoal/5 px-1 rounded">{order.chain}</span>}
                    </div>
                    <button onClick={function() { onCancel(order.id) }} className="text-[10px] text-red-500 hover:text-red-700 font-medium">
                      Cancel
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[10px]">
                    <div><span className="text-charcoal-muted">Target:</span><span className="font-mono ml-1">{formatPrice(order.target_price)}</span></div>
                    <div><span className="text-charcoal-muted">Amount:</span><span className="font-mono ml-1">${order.amount_usd}</span></div>
                    <div><span className="text-charcoal-muted">Current:</span><span className="font-mono ml-1">{order.current_price ? formatPrice(order.current_price) : '-'}</span></div>
                  </div>
                  {order.ai_reason && (
                    <p className="text-[9px] text-charcoal-muted mt-1 italic truncate">AI: {order.ai_reason.slice(0, 120)}</p>
                  )}
                  {order.wallet_address && (
                    <p className="text-[9px] text-emerald-600 mt-0.5 flex items-center gap-0.5">
                      <Wallet size={8} /> On-chain: {order.wallet_address.slice(0, 8)}...
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {historyOrders.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-charcoal mb-2 flex items-center gap-1.5">
            <BarChart3 size={12} /> History ({historyOrders.length})
          </h4>
          <div className="space-y-1.5">
            {historyOrders.slice(0, 10).map(function(order) {
              return (
                <div key={order.id} className="bg-charcoal/[0.02] border border-charcoal/5 rounded-lg px-3 py-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={'text-[9px] font-bold px-1 py-0.5 rounded ' + (order.side === 'buy' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-red-500/10 text-red-600')}>
                      {order.side?.toUpperCase()}
                    </span>
                    <span className="text-[11px] font-medium text-charcoal">{order.symbol}</span>
                    <span className="text-[10px] font-mono text-charcoal-muted">@ {formatPrice(order.target_price)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {order.status === 'executed' && order.ai_score > 0 && (
                      <span className="text-[9px] text-emerald-600">AI: {(order.ai_score * 100).toFixed(0)}%</span>
                    )}
                    <StatusBadge status={order.status} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
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

  const [walletAddress, setWalletAddress] = useState(function() {
    return localStorage.getItem('x10v_wallet') || ''
  })
  const [walletBalance, setWalletBalance] = useState(null)
  const [orders, setOrders] = useState([])

  useEffect(function() {
    if (walletAddress) {
      fetch(API_BASE + '/api/dex/wallet/balance?address=' + walletAddress)
        .then(function(r) { return r.ok ? r.json() : null })
        .then(function(d) { if (d) setWalletBalance(d) })
        .catch(function() {})
    }
  }, [walletAddress])

  var fetchOrders = useCallback(async function() {
    try {
      var res = await fetch(API_BASE + '/api/dex/orders?user_id=web')
      if (res.ok) {
        var data = await res.json()
        setOrders(data.orders || [])
      }
    } catch (e) {
      // ignore
    }
  }, [])

  useEffect(function() {
    fetchOrders()
    var iv = setInterval(fetchOrders, 15000)
    return function() { clearInterval(iv) }
  }, [fetchOrders])

  var fetchTrending = useCallback(async function() {
    setIsTrendingLoading(true)
    setError(null)
    try {
      var res = await fetch(API_BASE + '/api/dex/trending')
      if (!res.ok) throw new Error('Failed to fetch trending')
      var data = await res.json()
      setTrendingTokens(data.tokens || [])
      setAiAnalysis(data.analysis || null)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsTrendingLoading(false)
    }
  }, [])

  var handleSearch = async function(e) {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setIsSearching(true)
    setError(null)
    setActiveTab('search')
    try {
      var res = await fetch(API_BASE + '/api/dex/search?q=' + encodeURIComponent(searchQuery))
      if (!res.ok) throw new Error('Search failed')
      var data = await res.json()
      setSearchResults(data.pairs || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSearching(false)
    }
  }

  useEffect(function() { fetchTrending() }, [fetchTrending])

  var handleCreateOrder = async function(orderData) {
    try {
      var body = {}
      for (var k in orderData) body[k] = orderData[k]
      body.amount_usd = orderData.amount_usd || 100
      var res = await fetch(API_BASE + '/api/dex/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error('Failed to create order')
      await fetchOrders()
      setActiveTab('orders')
    } catch (err) {
      setError(err.message)
    }
  }

  var handleCancelOrder = async function(orderId) {
    try {
      await fetch(API_BASE + '/api/dex/orders/' + orderId, { method: 'DELETE' })
      await fetchOrders()
    } catch (e) {
      // ignore
    }
  }

  var tokens = activeTab === 'search' ? searchResults : trendingTokens
  var isLoading = activeTab === 'search' ? isSearching : isTrendingLoading
  var activeCount = orders.filter(function(o) { return o.status === 'active' }).length

  return (
    <div className="bg-white border border-charcoal/5 rounded-2xl overflow-hidden">
      <div className="px-6 py-4 border-b border-charcoal/5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 flex items-center justify-center">
              <TrendingUp size={16} className="text-emerald-600" />
            </div>
            <div>
              <h2 className="font-serif text-lg font-semibold text-charcoal">DEX Screener</h2>
              <p className="text-[10px] text-charcoal-muted">Real-time intelligence + AI auto-trading</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {activeCount > 0 && (
              <span className="text-[10px] bg-blue-500/10 text-blue-600 px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
                <Activity size={10} /> {activeCount} active
              </span>
            )}
            <button onClick={fetchTrending} disabled={isTrendingLoading} className="p-2 rounded-lg hover:bg-charcoal/5 transition-colors">
              <RefreshCw size={14} className={'text-charcoal-muted ' + (isTrendingLoading ? 'animate-spin' : '')} />
            </button>
          </div>
        </div>

        <WalletPanel
          walletAddress={walletAddress}
          setWalletAddress={setWalletAddress}
          walletBalance={walletBalance}
          setWalletBalance={setWalletBalance}
        />

        <form onSubmit={handleSearch} className="flex gap-2 mt-3">
          <div className="flex-1 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-charcoal-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={function(e) { setSearchQuery(e.target.value) }}
              placeholder="Search any token (PEPE, BONK, SOL/USDC...)"
              className="w-full pl-9 pr-3 py-2 text-sm bg-cream border border-charcoal/10 rounded-lg focus:outline-none focus:border-terminal-cyan focus:ring-1 focus:ring-terminal-cyan/20 text-charcoal placeholder:text-charcoal-muted/50"
            />
          </div>
          <button type="submit" disabled={isSearching || !searchQuery.trim()}
            className="px-4 py-2 bg-charcoal text-cream text-sm font-medium rounded-lg hover:bg-charcoal/90 transition-colors disabled:opacity-50">
            {isSearching ? <Loader2 size={14} className="animate-spin" /> : 'Search'}
          </button>
        </form>

        <div className="flex gap-4 mt-3">
          {[
            { id: 'trending', label: 'Trending' },
            { id: 'search', label: 'Search', count: searchResults.length },
            { id: 'orders', label: 'My Orders', count: orders.length },
          ].map(function(tab) {
            return (
              <button
                key={tab.id}
                onClick={function() { setActiveTab(tab.id) }}
                className={'text-xs font-medium pb-1 border-b-2 transition-colors flex items-center gap-1 ' + (activeTab === tab.id ? 'border-terminal-cyan text-charcoal' : 'border-transparent text-charcoal-muted hover:text-charcoal')}
              >
                {tab.label}
                {tab.count > 0 && tab.id !== 'trending' && (
                  <span className="text-[9px] bg-charcoal/5 px-1.5 rounded-full">{tab.count}</span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      <div className="p-4">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-xs text-red-700 flex items-center gap-2">
            <AlertTriangle size={14} /> {error}
            <button onClick={function() { setError(null) }} className="ml-auto text-red-400 hover:text-red-600">
              <X size={12} />
            </button>
          </div>
        )}

        {activeTab === 'orders' ? (
          <OrdersPanel orders={orders} onCancel={handleCancelOrder} />
        ) : isLoading ? (
          <div className="flex flex-col items-center justify-center py-12 text-charcoal-muted">
            <Loader2 size={24} className="animate-spin mb-2" />
            <p className="text-sm">{activeTab === 'search' ? 'Searching DEX Screener...' : 'Fetching trending tokens + AI analysis...'}</p>
          </div>
        ) : tokens.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-charcoal-muted">
            <Search size={24} className="mb-2 opacity-50" />
            <p className="text-sm">{activeTab === 'search' ? 'Search for any token to see data' : 'No trending tokens available'}</p>
          </div>
        ) : (
          <div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {tokens.map(function(token, i) {
                return (
                  <TokenCard
                    key={token.symbol + '-' + token.chain + '-' + (token.pair_address || '') + '-' + i}
                    token={token}
                    index={i}
                    onCreateOrder={handleCreateOrder}
                    walletAddress={walletAddress}
                  />
                )
              })}
            </div>

            {aiAnalysis && activeTab === 'trending' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 bg-gradient-to-br from-terminal-cyan/5 to-emerald-50 border border-terminal-cyan/20 rounded-xl p-4"
              >
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="font-semibold text-sm text-charcoal">AI Swarm Analysis</h3>
                  <span className="text-[10px] bg-terminal-cyan/10 text-terminal-cyan px-2 py-0.5 rounded-full">3-LLM Verdict</span>
                </div>
                {aiAnalysis.structured_data?.summary && (
                  <p className="text-xs text-charcoal-muted leading-relaxed">{aiAnalysis.structured_data.summary}</p>
                )}
                {aiAnalysis.structured_data?.timeline_or_metrics?.length > 0 && (
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {aiAnalysis.structured_data.timeline_or_metrics.slice(0, 6).map(function(m, i) {
                      return (
                        <div key={i} className="bg-white/60 rounded-lg px-3 py-2">
                          <p className="text-[10px] text-charcoal-muted">{m.key}</p>
                          <p className="text-xs font-medium text-charcoal">{m.value}</p>
                        </div>
                      )
                    })}
                  </div>
                )}
              </motion.div>
            )}
          </div>
        )}
      </div>

      <div className="px-6 py-3 border-t border-charcoal/5 bg-cream/50 flex items-center justify-between">
        <span className="text-[10px] text-charcoal-muted">
          DEX Screener API + X10V 3-LLM Swarm - Auto-trades checked every 60s
        </span>
        <a href="https://dexscreener.com" target="_blank" rel="noopener noreferrer" className="text-[10px] text-terminal-cyan hover:underline flex items-center gap-1">
          dexscreener.com <ExternalLink size={8} />
        </a>
      </div>
    </div>
  )
}
