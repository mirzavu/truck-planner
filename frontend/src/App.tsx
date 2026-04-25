import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { ConfigProvider, DatePicker, Modal } from 'antd'
import dayjs from 'dayjs'

import { fetchTripPlan } from './api'
import type { DailyLog, DutyStatus, Stop, TripPlanResponse } from './types'

const demoRequest = {
  currentLocation: 'Dallas, TX',
  pickupLocation: 'Oklahoma City, OK',
  dropoffLocation: 'Denver, CO',
  cycleUsedHours: '18',
  startAt: '2026-04-26T08:00',
}

function formatDate(isoDate: string, timeZone: string) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone,
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(isoDate))
}

function stopSummary(stop: Stop) {
  return `${stop.durationMinutes} min`
}

function RouteMap({ route, stops }: { route: TripPlanResponse['route']; stops: Stop[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerGroupRef = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    mapRef.current = L.map(containerRef.current, {
      zoomControl: true,
      scrollWheelZoom: false,
    }).setView([39.5, -98.35], 4)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(mapRef.current)

    layerGroupRef.current = L.layerGroup().addTo(mapRef.current)

    return () => {
      mapRef.current?.remove()
      mapRef.current = null
      layerGroupRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!mapRef.current || !layerGroupRef.current) return

    const map = mapRef.current
    const layerGroup = layerGroupRef.current
    layerGroup.clearLayers()

    const points = route.geometry.coordinates.map(([lng, lat]) => [lat, lng] as [number, number])
    if (points.length === 0) return

    const routeLine = L.polyline(points, {
      color: '#d44b2c',
      weight: 5,
      opacity: 0.95,
    })
    routeLine.addTo(layerGroup)

    for (const stop of stops) {
      const color = stop.type === 'pickup' || stop.type === 'dropoff' ? '#0a4f5f' : '#d44b2c'
      L.circleMarker([stop.lat, stop.lng], {
        radius: 7,
        color,
        weight: 3,
        fillColor: '#f8f1dc',
        fillOpacity: 1,
      })
        .bindPopup(`<strong>${stop.label}</strong><br/>${stop.locationName}`)
        .addTo(layerGroup)
    }

    map.fitBounds(routeLine.getBounds(), { padding: [28, 28] })
  }, [route, stops])

  return <div ref={containerRef} className="h-full w-full rounded-xl z-0" />
}

const ROW_Y: Record<DutyStatus, number> = {
  off_duty: 178,
  sleeper_berth: 199,
  driving: 220,
  on_duty_not_driving: 241,
}

