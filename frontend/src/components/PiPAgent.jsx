import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { PictureInPicture2, X } from 'lucide-react'

/**
 * PiPAgent — Document Picture-in-Picture floating command center.
 *
 * Renders `children` (OmniInput + SwarmTerminal) inside an always-on-top
 * PiP window via React Portal. Clones all stylesheets into the PiP document
 * so Tailwind + custom CSS render identically.
 *
 * Props:
 *   isOpen       — controlled open state
 *   onOpen       — callback to request PiP open
 *   onClose      — callback when PiP closes (user or browser)
 *   children     — React nodes to render inside the floating window
 */
export default function PiPAgent({ isOpen, onOpen, onClose, children }) {
  const [pipWindow, setPipWindow] = useState(null)
  const [portalContainer, setPortalContainer] = useState(null)
  const pipSupported = typeof window !== 'undefined' && 'documentPictureInPicture' in window

  // -------------------------------------------------------------------
  // Open the PiP window
  // -------------------------------------------------------------------
  const openPiP = useCallback(async () => {
    if (!pipSupported) {
      alert(
        'Document Picture-in-Picture is not supported in this browser.\n\n' +
        'Please use Chrome 116+ or Edge 116+ on desktop.'
      )
      return
    }

    try {
      const pip = await window.documentPictureInPicture.requestWindow({
        width: 480,
        height: 640,
      })

      // Clone all stylesheets from the main document into the PiP window
      // This ensures Tailwind and our custom CSS work inside the portal
      const mainStyles = [...document.styleSheets]
      for (const sheet of mainStyles) {
        try {
          if (sheet.href) {
            // External stylesheet — create a <link>
            const link = pip.document.createElement('link')
            link.rel = 'stylesheet'
            link.href = sheet.href
            pip.document.head.appendChild(link)
          } else if (sheet.cssRules) {
            // Inline <style> — clone rules
            const style = pip.document.createElement('style')
            let cssText = ''
            for (const rule of sheet.cssRules) {
              cssText += rule.cssText + '\n'
            }
            style.textContent = cssText
            pip.document.head.appendChild(style)
          }
        } catch {
          // CORS-restricted sheet — skip silently
        }
      }

      // Inject a small override for the PiP window body
      const pipOverride = pip.document.createElement('style')
      pipOverride.textContent = `
        *, *::before, *::after { box-sizing: border-box; }
        html, body {
          margin: 0; padding: 0;
          background: #0D1117;
          color: #FAF9F6;
          font-family: Inter, system-ui, -apple-system, sans-serif;
          overflow-x: hidden;
        }
        /* Scrollbar inside PiP */
        .terminal-scroll::-webkit-scrollbar { width: 5px; }
        .terminal-scroll::-webkit-scrollbar-track { background: #0D1117; }
        .terminal-scroll::-webkit-scrollbar-thumb { background: #21262D; border-radius: 3px; }
        /* Blinking cursor */
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        .cursor-blink { animation: blink 1.1s step-end infinite; }
        @keyframes pulse-soft { 0%,100%{opacity:1} 50%{opacity:0.6} }
        .pulse-soft { animation: pulse-soft 2s ease-in-out infinite; }
      `
      pip.document.head.appendChild(pipOverride)

      // Set title
      pip.document.title = 'X10V — Floating Agent'

      // Create a mount point inside PiP body
      const container = pip.document.createElement('div')
      container.id = 'pip-root'
      pip.document.body.appendChild(container)

      // Listen for PiP window close
      pip.addEventListener('pagehide', () => {
        setPipWindow(null)
        setPortalContainer(null)
        onClose?.()
      })

      setPipWindow(pip)
      setPortalContainer(container)
      onOpen?.()
    } catch (err) {
      console.error('PiP open failed:', err)
      alert(`Could not open PiP window: ${err.message}`)
    }
  }, [pipSupported, onOpen, onClose])

  // -------------------------------------------------------------------
  // Close the PiP window programmatically
  // -------------------------------------------------------------------
  const closePiP = useCallback(() => {
    if (pipWindow) {
      pipWindow.close()
      setPipWindow(null)
      setPortalContainer(null)
      onClose?.()
    }
  }, [pipWindow, onClose])

  // Sync controlled state
  useEffect(() => {
    if (isOpen && !pipWindow) openPiP()
    if (!isOpen && pipWindow) closePiP()
  }, [isOpen, pipWindow, openPiP, closePiP])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pipWindow) pipWindow.close()
    }
  }, [pipWindow])

  // -------------------------------------------------------------------
  // The "Pop Out Agent" button (rendered inline in the main dashboard)
  // -------------------------------------------------------------------
  const triggerButton = (
    <button
      onClick={isOpen ? closePiP : openPiP}
      disabled={!pipSupported}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-sans font-medium
        transition-all duration-200 border
        ${isOpen
          ? 'bg-terminal-cyan/10 border-terminal-cyan/30 text-terminal-cyan hover:bg-terminal-cyan/20'
          : 'bg-white border-charcoal/8 text-charcoal-muted hover:border-slate-accent/40 hover:text-slate-accent'
        }
        ${!pipSupported ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
      `}
      title={
        !pipSupported
          ? 'Document PiP requires Chrome/Edge 116+'
          : isOpen
            ? 'Close floating agent'
            : 'Pop out Command Center as floating widget'
      }
    >
      {isOpen ? <X size={14} /> : <PictureInPicture2 size={14} />}
      {isOpen ? 'Close PiP' : 'Pop Out Agent'}
    </button>
  )

  // -------------------------------------------------------------------
  // The PiP portal content — dark themed floating widget
  // -------------------------------------------------------------------
  const pipContent = portalContainer
    ? createPortal(
        <div className="min-h-screen bg-terminal-bg text-cream p-4 space-y-4">
          {/* PiP Header */}
          <div className="flex items-center justify-between pb-3 border-b border-terminal-border">
            <div className="flex items-center gap-2">
              <div className="flex gap-1">
                <div className="w-2 h-2 rounded-full bg-terminal-cyan" />
                <div className="w-2 h-2 rounded-full bg-terminal-yellow" />
                <div className="w-2 h-2 rounded-full bg-terminal-green" />
              </div>
              <span className="text-sm font-mono text-terminal-muted">
                X10V Agent
              </span>
            </div>
            <button
              onClick={closePiP}
              className="p-1 rounded hover:bg-terminal-border/50 text-terminal-muted
                         hover:text-terminal-red transition-colors"
            >
              <X size={14} />
            </button>
          </div>

          {/* Floating children — OmniInput + SwarmTerminal */}
          {children}
        </div>,
        portalContainer,
      )
    : null

  return (
    <>
      {triggerButton}
      {pipContent}
    </>
  )
}
