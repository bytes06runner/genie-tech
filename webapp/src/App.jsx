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

function getUrlParam(key) {
  try {
    return new URLSearchParams(window.location.search).get(key) || ''
  } catch { return '' }
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

// ─── Connect Mode: paste address from Lute (Mini App can't access Chrome extensions) ──
function ConnectMode() {
  const [address, setAddress] = useState('')
  const [status, setStatus] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [balance, setBalance] = useState(null)
  const sentRef = useRef(false)

  const isTelegramWebView = !!tg
  log(`ConnectMode rendered — isTelegram=${isTelegramWebView}`)

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText()
      const trimmed = text.trim()
      setAddress(trimmed)
      setErrorMsg('')
      log(`Pasted from clipboard: ${trimmed.slice(0, 12)}...`)

      // Auto-submit if it looks like a valid address
      if (isValidAlgoAddress(trimmed)) {
        log('Valid address detected after paste — auto-verifying...')
        await verifyAndConnect(trimmed)
      }
    } catch (e) {
      setErrorMsg('Clipboard access denied — please long-press the input field and paste manually.')
      log(`Clipboard error: ${e.message}`)
    }
  }

  const verifyAndConnect = async (addr) => {
    const trimmed = (addr || address).trim()
    log(`Verifying: ${trimmed.slice(0, 10)}... (${trimmed.length} chars)`)

    if (!isValidAlgoAddress(trimmed)) {
      setErrorMsg('Invalid Algorand address — must be 58 characters, base32 encoded.')
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
      setAddress(trimmed)
      setStatus('success')
      log(`Verified! Balance: ${bal} ALGO`)

      if (tg && !sentRef.current) {
        sentRef.current = true
        setTimeout(() => {
          const data = JSON.stringify({ action: 'wallet_connected', address: trimmed, balance: bal })
          log(`sendData: ${data}`)
          tg.sendData(data)
          tg.close()
        }, 1200)
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

        {/* Step-by-step instructions */}
        <div style={{ ...S.card, margin: '20px 0 16px', borderColor: '#58A6FF' }}>
          <div style={{ fontSize: 13, color: '#E6EDF3', lineHeight: 2 }}>
            <p style={{ margin: '0 0 4px', fontWeight: 700, color: '#58A6FF' }}>📋 Quick Steps:</p>
            <p style={{ margin: 0 }}>
              <strong style={{ color: '#3FB950' }}>1.</strong> Open <strong>Lute Wallet</strong> in Chrome → copy your address
            </p>
            <p style={{ margin: 0 }}>
              <strong style={{ color: '#3FB950' }}>2.</strong> Tap the big <strong>📋 Paste Address</strong> button below
            </p>
            <p style={{ margin: 0 }}>
              <strong style={{ color: '#3FB950' }}>3.</strong> We auto-verify on TestNet & connect ✨
            </p>
          </div>
        </div>

        {/* BIG paste button — primary action */}
        <button
          onClick={handlePaste}
          disabled={status === 'checking'}
          style={{
            ...S.btn,
            width: '100%', padding: '18px 0', fontSize: 18,
            background: status === 'checking' ? '#21262D' : 'linear-gradient(90deg,#238636,#2EA043)',
            cursor: status === 'checking' ? 'not-allowed' : 'pointer',
            borderRadius: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
            marginBottom: 16,
          }}
        >
          {status === 'checking' ? '⏳ Verifying on TestNet…' : '📋 Paste Address from Lute'}
        </button>

        {/* Manual input fallback */}
        <div style={S.card}>
          <label style={{ fontSize: 12, color: '#8B949E', display: 'block', marginBottom: 6 }}>Or type / paste manually:</label>
          <input
            type="text"
            value={address}
            onChange={(e) => { setAddress(e.target.value); setErrorMsg(''); setStatus(null) }}
            placeholder="Paste your 58-character address…"
            spellCheck="false"
            autoComplete="off"
            style={{
              width: '100%', background: 'rgba(0,0,0,0.3)', border: '1px solid #30363D', borderRadius: 8,
              padding: '12px', color: '#E6EDF3', fontSize: 13, fontFamily: 'monospace', outline: 'none',
              boxSizing: 'border-box',
            }}
          />

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
            onClick={() => verifyAndConnect()}
            disabled={!address.trim() || status === 'checking'}
            style={{
              ...S.btn,
              width: '100%', marginTop: 12, padding: '12px 0', fontSize: 15,
              background: (!address.trim() || status === 'checking') ? '#21262D' : 'linear-gradient(90deg,#238636,#2EA043)',
              cursor: (!address.trim() || status === 'checking') ? 'not-allowed' : 'pointer',
              opacity: (!address.trim() || status === 'checking') ? 0.5 : 1,
            }}
          >
            🔗 Verify & Connect
          </button>
        </div>

        {/* Setup guide */}
        <div style={{ ...S.card, marginTop: 16 }}>
          <h3 style={{ fontSize: 13, color: '#8B949E', margin: '0 0 8px', fontWeight: 600 }}>ℹ️ Don't have Lute yet?</h3>
          <ul style={{ fontSize: 12, color: '#8B949E', margin: 0, paddingLeft: 16, lineHeight: 2.2 }}>
            <li>Install <a href="https://lute.app" style={{ color: '#58A6FF' }} target="_blank" rel="noreferrer">Lute Wallet</a> Chrome extension</li>
            <li>Switch to <strong>Algorand TestNet</strong> in Lute settings</li>
            <li>Fund via <a href="https://bank.testnet.algorand.network/" style={{ color: '#58A6FF' }} target="_blank" rel="noreferrer">TestNet Dispenser</a></li>
            <li>Copy your address → come back here & paste</li>
          </ul>
        </div>

        {/* Why paste explanation */}
        <div style={{ ...S.card, marginTop: 12, borderColor: '#30363D' }}>
          <p style={{ fontSize: 11, color: '#484F58', margin: 0, lineHeight: 1.6 }}>
            💡 <strong>Why paste?</strong> Telegram Mini Apps run in a secure WebView —
            Chrome extensions like Lute can't connect directly here. Simply copy your
            address from Lute in Chrome, then paste it above. Your wallet is verified
            on-chain before connecting.
          </p>
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
WebView: ${isTelegramWebView ? 'Telegram Mini App' : 'Regular Browser'}
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

// ─── Sign Swap Mode: DeFi Agent unsigned transaction signing ─────

function SignSwapMode() {
  const [status, setStatus] = useState('loading') // loading | ready | signing | success | error
  const [txData, setTxData] = useState(null)
  const [address, setAddress] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [txId, setTxId] = useState('')
  const sentRef = useRef(false)

  const ptxId = getUrlParam('ptx')

  log(`SignSwapMode rendered — ptx=${ptxId}`)

  // Fetch pending transaction from backend
  useEffect(() => {
    if (!ptxId) {
      setErrorMsg('No pending transaction ID provided.')
      setStatus('error')
      return
    }

    const backendUrl = import.meta.env.VITE_BACKEND_URL || 'https://x10v-backend.onrender.com'

    fetch(`${backendUrl}/api/pending_tx/${ptxId}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(data => {
        log(`Fetched pending TX: ${JSON.stringify(data).slice(0, 200)}`)
        setTxData(data)
        setAddress(data.sender || '')
        setStatus('ready')
      })
      .catch(err => {
        log(`Failed to fetch pending TX: ${err.message}`)
        setErrorMsg(`Could not load transaction: ${err.message}`)
        setStatus('error')
      })
  }, [ptxId])

  const handleSign = async () => {
    if (!txData || !algodClient) return

    setStatus('signing')
    setErrorMsg('')

    try {
      log('Building transaction from pending TX data...')

      // Use sender from pending TX (user's connected wallet)
      const sender = txData.sender
      if (!sender) {
        setErrorMsg('No sender address in transaction. Please connect your wallet first via /connect_wallet.')
        setStatus('error')
        return
      }

      // Reconstruct the PaymentTxn using algosdk
      const suggestedParams = await algodClient.getTransactionParams().do()
      const txn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
        from: sender,
        to: txData.receiver,
        amount: Math.floor(txData.amount_algo * 1e6),
        suggestedParams,
        note: new Uint8Array(Buffer.from(txData.note || 'X10V DeFi Agent Protective Transfer')),
      })

      log('Transaction built. Requesting Lute wallet signature...')

      // Check for Lute wallet extension
      if (!window.algorand) {
        setErrorMsg('Lute Wallet extension not found. Please install it from lute.app')
        setStatus('error')
        return
      }

      // Ensure wallet is enabled/connected before signing
      try {
        await window.algorand.enable({ genesisID: 'testnet-v1.0' })
        log('Lute wallet enabled for signing')
      } catch (e) {
        log(`Lute enable for signing failed: ${e.message}`)
        setErrorMsg('Please approve the connection in your Lute wallet popup.')
        setStatus('error')
        return
      }

      // Request signature from Lute
      const encodedTxn = txn.toByte()
      const b64Txn = btoa(String.fromCharCode(...encodedTxn))

      const result = await window.algorand.signTxns([{
        txn: b64Txn,
      }])

      if (!result || !result[0]) {
        setErrorMsg('Wallet rejected the transaction.')
        setStatus('error')
        return
      }

      log('Transaction signed! Submitting to network...')

      // Decode signed transaction and submit
      const signedBytes = new Uint8Array(atob(result[0]).split('').map(c => c.charCodeAt(0)))
      const sendResult = await algodClient.sendRawTransaction(signedBytes).do()
      const confirmedTxId = sendResult.txId || sendResult.txid

      log(`Transaction submitted! TX ID: ${confirmedTxId}`)

      // Wait for confirmation
      await algosdk.waitForConfirmation(algodClient, confirmedTxId, 4)

      setTxId(confirmedTxId)
      setStatus('success')

      // Notify backend that the TX was signed
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'https://x10v-backend.onrender.com'
      fetch(`${backendUrl}/api/pending_tx/${ptxId}/signed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ algo_tx_id: confirmedTxId }),
      }).catch(e => log(`Backend notify failed: ${e.message}`))

      // Send result back to Telegram
      if (tg && !sentRef.current) {
        sentRef.current = true
        setTimeout(() => {
          const data = JSON.stringify({
            action: 'onchain_action_signed',
            ptx_id: ptxId,
            tx_id: confirmedTxId,
            amount_algo: txData.amount_algo,
          })
          log(`sendData: ${data}`)
          tg.sendData(data)
          tg.close()
        }, 2000)
      }

    } catch (e) {
      log(`Sign/submit failed: ${e.message}`)
      setErrorMsg(`Transaction failed: ${e.message}`)
      setStatus('error')
    }
  }

  if (status === 'loading') {
    return (
      <div style={S.page}>
        <div style={S.card}>
          <p style={{ fontSize: 40, textAlign: 'center' }}>⏳</p>
          <p style={{ fontSize: 14, color: '#8B949E', textAlign: 'center', marginTop: 8 }}>Loading transaction…</p>
        </div>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div style={S.page}>
        <div style={{ ...S.card, borderColor: '#238636', maxWidth: 420, width: '100%' }}>
          <p style={{ fontSize: 48, textAlign: 'center' }}>✅</p>
          <h2 style={{ color: '#3FB950', margin: '8px 0', textAlign: 'center' }}>Transfer Executed!</h2>
          <p style={{ fontSize: 13, color: '#8B949E', textAlign: 'center' }}>Transaction confirmed on Algorand TestNet</p>
          <div style={S.mono}>
            <p style={{ margin: '4px 0' }}>� {txData?.amount_algo} ALGO → Safe Vault</p>
            <p style={{ margin: '4px 0', fontSize: 10, wordBreak: 'break-all' }}>TX: {txId}</p>
          </div>
          <a
            href={`https://testnet.explorer.perawallet.app/tx/${txId}`}
            target="_blank"
            rel="noreferrer"
            style={{ ...S.btn, display: 'block', textAlign: 'center', marginTop: 12, padding: '10px 0', textDecoration: 'none' }}
          >
            🔍 View on Explorer
          </a>
        </div>
      </div>
    )
  }

  return (
    <div style={S.page}>
      <div style={{ maxWidth: 420, width: '100%' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', padding: '12px 0 20px', borderBottom: '1px solid #21262D' }}>
          <h1 style={{ fontSize: 20, fontWeight: 800, background: 'linear-gradient(90deg,#F85149,#FF7B72)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', margin: 0 }}>
            🚨 DeFi Agent — Protective Transfer
          </h1>
          <p style={{ fontSize: 12, color: '#8B949E', marginTop: 6 }}>Review and sign the autonomous transfer</p>
        </div>

        {/* Transaction details card */}
        {txData && (
          <div style={{ ...S.card, margin: '20px 0 16px', borderColor: '#F85149' }}>
            <h3 style={{ fontSize: 14, margin: '0 0 12px', color: '#FF7B72' }}>📋 Transaction Details</h3>
            <div style={{ fontSize: 12, color: '#E6EDF3', lineHeight: 2 }}>
              <p>� <strong>Transfer:</strong> {txData.amount_algo} ALGO → Safe Vault</p>
              <p>📤 <strong>From:</strong> <span style={{ fontFamily: 'monospace', fontSize: 10 }}>{txData.sender?.slice(0, 20)}…</span></p>
              <p>📥 <strong>To:</strong> <span style={{ fontFamily: 'monospace', fontSize: 10 }}>{txData.receiver?.slice(0, 20)}…</span></p>
              <p>📝 <strong>Reason:</strong> {txData.note || 'DeFi Agent Protective Transfer'}</p>
              <p>🆔 <strong>ID:</strong> <span style={{ fontFamily: 'monospace', fontSize: 10 }}>{ptxId}</span></p>
            </div>
          </div>
        )}

        {/* Error display */}
        {errorMsg && (
          <div style={{ marginBottom: 16, background: 'rgba(248,81,73,0.1)', border: '1px solid #F85149', borderRadius: 8, padding: 10 }}>
            <p style={{ fontSize: 12, color: '#F85149', margin: 0 }}>{errorMsg}</p>
          </div>
        )}

        {/* Action buttons */}
        {status === 'ready' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <button
              onClick={handleSign}
              style={{
                ...S.btn,
                width: '100%', padding: '14px 0', fontSize: 16,
                background: 'linear-gradient(90deg,#F85149,#DA3633)',
              }}
            >
              🔐 Sign & Execute Transfer
            </button>
            <button
              onClick={() => { if (tg) tg.close(); else window.close() }}
              style={{
                ...S.btn, width: '100%', padding: '12px 0', fontSize: 14,
                background: '#21262D', color: '#8B949E',
              }}
            >
              Cancel
            </button>
          </div>
        )}

        {status === 'signing' && (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <p style={{ fontSize: 28 }}>🔐</p>
            <p style={{ fontSize: 14, color: '#8B949E', marginTop: 8 }}>Waiting for Lute wallet…</p>
            <p style={{ fontSize: 12, color: '#484F58', marginTop: 4 }}>Check your Lute extension popup</p>
          </div>
        )}

        {/* Network badge */}
        <div style={{ textAlign: 'center', marginTop: 20 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#8B949E', background: '#161B22', padding: '4px 12px', borderRadius: 20, border: '1px solid #21262D' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#D29922' }} />
            Algorand TestNet — Autonomous DeFi Agent
          </span>
        </div>
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

  const renderMode = () => {
    switch (mode) {
      case 'sign_swap':
        return <SignSwapMode />
      case 'connect':
      default:
        return <ConnectMode />
    }
  }

  return (
    <ErrorBoundary>
      {renderMode()}
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
