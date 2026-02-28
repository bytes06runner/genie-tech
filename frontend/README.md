# X10V AI Swarm — Frontend

> Omni-Channel Autonomous Intelligence Agent — Voice · Web · Telegram · YouTube

A modern, reactive frontend for the X10V AI Swarm platform featuring an animated hero landing page, real-time WebSocket dashboard, voice assistant, YouTube deep research, and more.

---

## Tech Stack

| Technology | Purpose |
|---|---|
| **React 18** | UI framework (JSX, hooks) |
| **Vite 6** | Build tooling & dev server |
| **Tailwind CSS 3** | Utility-first responsive styling |
| **Framer Motion** | Animations & transitions |
| **Lucide React** | Icon library |
| **shadcn/ui pattern** | `Button` component via Radix + CVA |
| **class-variance-authority** | Type-safe component variants |
| **@radix-ui/react-slot** | Polymorphic component composition |

---

## Setup Instructions

```bash
# 1. Clone the repository
git clone https://github.com/bytes06runner/genie-tech.git
cd genie-tech/frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
# → http://localhost:5173

# 4. Build for production
npm run build
npm run preview
```

> **Prerequisite:** The FastAPI backend must be running on `localhost:8000` for WebSocket connections and API calls to work. See `../backend/README.md`.

---

## Project Structure

```
frontend/
├── index.html                   # HTML entry point
├── package.json                 # Dependencies & scripts
├── vite.config.js               # Vite config with @ path alias
├── tailwind.config.js           # Tailwind theme (colors, fonts)
├── postcss.config.js            # PostCSS plugins
├── public/
│   └── vite.svg                 # Static assets
└── src/
    ├── main.jsx                 # React root mount
    ├── App.jsx                  # Root component (Hero → Dashboard)
    ├── index.css                # Tailwind directives + custom animations
    ├── lib/
    │   └── utils.js             # cn() class merge utility (clsx + twMerge)
    └── components/
        ├── Dashboard.jsx        # Main dashboard with WS, tasks, logs
        ├── OmniInput.jsx        # Natural-language command input
        ├── SwarmTerminal.jsx    # Real-time log terminal
        ├── TaskQueue.jsx        # Active task list
        ├── PiPAgent.jsx         # Picture-in-Picture screen sharing
        ├── VoiceAssistant.jsx   # Groq voice intent classifier
        ├── YouTubeResearch.jsx  # YouTube transcript → AI analysis
        └── ui/                  # shadcn-style reusable primitives
            ├── button.jsx       # Button with variant/size support
            └── background-paths.jsx  # Animated SVG hero section
```

---

## Key Design Decisions

### 1. Animated Hero Landing Page (`BackgroundPaths`)
The hero uses **36 animated SVG cubic-bezier paths** rendered in two mirrored layers (`position=1` and `position=-1`). This creates a flowing circuit-board effect inspired by the EQTY Lab dark aesthetic — near-black `#0a0a0a` background with emerald `#10b981` accent gradients. Each letter in the headline animates with a spring physics effect.

### 2. shadcn/ui Component Pattern (without full shadcn)
Rather than installing the full `shadcn` CLI and TypeScript, we adopted the **shadcn pattern** — manually creating `src/components/ui/` with CVA-based variant components and a `cn()` utility in `src/lib/utils.js`. This gives us the same composable API without requiring a TypeScript migration.

### 3. `@/` Path Alias
Configured in `vite.config.js` via `resolve.alias`, allowing clean imports like:
```js
import { Button } from "@/components/ui/button";
```
This mirrors shadcn's default convention and keeps imports readable.

### 4. Dark Theme First
The entire UI is dark-themed to match the EQTY Lab reference design:
- Background: `#0a0a0a` (near-black)
- Accent: Emerald gradient (`#065f46` → `#10b981` → `#34d399`)
- Text: White with opacity layers for hierarchy
- Radial glow behind hero center for depth

### 5. Component Architecture
Each feature is isolated into its own component with zero cross-dependencies:
- **Dashboard** orchestrates layout + WebSocket connection
- **OmniInput** handles command submission
- **SwarmTerminal** renders real-time logs
- **VoiceAssistant** and **YouTubeResearch** are fully self-contained side panels

---

## Responsive Behavior

| Breakpoint | Layout |
|---|---|
| **Mobile** (`<640px`) | Single column, stacked sections, 5xl headline |
| **Tablet** (`sm:` 640px+) | 7xl headline, wider padding |
| **Desktop** (`md:` 768px+) | 8xl headline, side-by-side panels in dashboard |
| **Wide** (`lg:` 1024px+) | Full two-column grid layout |

---

## Environment

The frontend expects these backend endpoints (default `localhost:8000`):

- `ws://localhost:8000/ws` — WebSocket for real-time swarm logs
- `GET /tasks` — Fetch active task queue
- `POST /api/swarm` — Submit natural-language commands
- `POST /api/voice-intent` — Voice intent classification
- `POST /api/youtube-research` — YouTube transcript analysis
- `POST /api/youtube-pdf` — PDF export generation

---

*Built for the X10V AI Swarm Hackathon — Omni-Channel Autonomous Intelligence Agent*
