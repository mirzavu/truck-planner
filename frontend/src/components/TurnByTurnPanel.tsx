import { useState, useEffect, useRef } from 'react'
import { ArrowRight, CornerUpLeft, CornerUpRight, ArrowUp, ArrowDown, MapPin, Navigation } from 'lucide-react'
import type { RouteLeg } from '../types'

function getDirectionIcon(instruction: string) {
  const lower = instruction.toLowerCase()
  if (lower.includes('left')) return <CornerUpLeft className="w-5 h-5" />
  if (lower.includes('right')) return <CornerUpRight className="w-5 h-5" />
  if (lower.includes('head') || lower.includes('continue') || lower.includes('straight')) return <ArrowUp className="w-5 h-5" />
  if (lower.includes('exit') || lower.includes('merge')) return <Navigation className="w-5 h-5" />
  if (lower.includes('south')) return <ArrowDown className="w-5 h-5" />
  if (lower.includes('arrive') || lower.includes('destination')) return <MapPin className="w-5 h-5" />
  return <ArrowUp className="w-5 h-5" /> // fallback
}

export function TurnByTurnPanel({ legs }: { legs: RouteLeg[] }) {
  const [activeStepId, setActiveStepId] = useState<string | null>(null)
  
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    
    // Observer for the active step highlight
    const stepObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          setActiveStepId(entry.target.id)
        }
      })
    }, {
      root: containerRef.current,
      rootMargin: '-20% 0px -70% 0px', // Trigger point a bit further down from the sticky header
      threshold: 0
    })

    const stepEls = containerRef.current.querySelectorAll('.route-step-item')
    stepEls.forEach(el => stepObserver.observe(el))

    return () => {
      stepObserver.disconnect()
    }
  }, [legs])

  if (!legs || legs.length === 0) return null

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-[24px] border border-[#132a38]/10 shadow-sm flex flex-col overflow-hidden h-[480px] relative">
      {/* Static Header Info */}
      <div className="p-6 border-b border-[#132a38]/5 shrink-0 bg-white/90 z-40 relative">
        <p className="text-[#0a4f5f] text-[10px] font-bold uppercase tracking-widest mb-1">Route instructions</p>
        <h2 className="font-serif text-2xl font-bold text-[#132a38]">Turn-by-turn highlights</h2>
      </div>

      {/* Scrollable List */}
      <div ref={containerRef} className="overflow-y-auto px-4 pb-4 flex-1 scrollbar-thin scrollbar-thumb-gray-300 relative">
        {legs.map((leg, lIdx) => (
          <div key={`${leg.from}-${leg.to}-${lIdx}`} className="relative pb-6">
            
            {/* Sticky Native Leg Header */}
            <div className="sticky top-0 z-30 bg-[#f9f5ec]/95 backdrop-blur-md border-b border-[#132a38]/5 py-3 -mx-4 px-4 mb-4 shadow-[0_4px_10px_-6px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3 text-[#132a38]">
                <div className="bg-[#d44b2c]/10 text-[#d44b2c] p-1.5 rounded-lg shrink-0">
                  <Navigation className="w-4 h-4" />
                </div>
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-semibold text-sm truncate">{leg.from}</span>
                  <ArrowRight className="w-4 h-4 shrink-0 text-[#0a4f5f]/50" />
                  <span className="font-semibold text-sm truncate">{leg.to}</span>
                </div>
              </div>
            </div>
            
            <div className="relative pl-6 space-y-2">
              {/* Progress Line */}
              <div className="absolute left-2.5 top-0 bottom-0 w-px bg-gradient-to-b from-[#132a38]/5 via-[#132a38]/10 to-[#132a38]/5"></div>
              
              <div className="space-y-1">
                {leg.steps.map((step, sIdx) => {
                  const stepId = `step-${lIdx}-${sIdx}`
                  const isActive = activeStepId === stepId
                  
                  return (
                    <div 
                      key={stepId} 
                      id={stepId}
                      className={`route-step-item relative p-3 rounded-xl flex items-center justify-between gap-4 transition-all duration-300 border ${
                        isActive 
                          ? 'bg-gradient-to-r from-[#eef4f6] to-[#fffcf5] border-[#0a4f5f]/20 shadow-[0_2px_10px_-4px_rgba(10,79,95,0.1)]' 
                          : 'bg-transparent border-transparent hover:bg-[#132a38]/5'
                      }`}
                    >
                      {/* Active indicator dot on the progress line */}
                      {isActive && (
                        <div className="absolute -left-[17px] top-1/2 -mt-1 w-2 h-2 rounded-full bg-[#d44b2c] shadow-[0_0_0_4px_rgba(212,75,44,0.1)] transition-all duration-300"></div>
                      )}

                      <div className={`shrink-0 flex items-center justify-center w-9 h-9 rounded-full transition-colors ${
                        isActive ? 'bg-[#0a4f5f] text-white shadow-md' : 'bg-[#132a38]/5 text-[#132a38]/60'
                      }`}>
                        {getDirectionIcon(step.instruction)}
                      </div>
                      
                      <div className="flex-1 min-w-0 pr-2">
                        <strong className={`block text-[13px] leading-snug transition-colors ${isActive ? 'text-[#132a38] font-bold' : 'text-[#132a38]/80 font-semibold'}`}>
                          {step.instruction}
                        </strong>
                      </div>
                      
                      <div className="text-right shrink-0 flex flex-col justify-center">
                        <span className={`block text-xs font-bold ${isActive ? 'text-[#0a4f5f]' : 'text-[#132a38]'}`}>{step.distanceMiles} <span className="text-[10px] font-medium opacity-70">mi</span></span>
                        {step.durationMinutes > 0 && (
                          <span className="block text-[10px] font-semibold text-gray-500">{step.durationMinutes} min</span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
