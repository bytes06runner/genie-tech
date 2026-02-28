import algosdk from 'algosdk'

export const ALGO_TESTNET = {
  token: '',
  server: 'https://testnet-api.algonode.cloud',
  port: 443,
}

export const algodClient = new algosdk.Algodv2(
  ALGO_TESTNET.token,
  ALGO_TESTNET.server,
  ALGO_TESTNET.port
)

export const DUMMY_RECEIVER = 'HZ57J3K46JIJXILONBBZOHX6BKPXEM2VVXNRFSUED6DKFD5ZD24PMJ3MVA'

export async function getAccountBalance(address) {
  try {
    const info = await algodClient.accountInformation(address).do()
    return info['amount'] / 1e6
  } catch (err) {
    console.error('Failed to fetch balance:', err)
    return null
  }
}

export async function buildPaymentTxn(senderAddress, receiverAddress, amountAlgo) {
  const suggestedParams = await algodClient.getTransactionParams().do()
  const amountMicroAlgo = Math.floor(amountAlgo * 1e6)

  const txn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
    from: senderAddress,
    to: receiverAddress,
    amount: amountMicroAlgo,
    suggestedParams,
    note: new Uint8Array(Buffer.from('X10V Telegram Web3 Bridge')),
  })
  return txn
}

export async function waitForConfirmation(txId, rounds = 4) {
  const result = await algosdk.waitForConfirmation(algodClient, txId, rounds)
  return result
}
