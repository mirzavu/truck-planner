export type DutyStatus =
  | 'off_duty'
  | 'sleeper_berth'
  | 'driving'
  | 'on_duty_not_driving'

export type RouteInstruction = {
  instruction: string
  distanceMiles: number
  durationMinutes: number
}

export type RouteLeg = {
  from: string
  to: string
  distanceMiles: number
  durationHours: number
  steps: RouteInstruction[]
}

export type Stop = {
  type: 'current' | 'pickup' | 'dropoff' | 'fuel' | 'break' | 'rest' | 'restart'
  label: string
  locationName: string
  lat: number
  lng: number
  arrivalAt: string
  departureAt: string
  durationMinutes: number
  dutyStatus: DutyStatus
}

export type DailyLog = {
  date: string
  timezone: string
  totalMiles: number
  dutyTotals: {
    offDuty: number
    sleeperBerth: number
    driving: number
    onDutyNotDriving: number
  }
  segments: Array<{
    status: DutyStatus
    startAt: string
    endAt: string
  }>
  remarks: Array<{
    at: string
    label: string
  }>
  header: {
    carrierName: string
    mainOfficeAddress: string
    homeTerminalAddress: string
    truckNumber: string
    trailerNumber: string
    shippingDocument: string
    driverName: string
    coDriverName: string
  }
}

export type TripPlanResponse = {
  trip: {
    startAt: string
    endAt: string
    timezone: string
    totalDistanceMiles: number
    totalDriveHours: number
    totalOnDutyHours: number
    cycleHoursStart: number
    cycleHoursEnd: number
    days: number
  }
  route: {
    geometry: {
      type: 'LineString'
      coordinates: [number, number][]
    }
    legs: RouteLeg[]
  }
  stops: Stop[]
  dailyLogs: DailyLog[]
}

export type PlanRequest = {
  currentLocation: string
  pickupLocation: string
  dropoffLocation: string
  cycleUsedHours: number
  startAt?: string
}
