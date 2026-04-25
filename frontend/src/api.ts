import type { PlanRequest, TripPlanResponse } from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export async function fetchTripPlan(payload: PlanRequest): Promise<TripPlanResponse> {
  const response = await fetch(`${API_BASE_URL}/api/trips/plan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  const data = (await response.json()) as TripPlanResponse | { error?: string }
  if (!response.ok) {
    throw new Error(data && 'error' in data ? data.error || 'Failed to generate trip plan.' : 'Failed to generate trip plan.')
  }

  return data as TripPlanResponse
}
