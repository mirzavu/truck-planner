from __future__ import annotations

import json
from datetime import datetime, timezone

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .clients import NominatimOsrmClient, TripPlanningError
from .engine import TripPlanner


def build_trip_planner() -> TripPlanner:
    return TripPlanner(NominatimOsrmClient())


def healthcheck_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"ok": True})


@csrf_exempt
def plan_trip_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    try:
        current_location = _require_string(payload, "currentLocation")
        pickup_location = _require_string(payload, "pickupLocation")
        dropoff_location = _require_string(payload, "dropoffLocation")
        cycle_used_hours = _require_number(payload, "cycleUsedHours")
        start_at = _parse_start_at(payload.get("startAt"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        planner = build_trip_planner()
        response_payload = planner.plan_trip(
            current_location_query=current_location,
            pickup_location_query=pickup_location,
            dropoff_location_query=dropoff_location,
            cycle_used_hours=cycle_used_hours,
            start_at=start_at,
        )
        return JsonResponse(response_payload)
    except TripPlanningError as exc:
        return JsonResponse({"error": str(exc)}, status=502)


def _require_string(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required.")
    return value.strip()


def _require_number(payload: dict, key: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number.")
    if value < 0 or value > 70:
        raise ValueError(f"{key} must be between 0 and 70.")
    return float(value)


def _parse_start_at(raw_value: str | None) -> datetime:
    if not raw_value:
        return datetime.now(timezone.utc)

    normalized = raw_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("startAt must be a valid ISO datetime.") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
