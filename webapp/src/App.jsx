import { useState, useEffect, useCallback } from 'react'
import { useWallet } from '@txnlab/use-wallet-react'
import algosdk from 'algosdk'
import { getAccountBalance, buildPaymentTxn, waitForConfirmation, DUMMY_RECEIVER, algodClient } from './algorand'
import AlgorandProvider from './AlgorandProvider'

const tg = window.Telegram?.WebApp

function WalletBridge() {
  const { wallets, activeWallet, activeAccount, signTransactions } = useWallet()
  const [balance, setBalance] = useState(null)
  const [txStatus, setTxStatus] = useState(null)
  const [txId, setTxId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [sendAmount, setSendAmount] = useState('0.1')
  const [addressSent, setAddressSent] = useState(false)

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

      if (tg && !addressSent) {
        setAddressSent(true)
        tg.sendData(JSON.stringify({
          action: 'wallet_connected',
          address: activeAccount.address,
        }))
        tg.close()
      }
    } else {
      setBalance(null)
    }
  }, [activeAccount, addressSent])

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
    if (isNaN(amount) || amount <= 0) {
      setTxStatus('Invalid amount')
      return
    }

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
          tg.sendData(JSON.stringify({
            status: 'success',
            txId: confirmedTxId,
            amount: amount,
            from: activeAccount.address,
            to: DUMMY_RECEIVER,
          }))
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
        {/* Header */}
        <div className="text-center pt-2 pb-4 border-b border-gray-800">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-green-400 to-cyan-400 bg-clip-text text-transparent">
            X10V Web3 Bridge
          </h1>
          <p className="text-tg-hint text-sm mt-1">Algorand TestNet → Lute Wallet</p>
        </div>

        {/* Wallet Connection */}
        {!activeAccount ? (
          <div className="fade-in space-y-3">
            <div className="bg-tg-secondary rounded-xl p-5 border border-gray-800">
              <h2 className="text-lg font-semibold mb-3">Connect Wallet</h2>
              <p className="text-tg-hint text-sm mb-4">
                Connect your Lute wallet to sign Algorand TestNet transactions directly from Telegram.
              </p>
              {luteWallet ? (
                <button
                  onClick={() => handleConnect(luteWallet)}
                  className="w-full py-3 px-4 bg-tg-button text-tg-buttonText font-semibold rounded-xl
                             hover:opacity-90 active:scale-[0.98] transition-all duration-150 pulse-glow"
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
                <li>• Install <a href="https://lute.app" className="text-tg-link underline" target="_blank">Lute Wallet</a> browser extension</li>
                <li>• Switch to Algorand TestNet in Lute settings</li>
                <li>• Fund via <a href="https://bank.testnet.algorand.network/" className="text-tg-link underline" target="_blank">Algorand Testnet Dispenser</a></li>
              </ul>
            </div>
          </div>
        ) : (
          <div className="fade-in space-y-4">
            {/* Connected Wallet Info */}
            <div className="bg-tg-secondary rounded-xl p-4 border border-green-900/50">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-green-400">✅ Wallet Connected</span>
                <button
                  onClick={handleDisconnect}
                  className="text-xs text-red-400 hover:text-red-300 transition-colors"
                >
                  Disconnect
                </button>
              </div>
              <div className="space-y-2">
                <div>
                  <span className="text-xs text-tg-hint">Address</span>
                  <p className="text-sm font-mono break-all bg-black/30 rounded-lg p-2 mt-1">
                    {activeAccount.address}
                  </p>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-tg-hint">TestNet Balance</span>
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold text-green-400">
                      {balance !== null ? `${balance.toFixed(4)} ALGO` : '…'}
                    </span>
                    <button
                      onClick={refreshBalance}
                      className="text-xs text-tg-link hover:underline"
                    >
                      ↻
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Send Transaction */}
            <div className="bg-tg-secondary rounded-xl p-4 border border-gray-800">
              <h2 className="text-lg font-semibold mb-3">Send ALGO</h2>

              <div className="space-y-3">
                <div>
                  <label className="text-xs text-tg-hint block mb-1">Amount (ALGO)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.001"
                    value={sendAmount}
                    onChange={(e) => setSendAmount(e.target.value)}
                    className="w-full bg-black/30 border border-gray-700 rounded-lg px-3 py-2 text-sm
                               focus:outline-none focus:border-tg-link transition-colors"
                  />
                </div>

                <div>
                  <label className="text-xs text-tg-hint block mb-1">Recipient (TestNet)</label>
                  <p className="text-xs font-mono break-all bg-black/20 rounded-lg p-2 text-tg-hint">
                    {DUMMY_RECEIVER}
                  </p>
                </div>

                <button
                  onClick={handleSendAlgo}
                  disabled={loading || balance === null || balance < parseFloat(sendAmount || '0') + 0.001}
                  className="w-full py-3 px-4 bg-gradient-to-r from-green-600 to-emerald-600
                             text-white font-semibold rounded-xl
                             hover:from-green-500 hover:to-emerald-500
                             disabled:opacity-40 disabled:cursor-not-allowed
                             active:scale-[0.98] transition-all duration-150"
                >
                  {loading ? '⏳ Processing …' : `⚡ Send ${sendAmount} ALGO`}
                </button>
              </div>
            </div>

            {/* Transaction Status */}
            {txStatus && (
              <div className={`fade-in rounded-xl p-4 border ${
                txStatus.includes('✅') ? 'bg-green-950/30 border-green-800' :
                txStatus.includes('❌') ? 'bg-red-950/30 border-red-800' :
                'bg-tg-secondary border-gray-800'
              }`}>
                <p className="text-sm">{txStatus}</p>
                {txId && (
                  <a
                    href={`https://testnet.explorer.perawallet.app/tx/${txId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-tg-link hover:underline mt-2 block"
                  >
                    View on Explorer →  {txId.slice(0, 12)}…
                  </a>
                )}
              </div>
            )}

            {/* Network Badge */}
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
  return (
    <AlgorandProvider>
      <WalletBridge />
    </AlgorandProvider>
  )
}