function DailyLogSheet({ log }: { log: DailyLog }) {
  const [isExpanded, setIsExpanded] = useState(false)

  const dateParts = useMemo(() => {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: log.timezone, hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    }).formatToParts(new Date(log.segments[0]?.startAt ?? `${log.date}T00:00:00Z`))
    const partMap = Object.fromEntries(parts.map((part) => [part.type, part.value]))
    return { year: partMap.year ?? '0000', month: partMap.month ?? '00', day: partMap.day ?? '00' }
  }, [log])

  const path = useMemo(() => {
    if (log.segments.length === 0) return ''
    const points: string[] = []
    log.segments.forEach((segment, index) => {
      const getHourVal = (iso: string) => {
        const d = new Intl.DateTimeFormat('en-US', { timeZone: log.timezone, hour12: false, hour: '2-digit', minute: '2-digit' }).formatToParts(new Date(iso))
        const map = Object.fromEntries(d.map(p => [p.type, p.value]))
        return Number(map.hour) + Number(map.minute) / 60
      }
      const startX = 60 + (getHourVal(segment.startAt) / 24) * 400
      const endX = 60 + (getHourVal(segment.endAt) / 24) * 400
      const rowY = ROW_Y[segment.status]

      points.push(index === 0 ? `M ${startX.toFixed(2)} ${rowY}` : `L ${startX.toFixed(2)} ${rowY}`)
      points.push(`L ${endX.toFixed(2)} ${rowY}`)
      if (log.segments[index + 1]) points.push(`L ${endX.toFixed(2)} ${ROW_Y[log.segments[index + 1].status]}`)
    })
    return points.join(' ')
  }, [log])

  const LogGraphic = (
    <div className="relative w-full aspect-[513/518] bg-contain bg-no-repeat bg-center" style={{ backgroundImage: 'url(/blank-paper-log.png)' }}>
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 513 518">
        <text className="text-[11px] font-semibold fill-[#11242d]" x="265" y="25">{dateParts.month}</text>
        <text className="text-[11px] font-semibold fill-[#11242d]" x="312" y="25">{dateParts.day}</text>
        <text className="text-[11px] font-semibold fill-[#11242d]" x="359" y="25">{dateParts.year}</text>
        <text className="text-[8px] font-semibold fill-[#11242d]" x="84" y="85">{log.totalMiles.toFixed(0)}</text>
        <text className="text-[8px] font-semibold fill-[#11242d]" x="294" y="85">{log.header.carrierName}</text>
        <text className="text-[8px] font-semibold fill-[#11242d]" x="294" y="101">{log.header.mainOfficeAddress.slice(0, 38)}</text>
        <text className="text-[8px] font-semibold fill-[#11242d]" x="294" y="116">{log.header.homeTerminalAddress.slice(0, 38)}</text>
        <text className="text-[8px] font-semibold fill-[#11242d]" x="76" y="117">{log.header.truckNumber}/{log.header.trailerNumber}</text>
        <text className="text-[8px] font-semibold fill-[#11242d]" x="28" y="365">{log.header.shippingDocument}</text>
        <path d={path} fill="none" stroke="#1670b8" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
        <text className="text-[8px] font-bold fill-[#11242d] text-center" x="490" y="184">{log.dutyTotals.offDuty}</text>
        <text className="text-[8px] font-bold fill-[#11242d] text-center" x="490" y="205">{log.dutyTotals.sleeperBerth}</text>
        <text className="text-[8px] font-bold fill-[#11242d] text-center" x="490" y="226">{log.dutyTotals.driving}</text>
        <text className="text-[8px] font-bold fill-[#11242d] text-center" x="490" y="247">{log.dutyTotals.onDutyNotDriving}</text>
        {log.remarks.slice(0, 5).map((remark, i) => (
          <text key={i} className="text-[7px] fill-[#11242d]" x="28" y={394 + i * 16}>
            {new Intl.DateTimeFormat('en-US', { timeZone: log.timezone, hour: 'numeric', minute: '2-digit' }).format(new Date(remark.at))} {remark.label.slice(0, 62)}
          </text>
        ))}
      </svg>
    </div>
  )

  return (
    <>
      <article id={`log-${log.date}`} className="border border-[#132a38]/10 rounded-2xl bg-[#fffcf5] p-4 flex flex-col gap-3 min-w-[320px] snap-center">
        <header className="flex justify-between items-start">
          <div>
            <p className="text-[10px] font-bold text-[#0a4f5f] uppercase tracking-wider mb-1">Daily log</p>
            <h3 className="font-serif text-[#132a38] text-xl font-bold">{log.date}</h3>
          </div>
          <div className="text-xs text-gray-500">{log.timezone}</div>
        </header>
        <div 
          className="p-1.5 rounded-xl bg-gradient-to-b from-[#fff8ea] to-[#f6eacc] cursor-pointer hover:shadow-md transition-all group"
          onClick={() => setIsExpanded(true)}
        >
          <div className="relative overflow-hidden rounded-lg">
            {LogGraphic}
            <div className="absolute inset-0 bg-[#d44b2c]/0 group-hover:bg-[rgba(212,75,44,0.15)] transition-colors flex items-center justify-center">
               <span className="opacity-0 group-hover:opacity-100 bg-white/95 text-[#132a38] text-xs font-bold px-4 py-2 rounded-full shadow-sm transition-all duration-300 transform scale-95 group-hover:scale-100">
                 Click to enlarge
               </span>
            </div>
          </div>
        </div>
      </article>

      <Modal 
        open={isExpanded} 
        onCancel={() => setIsExpanded(false)} 
        footer={null} 
        width="90vw"
        style={{ maxWidth: 800 }}
        centered
        title={<span className="font-serif text-xl border-none">Daily Log: {log.date}</span>}
      >
        <div className="mt-4 p-2 md:p-6 bg-[#fffcf5] rounded-xl border border-[#132a38]/10 pointer-events-none">
          {LogGraphic}
        </div>
      </Modal>
    </>
  )
}

