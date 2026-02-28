import { useState, useEffect, useCallback, useRef } from 'react'
import { useWallet } from '@txnlab/use-wallet-react'
import algosdk from 'algosdk'
import { getAccountBalance, buildPaymentTxn, waitForConfirmation, DUMMY_RECEIVER, algodClient } from './algorand'
import AlgorandProvider from './AlgorandProvider'

const tg = window.Telegram?.WebApp

function getAppMode() {
  const params = new URLSearchParams(window.location.search)
  return params.get('mode') || 'transact'
}

function isValidAlgorandAddress(addr) {
  if (!addr || typeof addr !== 'string') return false
  if (addr.length !== 58) return false
  try {
    algosdk.decodeAddress(addr)
    return true
  } catch {
    return false
  }
}

function ConnectMode() {
  const { wallets, activeWallet, activeAccount } = useWallet()
  const [balance, setBalance] = useState(null)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [manualAddress, setManualAddress] = useState('')
  const [checking, setChecking] = useState(false)
  const dataSentRef = useRef(false)

  useEffect(() => {
    if (tg) {
      tg.ready()
      tg.expand()
      tg.MainButton.hide()
    }
  }, [])

  useEffect(() => {
    if (activeAccount?.address && !dataSentRef.current) {
      sendWalletData(activeAccount.address)
    }
  }, [activeAccount])

  const sendWalletData = async (addr) => {
    if (dataSentRef.current) return
    dataSentRef.current = true
    setSuccess(true)

    try {
      const bal = await getAccountBalance(addr)
      setBalance(bal)

      if (tg) {
        setTimeout(() => {
          tg.sendData(JSON.stringify({
            action: 'wallet_connected',
            address: addr,
            balance: bal,
          }))
          tg.close()
        }, 800)
      }
    } catch (err) {
      console.error('Balance fetch error:', err)
      if (tg) {
        setTimeout(() => {
          tg.sendData(JSON.stringify({
            action: 'wallet_connected',
            address: addr,
            balance: 0,
          }))
          tg.close()
        }, 800)
      }
    }
  }

  const handleConnect = async (wallet) => {
    try {
      setError(null)
      await wallet.connect()
    } catch (err) {
      console.error('Lute connect failed:', err)
      setError(`Connection failed: ${err.message}. Try the manual option below.`)
    }
  }

  const handleManualSubmit = async () => {
    const trimmed = manualAddress.trim()
    setError(null)

    if (!isValidAlgorandAddress(trimmed)) {
      setError('Invalid Algorand address. Must be 58 characters (base32).')
      return
    }

    setChecking(true)
    try {
      const info = await algodClient.accountInformation(trimmed).do()
      const balanceAlgo = (info['amount'] || 0) / 1e6
      setBalance(balanceAlgo)
      setSuccess(true)

      if (tg) {
        setTimeout(() => {
          tg.sendData(JSON.stringify({
            action: 'wallet_connected',
            address: trimmed,
            balance: balanceAlgo,
          }))
          tg.close()
        }, 800)
      }
    } catch (err) {
      console.error('Address validation error:', err)
      setError('Could not verify address on TestNet. Make sure it is a valid Algorand TestNet address.')
      setChecking(false)
    }
  }

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText()
      setManualAddress(text.trim())
      setError(null)
    } catch {
      setError('Clipboard access denied. Please paste manually.')
    }
  }

  const luteWallet = wallets?.find(w => w.id === 'lute')

  if (success) {
    return (
      <div className="min-h-screen bg-tg-bg text-tg-text p-4 flex items-center justify-center">
        <div className="max-w-md w-full bg-tg-secondary rounded-2xl p-8 border border-green-900/50 text-center space-y-3">
          <div className="text-5xl">✅</div>
          <p className="text-xl font-bold text-green-400">Wallet Connected!</p>
          <p className="text-sm text-tg-hint">Sending address to X10V bot…</p>
          <p className="text-xs font-mono break-all bg-black/30 rounded-lg p-3 mt-2">
            {activeAccount?.address || manualAddress.trim()}
          </p>
          {balance !== null && (
            <p className="text-sm text-green-400">{balance.toFixed(4)} ALGO</p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-tg-bg text-tg-text p-4">
      <div className="max-w-md mx-auto space-y-5">
        <div className="text-center pt-2 pb-4 border-b border-gray-800">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-green-400 to-cyan-400 bg-clip-text text-transparent">
            X10V Wallet Connect
          </h1>
          <p className="text-tg-hint text-sm mt-1">Link your Algorand Lute Wallet</p>
        </div>

        <div className="bg-tg-secondary rounded-xl p-5 border border-gray-800 space-y-4">
          <h2 className="text-lg font-semibold">🔗 Connect with Lute Extension</h2>
          <p className="text-tg-hint text-sm">
            Click the button below to sign in with your Lute Wallet browser extension.
          </p>
          {luteWallet ? (
            <button
              onClick={() => handleConnect(luteWallet)}
              className="w-full py-3 px-4 bg-gradient-to-r from-green-600 to-emerald-600
                         text-white font-semibold rounded-xl
                         hover:from-green-500 hover:to-emerald-500
                         active:scale-[0.98] transition-all duration-150"
            >
              🔗 Connect Lute Wallet
            </button>
          ) : (
            <div className="space-y-2">
              {wallets?.map(wallet => (
                <button
                  key={wallet.id}
                  onClick={() => handleConnect(wallet)}
                  className="w-full py-3 px-4 bg-gradient-to-r from-green-600 to-emerald-600
                             text-white font-semibold rounded-xl
                             hover:from-green-500 hover:to-emerald-500
                             active:scale-[0.98] transition-all"
                >
                  🔗 Connect {wallet.metadata?.name || wallet.id}
                </button>
              ))}
            </div>
          )}

          {error && (
            <div className="bg-red-950/30 border border-red-800 rounded-lg p-3">
              <p className="text-xs text-red-400">{error}</p>
            </div>
          )}
        </div>

        <div className="bg-tg-secondary rounded-xl p-5 border border-gray-800 space-y-4">
          <button
            onClick={() => setShowManual(!showManual)}
            className="w-full flex items-center justify-between text-sm text-tg-hint hover:text-tg-text transition-colors"
          >
            <span>📋 Paste address manually instead</span>
            <span className="text-xs">{showManual ? '▲' : '▼'}</span>
          </button>

          {showManual && (
            <div className="space-y-3 fade-in">
              <div className="flex items-start gap-3 bg-yellow-950/30 border border-yellow-800/50 rounded-lg p-3">
                <span className="text-lg">💡</span>
                <div className="text-xs text-yellow-200/80 space-y-1">
                  <p>Open <strong>Lute Wallet</strong> → copy your TestNet address → paste below</p>
                </div>
              </div>
              <div>
                <label className="text-xs text-tg-hint block mb-1.5">Algorand TestNet Address</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={manualAddress}
                    onChange={(e) => { setManualAddress(e.target.value); setError(null) }}
                    placeholder="Paste your 58-character address …"
                    className="flex-1 bg-black/30 border border-gray-700 rounded-lg px-3 py-2.5 text-sm font-mono
                               focus:outline-none focus:border-tg-link transition-colors placeholder:text-gray-600"
                    spellCheck={false}
                    autoComplete="off"
                  />
                  <button
                    onClick={handlePaste}
                    className="px-3 py-2.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium
                               transition-colors border border-gray-700 whitespace-nowrap"
                  >
                    📋
                  </button>
                </div>
                {manualAddress && (
                  <p className={`text-xs mt-1.5 ${isValidAlgorandAddress(manualAddress.trim()) ? 'text-green-400' : 'text-tg-hint'}`}>
                    {manualAddress.trim().length}/58 characters
                    {isValidAlgorandAddress(manualAddress.trim()) && ' ✓ Valid'}
                  </p>
                )}
              </div>
              <button
                onClick={handleManualSubmit}
                disabled={!manualAddress.trim() || checking}
                className="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-cyan-600
                           text-white font-semibold rounded-xl
                           hover:from-blue-500 hover:to-cyan-500
                           disabled:opacity-40 disabled:cursor-not-allowed
                           active:scale-[0.98] transition-all duration-150"
              >
                {checking ? '⏳ Verifying on TestNet …' : '🔗 Connect with Address'}
              </button>
            </div>
          )}
        </div>

        <div className="bg-tg-secondary rounded-xl p-4 border border-gray-800">
          <h3 className="text-sm font-semibold text-tg-hint mb-2">ℹ️ Setup</h3>
          <ul className="text-xs text-tg-hint space-y-1.5">
            <li>• Install <a href="https://lute.app" className="text-tg-link underline" target="_blank" rel="noreferrer">Lute Wallet</a> Chrome extension</li>
            <li>• Switch to <strong>Algorand TestNet</strong> in Lute settings</li>
            <li>• Fund via <a href="https://bank.testnet.algorand.network/" className="text-tg-link underline" target="_blank" rel="noreferrer">Algorand Testnet Dispenser</a></li>
          </ul>
        </div>

        <div className="text-center">
          <span className="inline-flex items-center gap-1.5 text-xs text-tg-hint bg-tg-secondary px-3 py-1 rounded-full border border-gray-800">
            <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-pulse" />
            Algorand TestNet
          </span>
        </div>
      </div>
    </div>
  )
}

function TransactMode() {
  const { wallets, activeWallet, activeAccount, signTransactions } = useWallet()
  const [balance, setBalance] = useState(null)
  const [txStatus, setTxStatus] = useState(null)
  const [txId, setTxId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [sendAmount, setSendAmount] = useState('0.1')

  useEffect(() => {
    if (tg) {
      tg.ready()
      tg.expand()
      tg.MainButton.hide()
    }
  }, [])

  useEffect(() => {
    if (activeAccount?.address) {
      refreshBalance()
    } else {
      setBalance(null)
    }
  }, [activeAccount])

  const refreshBalance = useCallback(async () => {
    if (!activeAccount?.address) return
    const bal = await getAccountBalance(activeAccount.address)
    setBalance(bal)
  }, [activeAccount])

  const handleConnect = async (wallet) => {
    try {
      setTxStatus(null)
      await wallet.connect()
    } catch (err) {
      console.error('Connect failed:', err)
      setTxStatus(`Connection failed: ${err.message}`)
    }
  }

  const handleDisconnect = async () => {
    if (activeWallet) {
      await activeWallet.disconnect()
      setBalance(null)
      setTxStatus(null)
      setTxId(null)
    }
  }

  const handleSendAlgo = async () => {
    if (!activeAccount?.address) return
    const amount = parseFloat(sendAmount)
    if (isNaN(amount) || amount <= 0) { setTxStatus('Invalid amount'); return }

    setLoading(true)
    setTxStatus('Building transaction …')
    setTxId(null)

    try {
      const txn = await buildPaymentTxn(activeAccount.address, DUMMY_RECEIVER, amount)
      const encodedTxn = algosdk.encodeUnsignedTransaction(txn)
      setTxStatus('Waiting for Lute wallet signature …')
      const signedTxns = await signTransactions([encodedTxn])
      setTxStatus('Broadcasting to Algorand TestNet …')
      const { txId: confirmedTxId } = await algodClient.sendRawTransaction(signedTxns[0]).do()
      setTxId(confirmedTxId)
      setTxStatus('Waiting for confirmation …')
      await waitForConfirmation(confirmedTxId)
      setTxStatus('✅ Transaction confirmed!')
      await refreshBalance()

      if (tg) {
        tg.MainButton.setText('✅ Transaction Complete — Close')
        tg.MainButton.show()
        tg.MainButton.onClick(() => {
          tg.sendData(JSON.stringify({ status: 'success', txId: confirmedTxId, amount, from: activeAccount.address, to: DUMMY_RECEIVER }))
          tg.close()
        })
      }
    } catch (err) {
      console.error('Transaction failed:', err)
      setTxStatus(`❌ Failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const luteWallet = wallets?.find(w => w.id === 'lute')

  return (
    <div className="min-h-screen bg-tg-bg text-tg-text p-4">
      <div className="max-w-md mx-auto space-y-5">
        <div className="text-center pt-2 pb-4 border-b border-gray-800">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-green-400 to-cyan-400 bg-clip-text text-transparent">
            X10V Web3 Bridge
          </h1>
          <p className="text-tg-hint text-sm mt-1">Algorand TestNet → Lute Wallet</p>
        </div>

        {!activeAccount ? (
          <div className="fade-in space-y-3">
            <div className="bg-tg-secondary rounded-xl p-5 border border-gray-800">
              <h2 className="text-lg font-semibold mb-3">Connect Wallet</h2>
              <p className="text-tg-hint text-sm mb-4">
                Connect your Lute wallet to sign Algorand TestNet transactions.
              </p>
              {luteWallet ? (
                <button
                  onClick={() => handleConnect(luteWallet)}
                  className="w-full py-3 px-4 bg-tg-button text-tg-buttonText font-semibold rounded-xl
                             hover:opacity-90 active:scale-[0.98] transition-all duration-150"
                >
                  🔗 Connect Lute Wallet
                </button>
              ) : (
                <div className="space-y-2">
                  {wallets?.map(wallet => (
                    <button
                      key={wallet.id}
                      onClick={() => handleConnect(wallet)}
                      className="w-full py-3 px-4 bg-tg-button text-tg-buttonText font-semibold rounded-xl
                                 hover:opacity-90 active:scale-[0.98] transition-all"
                    >
                      🔗 Connect {wallet.metadata?.name || wallet.id}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="bg-tg-secondary rounded-xl p-4 border border-gray-800">
              <h3 className="text-sm font-semibold text-tg-hint mb-2">ℹ️ Setup</h3>
              <ul className="text-xs text-tg-hint space-y-1">
                <li>• Install <a href="https://lute.app" className="text-tg-link underline" target="_blank" rel="noreferrer">Lute Wallet</a> browser extension</li>
                <li>• Switch to Algorand TestNet in Lute settings</li>
                <li>• Fund via <a href="https://bank.testnet.algorand.network/" className="text-tg-link underline" target="_blank" rel="noreferrer">Algorand Testnet Dispenser</a></li>
              </ul>
            </div>
          </div>
        ) : (
          <div className="fade-in space-y-4">
            <div className="bg-tg-secondary rounded-xl p-4 border border-green-900/50">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-green-400">✅ Wallet Connected</span>
                <button onClick={handleDisconnect} className="text-xs text-red-400 hover:text-red-300 transition-colors">
                  Disconnect
                </button>
              </div>
              <div className="space-y-2">
                <div>
                  <span className="text-xs text-tg-hint">Address</span>
                  <p className="text-sm font-mono break-all bg-black/30 rounded-lg p-2 mt-1">{activeAccount.address}</p>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-tg-hint">TestNet Balance</span>
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold text-green-400">
                      {balance !== null ? `${balance.toFixed(4)} ALGO` : '…'}
                    </span>
                    <button onClick={refreshBalance} className="text-xs text-tg-link hover:underline">↻</button>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-tg-secondary rounded-xl p-4 border border-gray-800">
              <h2 className="text-lg font-semibold mb-3">Send ALGO</h2>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-tg-hint block mb-1">Amount (ALGO)</label>
                  <input type="number" step="0.01" min="0.001" value={sendAmount}
                    onChange={(e) => setSendAmount(e.target.value)}
                    className="w-full bg-black/30 border border-gray-700 rounded-lg px-3 py-2 text-sm
                               focus:outline-none focus:border-tg-link transition-colors" />
                </div>
                <div>
                  <label className="text-xs text-tg-hint block mb-1">Recipient (TestNet)</label>
                  <p className="text-xs font-mono break-all bg-black/20 rounded-lg p-2 text-tg-hint">{DUMMY_RECEIVER}</p>
                </div>
                <button onClick={handleSendAlgo}
                  disabled={loading || balance === null || balance < parseFloat(sendAmount || '0') + 0.001}
                  className="w-full py-3 px-4 bg-gradient-to-r from-green-600 to-emerald-600
                             text-white font-semibold rounded-xl hover:from-green-500 hover:to-emerald-500
                             disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98] transition-all duration-150">
                  {loading ? '⏳ Processing …' : `⚡ Send ${sendAmount} ALGO`}
                </button>
              </div>
            </div>

            {txStatus && (
              <div className={`fade-in rounded-xl p-4 border ${
                txStatus.includes('✅') ? 'bg-green-950/30 border-green-800' :
                txStatus.includes('❌') ? 'bg-red-950/30 border-red-800' :
                'bg-tg-secondary border-gray-800'}`}>
                <p className="text-sm">{txStatus}</p>
                {txId && (
                  <a href={`https://testnet.explorer.perawallet.app/tx/${txId}`} target="_blank" rel="noopener noreferrer"
                    className="text-xs text-tg-link hover:underline mt-2 block">
                    View on Explorer → {txId.slice(0, 12)}…
                  </a>
                )}
              </div>
            )}

            <div className="text-center">
              <span className="inline-flex items-center gap-1.5 text-xs text-tg-hint bg-tg-secondary px-3 py-1 rounded-full border border-gray-800">
                <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-pulse" />
                Algorand TestNet
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const appMode = getAppMode()

  return (
    <AlgorandProvider>
      {appMode === 'connect' ? <ConnectMode /> : <TransactMode />}
    </AlgorandProvider>
  )
}
