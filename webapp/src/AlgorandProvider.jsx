import { useState, useEffect } from 'react'
import { WalletProvider, WalletManager, WalletId, NetworkId } from '@txnlab/use-wallet-react'

export default function AlgorandProvider({ children, fallback }) {
  const [manager, setManager] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    try {
      const wm = new WalletManager({
        wallets: [WalletId.LUTE],
        network: NetworkId.TESTNET,
        algod: {
          baseServer: 'https://testnet-api.algonode.cloud',
          port: 443,
          token: '',
        },
      })
      setManager(wm)
    } catch (err) {
      console.error('WalletManager init failed:', err)
      setError(err)
    }
  }, [])

  if (error) {
    return fallback || null
  }

  if (!manager) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0D1117',
        color: '#E6EDF3',
        fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      }}>
        <p>Loading wallet…</p>
      </div>
    )
  }

  return (
    <WalletProvider manager={manager}>
      {children}
    </WalletProvider>
  )
}
