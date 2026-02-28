/**
 * App.jsx — Root application component.
 *
 * Renders an animated hero landing page (BackgroundPaths) followed by
 * the full X10V AI Swarm Dashboard. The CTA button on the hero smoothly
 * scrolls the user into the dashboard section.
 *
 * @module App
 */
import { useRef } from 'react'
import { BackgroundPaths } from '@/components/ui/background-paths'
import Dashboard from './components/Dashboard'

function App() {
  const dashRef = useRef(null)

  /** Smooth-scroll to the dashboard when CTA is clicked */
  const handleLaunch = () => {
    dashRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="bg-[#0a0a0a] min-h-screen">
      {/* Hero Section — animated paths + headline */}
      <BackgroundPaths
        title="X10V AI Swarm"
        subtitle="Omni-Channel Autonomous Intelligence Agent — Voice · Web · Telegram · YouTube"
        ctaText="Launch Dashboard"
        onCtaClick={handleLaunch}
      />

      {/* Dashboard Section */}
      <div ref={dashRef}>
        <Dashboard />
      </div>
    </div>
  )
}

export default App
