import React, { useState, useEffect, useRef, Component } from 'react'
import algosdk from 'algosdk'

// ─── Debug logger ────────────────────────────────────────────────
const log = (msg) => {
  const ts = new Date().toISOString().slice(11, 19)
  console.log(`[X10V ${ts}] ${msg}`)
  window.__log?.(`App: ${msg}`)
}

// ─── Safe Telegram SDK access ────────────────────────────────────
let tg = null
try {
  tg = window.Telegram?.WebApp
  log(`Telegram SDK: ${tg ? 'FOUND (v' + (tg.version || '?') + ')' : 'NOT FOUND'}`)
  if (tg) {
    tg.ready()
    tg.expand()
    log('tg.ready() + tg.expand() called')
  }
} catch (e) {
  log(`Telegram SDK init error: ${e.message}`)
}

// ─── Safe algod client ───────────────────────────────────────────
let algodClient = null
try {
  algodClient = new algosdk.Algodv2('', 'https://testnet-api.algonode.cloud', 443)
  log('algodClient created OK')
} catch (e) {
  log(`algodClient creation FAILED: ${e.message}`)
}

// ─── Helpers ─────────────────────────────────────────────────────
function getAppMode() {
  try {
    return new URLSearchParams(window.location.search).get('mode') || 'connect'
  } catch { return 'connect' }
}

function isValidAlgoAddress(addr) {
  if (!addr || addr.length !== 58) return false
  try { algosdk.decodeAddress(addr); return true } catch { return false }
}

