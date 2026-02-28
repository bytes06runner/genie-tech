import { WalletProvider, WalletManager, WalletId, NetworkId } from '@txnlab/use-wallet-react'

const walletManager = new WalletManager({
  wallets: [WalletId.LUTE],
  network: NetworkId.TESTNET,
  algod: {
    baseServer: 'https://testnet-api.algonode.cloud',
    port: 443,
    token: '',
  },
})

export default function AlgorandProvider({ children }) {
  return (
    <WalletProvider manager={walletManager}>
      {children}
    </WalletProvider>
  )
}
