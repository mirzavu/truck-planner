import type { PlanRequest, TripPlanResponse } from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export async function fetchTripPlan(payload: PlanRequest): Promise<TripPlanResponse> {
  const response = await fetch(`${API_BASE_URL}/api/trips/plan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  const data = (await response.json().catch(() => null)) as TripPlanResponse | { error?: string, message?: string, traceback?: string } | null
  
  if (!response.ok) {
    console.error('API Error:', response.status, data)
    const message = data && 'message' in data ? data.message : (data && 'error' in data ? data.error : null)
    throw new Error(message || `Server error (${response.status}). Please check console for details.`)
  }

  return data as TripPlanResponse
}