// ─── Error Boundary ──────────────────────────────────────────────
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(error) { return { error } }
  componentDidCatch(err, info) { log(`ErrorBoundary caught: ${err.message}`) }
  render() {
    if (this.state.error) {
      return (
        <div style={S.page}>
          <div style={S.card}>
            <p style={{ fontSize: 40 }}>⚠️</p>
            <h2 style={{ margin: '12px 0 0' }}>React Render Error</h2>
            <pre style={S.errorPre}>{this.state.error.message}{'\n\n'}{this.state.error.stack?.slice(0, 500)}</pre>
            <button style={S.btn} onClick={() => location.reload()}>Reload</button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

// ─── Connect Mode: paste address (always works) ─────────────────
function ConnectMode() {
  const [address, setAddress] = useState('')
  const [status, setStatus] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [balance, setBalance] = useState(null)
  const sentRef = useRef(false)

  log('ConnectMode rendered')

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText()
      setAddress(text.trim())
      setErrorMsg('')
      log('Pasted from clipboard')
    } catch (e) {
      setErrorMsg('Clipboard access denied. Please paste manually.')
      log(`Clipboard error: ${e.message}`)
    }
  }

  const handleSubmit = async () => {
    const trimmed = address.trim()
    log(`Submit: ${trimmed.slice(0, 10)}... (${trimmed.length} chars)`)

    if (!isValidAlgoAddress(trimmed)) {
      setErrorMsg('Invalid Algorand address (must be 58 characters, base32).')
      setStatus('error')
      return
    }
    if (!algodClient) {
      setErrorMsg('Algorand client not available. Please reload.')
      setStatus('error')
      return
    }

    setStatus('checking')
    setErrorMsg('')

    try {
      log('Verifying on TestNet...')
      const info = await algodClient.accountInformation(trimmed).do()
      const bal = (info['amount'] || 0) / 1e6
      setBalance(bal)
      setStatus('success')
      log(`Verified! Balance: ${bal} ALGO`)

      if (tg && !sentRef.current) {
        sentRef.current = true
        setTimeout(() => {
          const data = JSON.stringify({ action: 'wallet_connected', address: trimmed, balance: bal })
          log(`sendData: ${data}`)
          tg.sendData(data)
          tg.close()
        }, 1000)
      }
    } catch (e) {
      log(`Verification failed: ${e.message}`)
      setErrorMsg(`Could not verify on TestNet: ${e.message}`)
      setStatus('error')
    }
  }

  if (status === 'success') {
    return (
      <div style={S.page}>
        <div style={{ ...S.card, borderColor: '#238636' }}>
          <p style={{ fontSize: 48 }}>✅</p>
          <h2 style={{ color: '#3FB950', margin: '8px 0' }}>Wallet Connected!</h2>
          <p style={{ fontSize: 13, color: '#8B949E' }}>Sending to X10V bot…</p>
          <p style={S.mono}>{address.trim()}</p>
          {balance !== null && <p style={{ color: '#3FB950', fontWeight: 700, marginTop: 8 }}>{balance.toFixed(4)} ALGO</p>}
        </div>
      </div>
    )
  }

  return (
    <div style={S.page}>
      <div style={{ maxWidth: 420, width: '100%' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', padding: '12px 0 20px', borderBottom: '1px solid #21262D' }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, background: 'linear-gradient(90deg,#3FB950,#58A6FF)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', margin: 0 }}>
            X10V Wallet Connect
          </h1>
          <p style={{ fontSize: 13, color: '#8B949E', marginTop: 6 }}>Link your Algorand TestNet wallet</p>
        </div>

        {/* Instructions */}
        <div style={{ ...S.card, margin: '20px 0 16px', borderColor: '#634C1A' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ fontSize: 20 }}>💡</span>
            <div style={{ fontSize: 12, color: '#D4A72C', lineHeight: 1.7 }}>
              <strong>How to connect:</strong><br />
              1. Open your <strong>Lute Wallet</strong> Chrome extension<br />
              2. Switch to <strong>TestNet</strong> in Lute settings<br />
              3. Copy your address from Lute<br />
              4. Paste it below and tap <strong>Connect</strong>
            </div>
          </div>
        </div>

        {/* Input card */}
        <div style={S.card}>
          <label style={{ fontSize: 12, color: '#8B949E', display: 'block', marginBottom: 6 }}>Algorand TestNet Address</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              value={address}
              onChange={(e) => { setAddress(e.target.value); setErrorMsg(''); setStatus(null) }}
              placeholder="Paste your 58-character address…"
              spellCheck="false"
              autoComplete="off"
              style={{
                flex: 1, background: 'rgba(0,0,0,0.3)', border: '1px solid #30363D', borderRadius: 8,
                padding: '10px 12px', color: '#E6EDF3', fontSize: 13, fontFamily: 'monospace', outline: 'none',
              }}
            />
            <button onClick={handlePaste} style={{ ...S.btn, background: '#21262D', padding: '10px 14px', fontSize: 16 }}>
              📋
            </button>
          </div>

          {address && (
            <p style={{ fontSize: 11, marginTop: 6, color: isValidAlgoAddress(address.trim()) ? '#3FB950' : '#8B949E' }}>
              {address.trim().length}/58 characters {isValidAlgoAddress(address.trim()) && '✓ Valid format'}
            </p>
          )}

          {errorMsg && (
            <div style={{ marginTop: 10, background: 'rgba(248,81,73,0.1)', border: '1px solid #F85149', borderRadius: 8, padding: 10 }}>
              <p style={{ fontSize: 12, color: '#F85149', margin: 0 }}>{errorMsg}</p>
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={!address.trim() || status === 'checking'}
            style={{
              ...S.btn,
              width: '100%', marginTop: 14, padding: '12px 0', fontSize: 15,
              background: (!address.trim() || status === 'checking') ? '#21262D' : 'linear-gradient(90deg,#238636,#2EA043)',
              cursor: (!address.trim() || status === 'checking') ? 'not-allowed' : 'pointer',
              opacity: (!address.trim() || status === 'checking') ? 0.5 : 1,
            }}
          >
            {status === 'checking' ? '⏳ Verifying on TestNet…' : '🔗 Connect Wallet'}
          </button>
        </div>

        {/* Setup guide */}
        <div style={{ ...S.card, marginTop: 16 }}>
          <h3 style={{ fontSize: 13, color: '#8B949E', margin: '0 0 8px', fontWeight: 600 }}>ℹ️ Setup Guide</h3>
          <ul style={{ fontSize: 12, color: '#8B949E', margin: 0, paddingLeft: 16, lineHeight: 2.2 }}>
            <li>Install <a href="https://lute.app" style={{ color: '#58A6FF' }} target="_blank" rel="noreferrer">Lute Wallet</a> Chrome extension</li>
            <li>Switch to <strong>Algorand TestNet</strong> in Lute settings</li>
            <li>Fund via <a href="https://bank.testnet.algorand.network/" style={{ color: '#58A6FF' }} target="_blank" rel="noreferrer">TestNet Dispenser</a></li>
          </ul>
        </div>

        {/* Network badge */}
        <div style={{ textAlign: 'center', marginTop: 20 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#8B949E', background: '#161B22', padding: '4px 12px', borderRadius: 20, border: '1px solid #21262D' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#D29922' }} />
            Algorand TestNet
          </span>
        </div>

        {/* Debug panel */}
        <details style={{ marginTop: 24, fontSize: 11, color: '#484F58' }}>
          <summary style={{ cursor: 'pointer' }}>🐛 Debug Info</summary>
          <pre style={{ marginTop: 8, background: '#0D1117', border: '1px solid #21262D', borderRadius: 8, padding: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: 10, color: '#8B949E' }}>
{`Mode: ${getAppMode()}
Telegram SDK: ${tg ? 'YES v' + (tg.version || '?') : 'NO'}
algosdk: ${algosdk ? 'YES' : 'NO'}
algodClient: ${algodClient ? 'YES' : 'NO'}
URL: ${window.location.href}
UA: ${navigator.userAgent.slice(0, 120)}
Logs:
${(window.__bootLogs || []).join('\n')}`}
          </pre>
        </details>
      </div>
    </div>
  )
}

// ─── Root App ────────────────────────────────────────────────────
export default function App() {
  const [ready, setReady] = useState(false)
  const mode = getAppMode()

  log(`App() render — mode="${mode}"`)

  useEffect(() => {
    log('App useEffect — mounted')
    setReady(true)
  }, [])

  if (!ready) {
    return (
      <div style={S.page}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ fontSize: 28 }}>🔗</p>
          <p style={{ fontSize: 14, color: '#8B949E', marginTop: 8 }}>App is Loading…</p>
        </div>
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <ConnectMode />
    </ErrorBoundary>
  )
}

// ─── Inline Styles ───────────────────────────────────────────────
const S = {
  page: {
    minHeight: '100vh',
    background: '#0D1117',
    color: '#E6EDF3',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    padding: 16,
    flexDirection: 'column',
  },
  card: {
    background: '#161B22',
    border: '1px solid #21262D',
    borderRadius: 12,
    padding: 16,
  },
  btn: {
    background: '#238636',
    color: '#fff',
    border: 'none',
    borderRadius: 10,
    fontWeight: 600,
    cursor: 'pointer',
    fontSize: 14,
  },
  mono: {
    fontSize: 11,
    fontFamily: 'monospace',
    wordBreak: 'break-all',
    background: 'rgba(0,0,0,0.3)',
    borderRadius: 8,
    padding: 10,
    marginTop: 8,
  },
  errorPre: {
    fontSize: 11,
    color: '#F85149',
    background: '#161B22',
    padding: 12,
    borderRadius: 8,
    maxWidth: '90vw',
    overflow: 'auto',
    textAlign: 'left',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
    marginTop: 12,
  },
}
