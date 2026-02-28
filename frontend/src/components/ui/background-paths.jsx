/**
 * BackgroundPaths — Animated SVG hero section with floating path lines.
 *
 * Inspired by EQTY Lab's dark, futuristic aesthetic. Renders 36 animated SVG
 * paths that flow continuously across the viewport, creating a living circuit-board
 * effect behind hero content.
 *
 * @module ui/background-paths
 *
 * @example
 * <BackgroundPaths title="Verify to Trust AI" />
 */
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";

/**
 * Renders a field of animated SVG paths that drift across the viewport.
 * Two instances are typically layered (position=1 and position=-1) to
 * create depth and visual richness.
 *
 * @param {{ position: number }} props
 * @param {number} props.position - Multiplier that offsets path coordinates.
 *   Use 1 for left-flowing and -1 for right-flowing layers.
 * @returns {JSX.Element}
 */
function FloatingPaths({ position }) {
  /* Generate 36 unique SVG cubic-bezier paths with increasing opacity & width */
  const paths = Array.from({ length: 36 }, (_, i) => ({
    id: i,
    d: `M-${380 - i * 5 * position} -${189 + i * 6}C-${
      380 - i * 5 * position
    } -${189 + i * 6} -${312 - i * 5 * position} ${216 - i * 6} ${
      152 - i * 5 * position
    } ${343 - i * 6}C${616 - i * 5 * position} ${470 - i * 6} ${
      684 - i * 5 * position
    } ${875 - i * 6} ${684 - i * 5 * position} ${875 - i * 6}`,
    width: 0.5 + i * 0.03,
  }));

  return (
    <div className="absolute inset-0 pointer-events-none">
      <svg
        className="w-full h-full"
        viewBox="0 0 696 316"
        fill="none"
      >
        <title>Background Paths</title>
        {paths.map((path) => (
          <motion.path
            key={path.id}
            d={path.d}
            stroke="url(#eqty-gradient)"
            strokeWidth={path.width}
            strokeOpacity={0.08 + path.id * 0.02}
            initial={{ pathLength: 0.3, opacity: 0.6 }}
            animate={{
              pathLength: 1,
              opacity: [0.3, 0.6, 0.3],
              pathOffset: [0, 1, 0],
            }}
            transition={{
              duration: 20 + Math.random() * 10,
              repeat: Infinity,
              ease: "linear",
            }}
          />
        ))}
        {/* Gradient definition: dark-teal → emerald matching EQTY Lab palette */}
        <defs>
          <linearGradient id="eqty-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#065f46" />
            <stop offset="50%" stopColor="#10b981" />
            <stop offset="100%" stopColor="#34d399" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}

/**
 * Full-screen hero section with animated background paths and a CTA button.
 *
 * Themed after EQTY Lab's dark design — near-black background, emerald/green
 * accent gradients, and clean sans-serif typography.
 *
 * @param {object} props
 * @param {string} [props.title="X10V AI Swarm"] - Hero headline text.
 *   Each word animates in sequentially with a spring effect.
 * @param {string} [props.subtitle] - Optional subtitle beneath the headline.
 * @param {string} [props.ctaText="Launch Dashboard"] - Call-to-action button label.
 * @param {() => void} [props.onCtaClick] - Handler fired when CTA is pressed.
 * @returns {JSX.Element}
 */
export function BackgroundPaths({
  title = "X10V AI Swarm",
  subtitle = "Omni-Channel Autonomous Intelligence Agent",
  ctaText = "Launch Dashboard",
  onCtaClick,
}) {
  const words = title.split(" ");

  return (
    <div className="relative min-h-screen w-full flex items-center justify-center overflow-hidden bg-[#0a0a0a]">
      {/* Dual-layer animated path backgrounds */}
      <div className="absolute inset-0">
        <FloatingPaths position={1} />
        <FloatingPaths position={-1} />
      </div>

      {/* Radial glow behind center content — EQTY Lab style */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-emerald-500/5 blur-[120px]" />
      </div>

      {/* Hero content */}
      <div className="relative z-10 container mx-auto px-4 md:px-6 text-center">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 2 }}
          className="max-w-4xl mx-auto"
        >
          {/* Animated headline — each letter springs in */}
          <h1 className="text-5xl sm:text-7xl md:text-8xl font-bold mb-6 tracking-tighter">
            {words.map((word, wordIndex) => (
              <span
                key={wordIndex}
                className="inline-block mr-4 last:mr-0"
              >
                {word.split("").map((letter, letterIndex) => (
                  <motion.span
                    key={`${wordIndex}-${letterIndex}`}
                    initial={{ y: 100, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{
                      delay: wordIndex * 0.1 + letterIndex * 0.03,
                      type: "spring",
                      stiffness: 150,
                      damping: 25,
                    }}
                    className="inline-block text-transparent bg-clip-text
                      bg-gradient-to-r from-white to-white/80"
                  >
                    {letter}
                  </motion.span>
                ))}
              </span>
            ))}
          </h1>

          {/* Subtitle */}
          {subtitle && (
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8, duration: 0.8 }}
              className="text-lg md:text-xl text-gray-400 mb-10 max-w-2xl mx-auto font-light"
            >
              {subtitle}
            </motion.p>
          )}

          {/* CTA button with glass-morphism border */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.2, duration: 0.6 }}
          >
            <div
              className="inline-block group relative bg-gradient-to-b from-emerald-500/20 to-emerald-900/10
                p-px rounded-2xl backdrop-blur-lg overflow-hidden
                shadow-lg shadow-emerald-500/5 hover:shadow-emerald-500/20 transition-shadow duration-300"
            >
              <Button
                variant="ghost"
                onClick={onCtaClick}
                className="rounded-[1.15rem] px-8 py-6 text-lg font-semibold backdrop-blur-md
                  bg-[#0a0a0a]/95 hover:bg-[#111]/100
                  text-white transition-all duration-300
                  group-hover:-translate-y-0.5
                  border border-emerald-500/20 hover:border-emerald-500/40
                  hover:shadow-md"
              >
                <span className="opacity-90 group-hover:opacity-100 transition-opacity text-emerald-400">
                  {ctaText}
                </span>
                <span
                  className="ml-3 opacity-70 group-hover:opacity-100 group-hover:translate-x-1.5
                    transition-all duration-300 text-emerald-400"
                >
                  →
                </span>
              </Button>
            </div>
          </motion.div>
        </motion.div>
      </div>

      {/* Bottom fade to connect hero to dashboard */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#0a0a0a] to-transparent pointer-events-none" />
    </div>
  );
}