export default function App() {
  const [formData, setFormData] = useState(demoRequest)
  const [plan, setPlan] = useState<TripPlanResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const deferredPlan = useDeferredValue(plan)
  const flattenedSteps = useMemo(() => deferredPlan?.route.legs.flatMap((leg) => leg.steps.map((step) => ({
    ...step, key: `${leg.from}-${leg.to}-${step.instruction}-${step.distanceMiles}`, leg: `${leg.from} to ${leg.to}`,
  }))) ?? [], [deferredPlan])

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetchTripPlan({
        currentLocation: formData.currentLocation,
        pickupLocation: formData.pickupLocation,
        dropoffLocation: formData.dropoffLocation,
        cycleUsedHours: Number(formData.cycleUsedHours),
        startAt: formData.startAt ? new Date(formData.startAt).toISOString() : undefined,
      })
      startTransition(() => setPlan(response))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to generate the trip plan.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#d44b2c',
          borderRadius: 12,
          fontFamily: 'Space Grotesk, sans-serif',
          colorBgContainer: '#fffcf5',
        },
        components: {
          Calendar: {
            itemActiveBg: 'rgba(212, 75, 44, 0.1)',
          }
        }
      }}
    >
      <div className="min-h-screen bg-[#f8f3e8] text-[#132a38] font-sans p-4 md:p-8">
        <div className="max-w-7xl mx-auto space-y-6">
          
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-gradient-to-br from-[#fff8ea] to-[#fcf3dc] p-8 rounded-[28px] border border-[#132a38]/10 shadow-sm relative overflow-hidden">
              <div className="absolute inset-4 border border-dashed border-[#0a4f5f]/20 rounded-2xl pointer-events-none" />
              <p className="text-[#0a4f5f] text-xs font-bold uppercase tracking-widest mb-3 relative z-10">Truck HOS planner</p>
              <h1 className="font-serif text-4xl md:text-5xl font-bold leading-tight mb-4 text-[#132a38] relative z-10 max-w-lg">Plan the run. Surface the stops. Draw the logbook.</h1>
              <p className="text-gray-700 max-w-xl relative z-10">Enter the current location, pickup, dropoff, and cycle usage. The app generates a route, stop timeline, turn instructions, and filled daily paper logs.</p>
            </div>
            <div className="bg-gradient-to-br from-[#0a4f5f] to-[#122531] p-8 rounded-[28px] text-[#f6efe0] shadow-md flex flex-col justify-center">
              <p className="text-[#f6efe0]/70 text-xs font-bold uppercase tracking-widest mb-6">Assessment defaults</p>
              <div className="grid grid-cols-2 gap-6">
                <div><strong className="block text-3xl font-bold mb-1">70 / 8</strong><span className="text-sm text-[#f6efe0]/70">cycle</span></div>
                <div><strong className="block text-3xl font-bold mb-1">11h</strong><span className="text-sm text-[#f6efe0]/70">drive max</span></div>
                <div><strong className="block text-3xl font-bold mb-1">14h</strong><span className="text-sm text-[#f6efe0]/70">window</span></div>
                <div><strong className="block text-3xl font-bold mb-1">1k mi</strong><span className="text-sm text-[#f6efe0]/70">fuel cadence</span></div>
              </div>
            </div>
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5 bg-white/80 backdrop-blur-sm p-6 rounded-[24px] border border-[#132a38]/10 shadow-sm flex flex-col">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <p className="text-[#0a4f5f] text-[10px] font-bold uppercase tracking-widest mb-1">Trip inputs</p>
                  <h2 className="font-serif text-2xl font-bold text-[#132a38]">Build a trip plan</h2>
                </div>
                <button type="button" onClick={() => setFormData(demoRequest)} className="text-xs font-semibold px-4 py-2 rounded-full border border-[#132a38]/20 hover:bg-black/5 transition-colors">Load demo</button>
              </div>
              <form onSubmit={handleSubmit} className="space-y-4 flex-1 flex flex-col">
                <label className="block text-sm font-semibold text-[#132a38]">Current location
                  <input required value={formData.currentLocation} onChange={e => setFormData(c => ({...c, currentLocation: e.target.value}))} className="mt-1.5 w-full rounded-xl border border-[#132a38]/20 px-4 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-[#d44b2c]/50 transition-all" />
                </label>
                <label className="block text-sm font-semibold text-[#132a38]">Pickup location
                  <input required value={formData.pickupLocation} onChange={e => setFormData(c => ({...c, pickupLocation: e.target.value}))} className="mt-1.5 w-full rounded-xl border border-[#132a38]/20 px-4 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-[#d44b2c]/50 transition-all" />
                </label>
                <label className="block text-sm font-semibold text-[#132a38]">Dropoff location
                  <input required value={formData.dropoffLocation} onChange={e => setFormData(c => ({...c, dropoffLocation: e.target.value}))} className="mt-1.5 w-full rounded-xl border border-[#132a38]/20 px-4 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-[#d44b2c]/50 transition-all" />
                </label>
                <div className="grid grid-cols-2 gap-4">
                  <label className="block text-sm font-semibold text-[#132a38]">Cycle used
                    <input required type="number" min="0" max="70" step="0.25" value={formData.cycleUsedHours} onChange={e => setFormData(c => ({...c, cycleUsedHours: e.target.value}))} className="mt-1.5 w-full rounded-xl border border-[#132a38]/20 px-4 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-[#d44b2c]/50 transition-all" />
                  </label>
                  <label className="block text-sm font-semibold text-[#132a38]">Trip start
                    <DatePicker 
                      className="mt-1.5 w-full rounded-xl border border-[#132a38]/20 px-4 py-2 bg-white focus:outline-none transition-all"
                      showTime 
                      format="MM/DD/YYYY, hh:mm A" 
                      value={formData.startAt ? dayjs(formData.startAt) : null}
                      onChange={(date) => setFormData(c => ({...c, startAt: date ? date.toISOString() : ''}))}
                    />
                  </label>
                </div>
                <div className="pt-4 mt-auto">
                  <button type="submit" disabled={isLoading} className="w-full bg-gradient-to-r from-[#d44b2c] to-[#0a4f5f] text-[#fff6ea] font-bold py-3.5 px-6 rounded-full hover:opacity-90 transition-opacity disabled:opacity-60">
                    {isLoading ? 'Planning trip...' : 'Generate trip'}
                  </button>
                  {error && <p className="mt-4 text-sm text-red-800 bg-red-100 p-3 rounded-xl">{error}</p>}
                </div>
              </form>
            </div>

            <div className="lg:col-span-7 space-y-6 flex flex-col">
              <div className="bg-white/80 backdrop-blur-sm p-6 rounded-[24px] border border-[#132a38]/10 shadow-sm">
                <p className="text-[#0a4f5f] text-[10px] font-bold uppercase tracking-widest mb-1">Trip summary</p>
                <h2 className="font-serif text-2xl font-bold text-[#132a38] mb-6">Dispatch snapshot</h2>
                {deferredPlan ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="bg-[#fffcf5] border border-[#132a38]/10 rounded-xl p-4"><span className="text-xs text-gray-500 block mb-1">Miles</span><strong className="text-2xl font-bold text-[#132a38]">{deferredPlan.trip.totalDistanceMiles}</strong></div>
                      <div className="bg-[#fffcf5] border border-[#132a38]/10 rounded-xl p-4"><span className="text-xs text-gray-500 block mb-1">Drive hours</span><strong className="text-2xl font-bold text-[#132a38]">{deferredPlan.trip.totalDriveHours}</strong></div>
                      <div className="bg-[#fffcf5] border border-[#132a38]/10 rounded-xl p-4"><span className="text-xs text-gray-500 block mb-1">On-duty hours</span><strong className="text-2xl font-bold text-[#132a38]">{deferredPlan.trip.totalOnDutyHours}</strong></div>
                      <div className="bg-[#fffcf5] border border-[#132a38]/10 rounded-xl p-4"><span className="text-xs text-gray-500 block mb-1">Cycle end</span><strong className="text-2xl font-bold text-[#132a38]">{deferredPlan.trip.cycleHoursEnd}</strong></div>
                    </div>
                    <div className="bg-[#fffcf5] border border-[#132a38]/10 rounded-xl p-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div><span className="text-xs text-gray-500 block">Start</span><strong className="text-sm font-bold text-[#132a38]">{formatDate(deferredPlan.trip.startAt, deferredPlan.trip.timezone)}</strong></div>
                      <div><span className="text-xs text-gray-500 block">Finish</span><strong className="text-sm font-bold text-[#132a38]">{formatDate(deferredPlan.trip.endAt, deferredPlan.trip.timezone)}</strong></div>
                      <div><span className="text-xs text-gray-500 block">Logs</span><strong className="text-sm font-bold text-[#132a38]">{deferredPlan.trip.days} day(s)</strong></div>
                    </div>
                  </div>
                ) : (
                  <p className="text-gray-500 text-sm">Generate a trip to populate the route map, stop sequence, and daily logs.</p>
                )}
              </div>

              {deferredPlan && (
                <div className="bg-white/80 backdrop-blur-sm p-4 rounded-[24px] border border-[#132a38]/10 shadow-sm flex-1 min-h-[300px]">
                  <RouteMap route={deferredPlan.route} stops={deferredPlan.stops} />
                </div>
              )}
            </div>
          </section>

          {deferredPlan && (
            <>
              <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white/80 backdrop-blur-sm rounded-[24px] border border-[#132a38]/10 shadow-sm flex flex-col overflow-hidden h-[480px] pb-4">
                  <div className="p-6 border-b border-[#132a38]/5 shrink-0">
                    <p className="text-[#0a4f5f] text-[10px] font-bold uppercase tracking-widest mb-1">Stop timeline</p>
                    <h2 className="font-serif text-2xl font-bold text-[#132a38]">Duty-status changes</h2>
                  </div>
                  <div className="overflow-y-auto px-4 pt-4 space-y-3 flex-1 scrollbar-thin scrollbar-thumb-gray-300">
                    {deferredPlan.stops.map((stop) => (
                      <div key={`${stop.type}-${stop.arrivalAt}`} className="bg-[#fffcf5] border border-[#132a38]/10 rounded-xl p-4 flex items-center gap-4">
                        <div className={`w-28 shrink-0 text-center py-1.5 rounded-full text-xs font-bold uppercase tracking-widest ${['pickup', 'dropoff'].includes(stop.type) ? 'bg-[#0a4f5f]/10 text-[#0a4f5f]' : 'bg-[#d44b2c]/10 text-[#d44b2c]'}`}>
                          {stop.type}
                        </div>
                        <div className="flex-1 min-w-0">
                          <strong className="block text-[#132a38] truncate">{stop.label}</strong>
                          <p className="text-xs text-gray-500 truncate">{stop.locationName}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className="block text-sm text-[#132a38] font-medium">{formatDate(stop.arrivalAt, deferredPlan.trip.timezone)}</span>
                          <span className="block text-xs text-gray-500">{stopSummary(stop)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white/80 backdrop-blur-sm rounded-[24px] border border-[#132a38]/10 shadow-sm flex flex-col overflow-hidden h-[480px] pb-4">
                  <div className="p-6 border-b border-[#132a38]/5 shrink-0">
                    <p className="text-[#0a4f5f] text-[10px] font-bold uppercase tracking-widest mb-1">Route instructions</p>
                    <h2 className="font-serif text-2xl font-bold text-[#132a38]">Turn-by-turn highlights</h2>
                  </div>
                  <div className="overflow-y-auto px-4 pt-4 space-y-3 flex-1 scrollbar-thin scrollbar-thumb-gray-300">
                    {flattenedSteps.map((step) => (
                      <div key={step.key} className="bg-[#fffcf5] border border-[#132a38]/10 rounded-xl p-4 flex items-center justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <strong className="block text-[#132a38] text-sm">{step.instruction}</strong>
                          <p className="text-xs text-gray-500 truncate mt-0.5">{step.leg}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className="block text-sm font-semibold text-[#132a38]">{step.distanceMiles} mi</span>
                          <span className="block text-xs text-gray-500">{step.durationMinutes} min</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              <section className="bg-white/80 backdrop-blur-sm p-6 rounded-[24px] border border-[#132a38]/10 shadow-sm">
                <div className="mb-6">
                  <p className="text-[#0a4f5f] text-[10px] font-bold uppercase tracking-widest mb-1">Daily paper logs</p>
                  <h2 className="font-serif text-2xl font-bold text-[#132a38]">Rendered log sheets</h2>
                </div>
                <div className="flex overflow-x-auto gap-4 pb-4 snap-x snap-mandatory scrollbar-thin scrollbar-thumb-gray-300">
                  {deferredPlan.dailyLogs.map((log) => (
                    <DailyLogSheet key={log.date} log={log} />
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </ConfigProvider>
  )
}
