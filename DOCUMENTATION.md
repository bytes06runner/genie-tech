# X10V — Autonomous Multi-Agent DeFi Intelligence Platform

### Built for the Algorand Hackathon | Team: Genie Tech

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Our Solution](#3-our-solution)
4. [Why X10V Is Different from Current AI Agents](#4-why-x10v-is-different-from-current-ai-agents)
5. [Architecture Overview](#5-architecture-overview)
6. [System Components (Deep Dive)](#6-system-components-deep-dive)
7. [Algorand Integration](#7-algorand-integration)
8. [Tech Stack](#8-tech-stack)
9. [User Flow](#9-user-flow)
10. [Telegram Bot — 30+ Commands](#10-telegram-bot--30-commands)
11. [Security Model](#11-security-model)
12. [How to Win the Hackathon](#12-how-to-win-the-hackathon)
13. [Future Roadmap](#13-future-roadmap)
14. [Quick Start / Running Locally](#14-quick-start--running-locally)

---

## 1. Executive Summary

**X10V** is an **Autonomous Multi-Agent DeFi Intelligence Platform** built on Algorand. It combines a **3-LLM AI Swarm** (Gemini 2.5 Flash + Groq Llama-3.1), **n8n-style workflow automation**, **real-time market intelligence**, and **on-chain Algorand operations** into a single, Telegram-native agent that can:

- 🧠 **Think** — Multi-agent debate pipeline (Alpha → Beta → Gamma) for any query
- 👀 **See** — Real-time market data, web scraping, YouTube research
- ⚡ **Act** — Execute paper trades, create automations, trigger on-chain Algorand transactions
- 🛡️ **Protect** — Autonomous DeFi agent that monitors sentiment and executes protective fund transfers

**One bot. All channels. Fully autonomous.**

---

## 2. Problem Statement

### The Current State of AI + DeFi Is Broken

| Problem | Reality Today |
|---------|--------------|
| **Fragmented Tools** | Users juggle 5-10 separate apps: TradingView for charts, Discord bots for alerts, MetaMask for transactions, ChatGPT for analysis, n8n for automation. No single platform connects intelligence → decision → execution. |
| **Dumb AI Agents** | Most "AI agents" are simple ChatGPT wrappers — they can *answer questions* but can't *take action*. They have no market awareness, no automation, no wallet integration. |
| **No Autonomous Protection** | When markets crash, users must manually react. There's no agent that watches sentiment, detects danger, and *proactively moves funds* to safety — with human approval. |
| **DeFi Complexity** | Algorand has powerful capabilities, but the user experience is fragmented. Building transactions, signing them, monitoring the chain — all require separate tools and technical knowledge. |
| **No Telegram-Native DeFi** | 500M+ Telegram users exist, but DeFi interactions still require browser extensions, desktop wallets, and technical CLI knowledge. Mini Apps exist, but nobody has built a full autonomous DeFi agent inside one. |

### The Core Question

> *"What if your AI assistant could not only analyze markets, but autonomously detect danger, build a protective Algorand transaction, push it to your phone, and let you sign it — all from Telegram?"*

---

## 3. Our Solution

**X10V is the world's first Telegram-native Autonomous DeFi Agent with multi-LLM intelligence and Algorand on-chain execution.**

### What It Does (One Sentence)

X10V is an AI agent that **watches markets, scrapes the web, analyzes sentiment, creates automations, and autonomously executes Algorand on-chain protective transfers** — all from a single Telegram bot with 30+ commands and a real-time web dashboard.

### The Three Pillars

```
┌─────────────────────────────────────────────────────┐
│                   X10V PLATFORM                      │
├─────────────┬─────────────────┬─────────────────────┤
│  🧠 THINK   │   👀 OBSERVE    │   ⚡ ACT            │
│             │                 │                     │
│ 3-LLM Swarm│ Real-time       │ n8n Workflows       │
│ Alpha→Beta→ │ Market Data     │ Paper Trading       │
│ Gamma debate│ Web Scraping    │ Rule Engine         │
│             │ YouTube Research│ Scheduled Messages  │
│ Voice Intent│ Whale Alerts    │ Algorand TX Builder │
│ Classification│ Sentiment     │ Lute Wallet Signing │
│             │ Analysis        │ Protective Transfers│
└─────────────┴─────────────────┴─────────────────────┘
```

---

## 4. Why X10V Is Different from Current AI Agents

### Comparison Matrix

| Feature | ChatGPT / Copilot | Existing DeFi Bots | n8n / Zapier | **X10V** |
|---------|-------------------|--------------------|--------------|-----------| 
| Multi-LLM Debate (3 agents) | ❌ Single model | ❌ | ❌ | ✅ Alpha→Beta→Gamma |
| Real-time Market Data | ❌ Training cutoff | ⚠️ Limited | ❌ | ✅ yfinance + web scrape |
| Web Scraping (Playwright) | ❌ | ❌ | ⚠️ Paid nodes | ✅ Headless Chromium |
| YouTube Deep Research | ❌ | ❌ | ❌ | ✅ Transcript → AI analysis |
| n8n-Style Workflows | ❌ | ❌ | ✅ But no AI | ✅ AI-powered + NL creation |
| Algorand On-Chain Actions | ❌ | ⚠️ Basic swaps | ❌ | ✅ Full TX builder + signing |
| Autonomous Fund Protection | ❌ | ❌ | ❌ | ✅ Sentiment → protective transfer |
| Telegram Mini App Wallet | ❌ | ❌ | ❌ | ✅ Lute Wallet via Mini App |
| Voice Intent Classification | ❌ | ❌ | ❌ | ✅ Groq-powered RNN classifier |
| 30+ Commands in One Bot | ❌ | ⚠️ 5-10 | ❌ | ✅ Full-featured |
| Paper Trading Engine | ❌ | ❌ | ❌ | ✅ With slippage simulation |
| Zero API Cost for Data | ❌ Paid API | Paid API | Paid nodes | ✅ DuckDuckGo + yfinance |

### The Key Differentiators

1. **Multi-Agent Swarm, Not a Single LLM**
   - Most AI agents send one prompt to one model. X10V runs a **6-stage pipeline**: Vision → Router → Alpha (Groq, speed) → Beta (Gemini, depth) → Gamma (Gemini, final verdict). Three LLMs *debate* before any decision is made.

2. **State Isolation (No Hallucination Bleed)**
   - Every query starts from a **completely blank slate**. No conversation history is passed between calls. Context comes from **ChromaDB vector retrieval** (max 2 chunks, ~500 tokens), not from growing message arrays. This prevents the #1 problem with AI agents: hallucination from stale context.

3. **Autonomous DeFi Agent (Not Just a Chatbot)**
   - X10V doesn't just *answer questions about crypto*. It **actively monitors the Algorand blockchain**, detects whale movements, analyzes market sentiment, and when conditions are met, it **autonomously builds an unsigned Algorand transaction** and pushes it to your phone via Telegram with a **one-tap "Approve & Sign" button** that opens a Mini App for Lute Wallet signing.

4. **Natural Language → Automation Pipeline**
   - Instead of clicking through GUI builders, users type: *"Every hour check AAPL price and alert me if it drops below $170"* — and the AI parses this into a fully functional n8n-style workflow with trigger nodes, action nodes, and condition nodes.

5. **Telegram-Native (Not Browser-Dependent)**
   - Everything works inside Telegram. No browser extensions needed for daily operations. Wallet connection works via a paste-based flow optimized for Telegram's WebView environment.

---

## 5. Architecture Overview

```
                            ┌──────────────────────────────┐
                            │        USER INTERFACES       │
                            │                              │
                            │  📱 Telegram Bot (30+ cmds)  │
                            │  🌐 React Web Dashboard      │
                            │  📲 Telegram Mini App (Wallet)│
                            │  🎤 Voice Intent (Web Speech) │
                            └──────────┬───────────────────┘
                                       │
                            ┌──────────▼───────────────────┐
                            │     FastAPI Server (:8000)    │
                            │     WebSocket Live Feed       │
                            │     REST API Endpoints        │
                            └──────────┬───────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
┌─────────▼──────────┐  ┌─────────────▼────────────┐  ┌───────────▼──────────┐
│   🧠 SWARM BRAIN   │  │   ⚡ AUTOMATION ENGINE    │  │  🔗 ALGORAND INDEXER │
│                    │  │                          │  │                      │
│ ┌───────────────┐  │  │  n8n-Style Workflows     │  │  AlgodClient (SDK)   │
│ │ Vision Agent  │  │  │  Scheduled Messages      │  │  IndexerClient (SDK) │
│ │ (Gemini 2.5)  │  │  │  NL → Workflow Parser    │  │  TX Builder          │
│ └───────┬───────┘  │  │  10+ Action Node Types   │  │  Whale Monitor       │
│ ┌───────▼───────┐  │  │  DAG Execution Engine    │  │  Balance Lookup      │
│ │ Query Router  │  │  │                          │  │  Pending TX Store    │
│ │ (Groq 8b)    │  │  └──────────────────────────┘  │  Sentiment Trigger   │
│ └───────┬───────┘  │                                 └──────────────────────┘
│ ┌───────▼───────┐  │
│ │ Agent Alpha   │  │  ┌──────────────────────────┐  ┌──────────────────────┐
│ │ (Groq 8b)    │  │  │   🎯 RULE ENGINE         │  │  📊 MARKET MONITOR   │
│ │ Speed + Hypo  │  │  │                          │  │                      │
│ └───────┬───────┘  │  │  Dynamic Conditions      │  │  APScheduler Jobs    │
│ ┌───────▼───────┐  │  │  Groq NL Parser          │  │  yfinance + Scraper  │
│ │ Agent Beta    │  │  │  Auto-Execute on Match    │  │  Auto Paper Trade    │
│ │ (Gemini 2.5)  │  │  │  Groww Mock Executor     │  │  TG Push Notify      │
│ │ Deep Analyst  │  │  │                          │  │                      │
│ └───────┬───────┘  │  └──────────────────────────┘  └──────────────────────┘
│ ┌───────▼───────┐  │
│ │ Agent Gamma   │  │  ┌──────────────────────────┐  ┌──────────────────────┐
│ │ (Gemini 2.5)  │  │  │   🕷️ DEEP SCRAPER       │  │  💾 MEMORY MANAGER   │
│ │ Final Verdict │  │  │                          │  │                      │
│ └───────────────┘  │  │  DuckDuckGo URL Finder   │  │  ChromaDB Vector DB  │
│                    │  │  Playwright Chromium      │  │  Cosine Similarity   │
└────────────────────┘  │  3-Second Hard Timeout    │  │  Token-Optimized RAG │
                        └──────────────────────────┘  └──────────────────────┘
```

### Data Flow — Autonomous Protective Transfer

```
 Market Event          AI Analysis           On-Chain Action         User Approval
 ───────────          ────────────          ────────────────        ───────────────
                                                                   
 📉 Whale dumps    →  🧠 Swarm detects   →  🔗 TX Builder creates →  📱 Telegram sends
    10K ALGO           bearish sentiment      unsigned PaymentTxn     "🔐 Approve & Sign"
                       via Alpha→Beta→        to safe vault           Inline Keyboard
                       Gamma pipeline                                      │
                                                                           ▼
                                                                    📲 Mini App opens
                                                                       Lute Wallet signs
                                                                       TX submitted
                                                                           │
                                                                           ▼
                                                                    ✅ Funds safe in vault
```

---

## 6. System Components (Deep Dive)

### 6.1 Swarm Brain (`swarm_brain.py`) — The Decision Engine

The heart of X10V. A **6-stage stateless pipeline** using two LLM providers:

| Stage | Model | Role | Latency |
|-------|-------|------|---------|
| **Vision** | Gemini 2.5 Flash | Multimodal screen reading — extracts text from images, charts, dashboards | ~500ms |
| **Router** | Groq Llama-3.1-8b | Decides: does this query need live web data, or can it be answered from screen context alone? | ~200ms |
| **Alpha** | Groq Llama-3.1-8b | Speed-optimized rapid hypothesis. "Genius Student Mode" — can solve exam papers, analyze charts, generate code. | ~300ms |
| **Beta** | Gemini 2.5 Flash | Deep Analyst. Verifies Alpha's hypothesis with academic rigor. Cross-references with scraped web data. | ~800ms |
| **Gamma** | Gemini 2.5 Flash | Final Arbiter. Produces rich structured JSON verdict with summary, metrics, decision (inform/execute/abort), and file generation instructions. | ~600ms |

**Key Design: State Isolation**
- NO global message arrays
- NO conversation history passed between calls
- Context comes from ChromaDB (max 2 chunks, ~500 tokens)
- Every API call = completely blank slate
- This eliminates hallucination bleed — the #1 problem with AI chatbots

### 6.2 Automation Engine (`automation_engine.py`) — n8n Inside Telegram

A complete workflow automation engine with:

**Trigger Types:**
- `interval` — Run every N minutes
- `price_threshold` — When asset price crosses a level
- `keyword_match` — When scraped content contains keywords
- `webhook` — External HTTP trigger
- `time_once` — One-shot scheduled execution
- `on_chain_event` — Algorand blockchain event (whale alert)

**Action Node Types:**
- `send_message` — Push notification via Telegram
- `ai_analyze` — Run full 3-LLM Swarm analysis
- `web_scrape` — Playwright deep web extraction
- `stock_lookup` — yfinance real-time data
- `youtube_research` — Transcript extraction + AI summary
- `execute_trade` — Paper trade execution
- `api_call` — Generic HTTP request
- `analyze_sentiment` — Groq sentiment classification
- `execute_onchain_action` — Build Algorand transaction

**Natural Language Creation:**
```
User: "/workflow Every hour check BTC price, if above $100K alert me"
  ↓
Groq Llama-3.1-8b parses intent
  ↓
Creates workflow:
  Trigger: interval (60 min)
  Step 1: stock_lookup (BTC-USD)
  Step 2: condition (price > 100000)
  Step 3: send_message ("🚨 BTC above $100K!")
```

### 6.3 Algorand Indexer (`algorand_indexer.py`) — On-Chain Intelligence

Built on **py-algorand-sdk 2.6.1** with official `AlgodClient` and `IndexerClient`:

- **`get_algo_balance(address)`** — Real-time on-chain ALGO balance via `algod.account_info()`
- **`get_account_transactions(address)`** — Recent transaction history via `indexer.search_transactions_by_address()`
- **`poll_large_transactions(min_algo)`** — Whale alert detection via `indexer.search_transactions()`
- **`build_unsigned_payment(sender, amount, note)`** — Creates `PaymentTxn` for Mini App signing
- **`execute_onchain_action(action, amount, sender)`** — Autonomous DeFi agent action (builds TX → stores as pending → sends approval prompt to Telegram)
- **Pending TX Store** — SQLite table for Telegram → Mini App handoff

### 6.4 Telegram Bot (`tg_bot.py`) — 30+ Commands

The primary user interface with intelligent routing:

- **Free-text messages** → Intent detection → Route to appropriate handler
- **Voice commands** → Web Speech API → Groq classification → Action
- **Inline keyboards** → One-tap transaction approval/rejection
- **Mini App integration** → Wallet connection + TX signing

### 6.5 Market Monitor (`market_monitor.py`)

APScheduler-based background price monitoring:
- Checks asset prices every 5 minutes via yfinance
- Auto-executes paper trades when targets hit
- Sends Telegram push notifications
- Created automatically by the Swarm when analysis suggests "monitor_and_execute"

### 6.6 Rule Engine (`rule_engine.py`)

Dynamic conditional trading rules:
- Multi-condition logic (price + RSI + sentiment)
- Natural language creation via Groq
- Auto-evaluated every 60 seconds
- Groww Mock Executor with realistic slippage (0.01-0.08%) and fees

### 6.7 Deep Scraper (`deep_scraper.py`)

Playwright-powered headless web scraping:
- DuckDuckGo URL discovery (zero API cost)
- Headless Chromium page extraction
- 3-second hard timeout (never hangs the event loop)
- JS injection for clean text extraction

### 6.8 Memory Manager (`memory_manager.py`)

Token-optimized RAG via ChromaDB:
- Cosine similarity vector search
- Max 2 chunks, ~500 tokens per retrieval
- Agents NEVER pass full conversation histories
- Completely prevents context window overflow

### 6.9 YouTube Research (`yt_research.py`)

Domain-adaptive deep research:
- Transcript extraction via `youtube-transcript-api`
- Groq-powered summarization with structured output
- Domain detection (finance, tech, education, etc.)
- Export to JSON, Markdown, PDF

### 6.10 Voice Intent Classifier (`voice_intent.py`)

RNN-style intent classification:
- Web Speech API transcription → Groq Llama-3.1-8b
- 7 intent types: analyze_stock, summarize_video, set_automation, trade, monitor, portfolio, general_query
- Entity extraction: ticker normalization, timeframe, amounts
- Confidence scoring (0.0-1.0)

---

## 7. Algorand Integration

### Why Algorand?

| Feature | Why It Matters for X10V |
|---------|------------------------|
| **~3.3s finality** | Protective transfers execute fast enough to be useful in market downturns |
| **$0.001 fees** | Autonomous agent can trigger transactions without worrying about gas costs |
| **ABI compatibility** | Future smart contract integration for vault management |
| **Algonode free tier** | No API key needed for TestNet — zero infrastructure cost |
| **py-algorand-sdk** | Official Python SDK with `AlgodClient` + `IndexerClient` = clean integration |

### On-Chain Operations

```python
# Balance Lookup (real-time)
algod_client = algod.AlgodClient("", "https://testnet-api.algonode.cloud")
info = algod_client.account_info(address)  # → {amount, min-balance, status, ...}

# Transaction History
indexer_client = indexer.IndexerClient("", "https://testnet-idx.algonode.cloud")
txns = indexer_client.search_transactions_by_address(address, limit=10)

# Whale Detection
large_txns = indexer_client.search_transactions(min_amount=10_000_000_000)  # 10K ALGO

# Unsigned TX Builder
params = algod_client.suggested_params()
txn = transaction.PaymentTxn(sender, params, receiver, amount_microalgos, note)
unsigned_b64 = base64.b64encode(encoding.msgpack_encode(txn))
# → Stored in SQLite → Sent to Telegram → Signed in Mini App via Lute Wallet
```

### The Protective Transfer Flow

1. **Detect** — Whale monitoring + sentiment analysis detects bearish conditions
2. **Decide** — 3-LLM Swarm votes: "protective transfer recommended"
3. **Build** — `build_unsigned_payment()` creates a `PaymentTxn` to the safe vault
4. **Store** — Unsigned TX saved to `pending_transactions` table with status `pending`
5. **Prompt** — Telegram Inline Keyboard sent: "🔐 Approve & Sign (0.5 ALGO)"
6. **Sign** — User taps → Mini App opens → Lute Wallet signs → TX submitted
7. **Confirm** — Bot confirms: "✅ Funds transferred to safe vault"

### Mini App Wallet Integration

The Telegram Mini App (`webapp/`) handles two modes:

- **ConnectMode** — Paste-based wallet connection (optimized for Telegram WebView where Chrome extensions can't inject `window.algorand`)
- **SignSwapMode** — Opens in Chrome for actual Lute Wallet signing via `window.algorand.signTxns()`

---

## 8. Tech Stack

### Backend (Python 3.13)
| Component | Technology |
|-----------|-----------|
| API Server | FastAPI + Uvicorn |
| AI (Primary) | Google Gemini 2.5 Flash |
| AI (Speed) | Groq Llama-3.1-8b-instant |
| Blockchain | py-algorand-sdk 2.6.1 (AlgodClient + IndexerClient) |
| Database | SQLite + aiosqlite (async) |
| Vector DB | ChromaDB (local, in-memory) |
| Web Scraping | Playwright (headless Chromium) |
| Scheduling | APScheduler (AsyncIOScheduler) |
| Bot Framework | python-telegram-bot v22.6 |
| Market Data | yfinance (free, no API key) |
| YouTube | youtube-transcript-api |
| Live Search | duckduckgo-search (free) |

### Frontend (React 18)
| Component | Technology |
|-----------|-----------|
| Framework | React 18 + Vite 6 |
| Styling | Tailwind CSS + Framer Motion |
| WebSocket | Native WebSocket (live swarm terminal feed) |
| Blockchain | algosdk (JavaScript) |

### Telegram Mini App (Vercel)
| Component | Technology |
|-----------|-----------|
| Framework | React 18 + Vite 6 + algosdk |
| Hosting | Vercel (webapp-ten-fawn-33.vercel.app) |
| Wallet | Lute Wallet Extension (Chrome) |
| TG SDK | Telegram WebApp JavaScript SDK |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Algorand Network | TestNet via Algonode (free tier) |
| Deployment | Vercel (Mini App) + Local (Backend) |
| Repository | GitHub (bytes06runner/genie-tech) |

---

## 9. User Flow

### Flow 1: New User Onboarding
```
User sends /start
  → Bot creates account with $1,000 paper balance
  → Welcome message with quick start guide
  → User types anything → 3-LLM Swarm responds
```

### Flow 2: Market Analysis
```
User: "/analyze BTC"
  → yfinance fetches real-time BTC price
  → Alpha (Groq) generates rapid hypothesis
  → Beta (Gemini) verifies with deep analysis
  → Gamma (Gemini) produces final verdict
  → Bot sends: price, trend, support/resistance, recommendation
  → If "monitor_and_execute" → Auto-creates APScheduler job
```

### Flow 3: Autonomous Protection
```
APScheduler detects whale dump on Algorand (10K+ ALGO transfer)
  → Swarm analyzes: "bearish signal"
  → Automation engine triggers execute_onchain_action
  → TX Builder creates unsigned PaymentTxn (user funds → safe vault)
  → Bot sends Inline Keyboard: "🔐 Approve & Sign"
  → User taps → Mini App → Lute signs → Funds safe
```

### Flow 4: Natural Language Workflow
```
User: "/workflow Every morning scrape crypto news and send me a summary"
  → Groq parses: trigger=interval(1440min), steps=[web_scrape, ai_analyze, send_message]
  → Workflow saved to SQLite
  → APScheduler evaluates every 30 seconds
  → Every morning: scrapes → Swarm analyzes → sends summary to Telegram
```

### Flow 5: Wallet Connection (Telegram)
```
User: "/connect_wallet"
  → Bot shows "Open Wallet Connector" button
  → Mini App opens in Telegram WebView
  → User copies address from Lute (in Chrome) → pastes in Mini App
  → Auto-verify: algod.account_info() confirms address on TestNet
  → sendData({address, balance}) → Bot confirms wallet linked
  → /portfolio now shows real on-chain ALGO balance
```

---

## 10. Telegram Bot — 30+ Commands

| Category | Commands |
|----------|----------|
| **AI & Chat** | `/chat`, free-text messages (auto-routed through 3-LLM Swarm) |
| **Market Data** | `/stock <ticker>`, `/news <topic>`, `/scrape <query>` |
| **Research** | `/research <youtube_url>` |
| **Workflows** | `/workflow`, `/my_workflows`, `/run_workflow`, `/pause_workflow`, `/delete_workflow` |
| **Scheduling** | `/schedule`, `/my_schedules`, `/delete_schedule` |
| **Rules** | `/set_rule`, `/my_rules`, `/delete_rule`, `/suggest` |
| **Trading** | `/analyze <asset>`, `/mock_trade`, `/trade_history`, `/portfolio`, `/close` |
| **Monitors** | `/monitors`, `/cancel` |
| **Wallet** | `/connect_wallet`, `/disconnect`, `/reset_wallet`, `/transact` |
| **DeFi** | `/whale_alert`, `/pending_swaps` |

---

## 11. Security Model

| Layer | Mechanism |
|-------|-----------|
| **Wallet Safety** | No private keys stored. Lute Wallet signs externally. Bot only stores public address. |
| **TX Approval** | All on-chain actions require explicit user approval via Inline Keyboard → Mini App signing. The agent NEVER auto-submits transactions. |
| **State Isolation** | Each AI query is stateless. No conversation history leaks between users or sessions. |
| **DB Protection** | SQLite with WAL mode. Async operations via aiosqlite prevent race conditions. |
| **Timeout Safety** | All web scraping has 3-second hard timeouts. All external API calls have error boundaries. |
| **Sender Validation** | `execute_onchain_action()` returns error if no wallet connected — never uses fallback addresses. |

---

## 12. How to Win the Hackathon

### What Judges Look For → How X10V Delivers

| Criteria | X10V's Strength |
|----------|----------------|
| **Innovation** | First-ever Telegram-native autonomous DeFi agent with multi-LLM swarm intelligence. No existing project combines 3-LLM debate + n8n automation + Algorand TX builder + Mini App signing in one bot. |
| **Algorand Usage** | Deep SDK integration: AlgodClient (balance, TX params), IndexerClient (whale alerts, TX history), PaymentTxn builder, Mini App signing with Lute, TestNet operations. Not a token — it's infrastructure. |
| **Technical Depth** | 15 Python modules, 6000+ lines of backend code, 3 frontends (web dashboard, Telegram bot, Mini App), 6-stage AI pipeline, APScheduler automation, ChromaDB memory, Playwright scraping. |
| **User Experience** | 30+ Telegram commands, natural language workflow creation, one-tap TX approval, paste-based wallet connect, real-time web dashboard with live WebSocket feed. |
| **Completeness** | Not a prototype — it's a working product. Real on-chain balance display, real TX building, real whale monitoring, real automation execution. Every feature works end-to-end. |
| **Presentation** | Live demo: connect wallet → create workflow → trigger whale alert → see autonomous protective transfer → sign in Mini App. The demo tells a story. |

### Winning Demo Script (3 minutes)

1. **"Meet X10V"** (30s) — Show the web dashboard with animated hero + live Swarm Terminal
2. **"It Thinks"** (30s) — Type a question in Telegram → watch 3 agents debate in the terminal
3. **"It Observes"** (30s) — `/stock BTC` → real-time data. `/whale_alert` → blockchain scan
4. **"It Automates"** (30s) — `/workflow Every hour check AAPL and alert me` → workflow created in seconds
5. **"It Protects"** (60s) — Show the DeFi flow: whale dump detected → Swarm analyzes → protective transfer prompt → open Mini App → sign with Lute → funds safe
6. **"One Bot. All Channels."** (30s) — Recap: 30+ commands, web + Telegram + Mini App, real Algorand integration

---

## 13. Future Roadmap

| Phase | Feature |
|-------|---------|
| **v3.1** | MainNet deployment with real ALGO operations |
| **v3.2** | ASA (Algorand Standard Asset) monitoring and portfolio tracking |
| **v3.3** | Smart contract vault with multi-sig protection |
| **v3.4** | DEX integration (Tinyman, Pact) for automated swaps |
| **v3.5** | Multi-user organization mode with shared automations |
| **v4.0** | Voice-first mode: full voice-controlled DeFi operations |

---

## 14. Quick Start / Running Locally

### Prerequisites
- Python 3.13+
- Node.js 18+
- Lute Wallet Chrome Extension

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env with:
# GROQ_API_KEY=your_groq_key
# GEMINI_API_KEY=your_gemini_key
# TELEGRAM_BOT_TOKEN=your_bot_token
# WEBAPP_URL=https://your-webapp.vercel.app

python server.py  # Starts FastAPI on :8000 + Telegram bot
```

### Frontend (Web Dashboard)
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

### Mini App (Telegram Wallet)
```bash
cd webapp
npm install
npm run build
npx vercel --prod  # Deploy to Vercel
```

### Environment Variables
| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for Llama-3.1-8b-instant |
| `GEMINI_API_KEY` | Google AI API key for Gemini 2.5 Flash |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `WEBAPP_URL` | Deployed Mini App URL (Vercel) |

---

## License

Built for the Algorand Hackathon by **Team Genie Tech**.

---

*"X10V doesn't just answer questions about DeFi. It watches, thinks, and acts — autonomously protecting your assets while you sleep."*
