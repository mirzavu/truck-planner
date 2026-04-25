from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


METERS_PER_MILE = 1609.344
SECONDS_PER_HOUR = 3600


class TripPlanningError(Exception):
    pass


@dataclass(slots=True)
class LocationPoint:
    name: str
    lat: float
    lng: float


@dataclass(slots=True)
class RouteStep:
    instruction: str
    distance_miles: float
    duration_minutes: float


@dataclass(slots=True)
class RouteLeg:
    start: LocationPoint
    end: LocationPoint
    distance_miles: float
    duration_hours: float
    steps: list[RouteStep]


@dataclass(slots=True)
class RouteModel:
    geometry: list[tuple[float, float]]
    legs: list[RouteLeg]
    total_distance_miles: float
    total_duration_hours: float


class NominatimOsrmClient:
    def __init__(
        self,
        user_agent: str = "TruckHOSAssessment/1.0",
        nominatim_base_url: str = "https://nominatim.openstreetmap.org",
        osrm_base_url: str = "https://router.project-osrm.org",
        timeout: int = 20,
    ) -> None:
        self.user_agent = user_agent
        self.nominatim_base_url = nominatim_base_url.rstrip("/")
        self.osrm_base_url = osrm_base_url.rstrip("/")
        self.timeout = timeout
        self._reverse_cache: dict[tuple[float, float], str] = {}

    @property
    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent}

    def geocode(self, query: str) -> LocationPoint:
        try:
            response = requests.get(
                f"{self.nominatim_base_url}/search",
                params={"q": query, "format": "jsonv2", "limit": 1},
                headers=self._headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise TripPlanningError("Unable to geocode the requested location.") from exc

        if not data:
            raise TripPlanningError(f'No geocoding result found for "{query}".')

        top_result = data[0]
        return LocationPoint(
            name=top_result["display_name"],
            lat=float(top_result["lat"]),
            lng=float(top_result["lon"]),
        )

    def reverse_geocode(self, lat: float, lng: float) -> str:
        cache_key = (round(lat, 3), round(lng, 3))
        if cache_key in self._reverse_cache:
            return self._reverse_cache[cache_key]

        try:
            response = requests.get(
                f"{self.nominatim_base_url}/reverse",
                params={"lat": lat, "lon": lng, "format": "jsonv2"},
                headers=self._headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise TripPlanningError("Unable to reverse geocode a generated stop.") from exc

        label = data.get("display_name") or f"{lat:.3f}, {lng:.3f}"
        self._reverse_cache[cache_key] = label
        return label

    def build_route(self, waypoints: list[LocationPoint]) -> RouteModel:
        coordinate_string = ";".join(f"{point.lng},{point.lat}" for point in waypoints)
        try:
            response = requests.get(
                f"{self.osrm_base_url}/route/v1/driving/{coordinate_string}",
                params={
                    "alternatives": "false",
                    "steps": "true",
                    "geometries": "geojson",
                    "overview": "full",
                },
                headers=self._headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise TripPlanningError("Unable to build the route for this trip.") from exc

        routes = payload.get("routes") or []
        if not routes:
            raise TripPlanningError("No drivable route was found for the supplied trip.")

        route_data = routes[0]
        geometry = [
            (float(lng), float(lat))
            for lng, lat in route_data["geometry"]["coordinates"]
        ]

        legs: list[RouteLeg] = []
        for index, leg_data in enumerate(route_data["legs"]):
            start = waypoints[index]
            end = waypoints[index + 1]
            steps = [
                RouteStep(
                    instruction=self._format_step(step, end.name),
                    distance_miles=round(step.get("distance", 0) / METERS_PER_MILE, 2),
                    duration_minutes=round(step.get("duration", 0) / 60, 1),
                )
                for step in leg_data.get("steps", [])
                if step.get("distance", 0) > 0
            ]
            legs.append(
                RouteLeg(
                    start=start,
                    end=end,
                    distance_miles=leg_data["distance"] / METERS_PER_MILE,
                    duration_hours=leg_data["duration"] / SECONDS_PER_HOUR,
                    steps=steps,
                )
            )

        return RouteModel(
            geometry=geometry,
            legs=legs,
            total_distance_miles=route_data["distance"] / METERS_PER_MILE,
            total_duration_hours=route_data["duration"] / SECONDS_PER_HOUR,
        )

    def _format_step(self, step: dict[str, Any], destination_name: str) -> str:
        maneuver = step.get("maneuver", {})
        maneuver_type = maneuver.get("type", "continue")
        modifier = maneuver.get("modifier", "")
        road_name = step.get("name") or step.get("ref") or "the road ahead"

        if maneuver_type == "depart":
            heading = f" {modifier}" if modifier else ""
            return f"Depart and head{heading} on {road_name}".strip()
        if maneuver_type == "arrive":
            return f"Arrive near {destination_name}"
        if maneuver_type == "roundabout":
            return f"Take the roundabout toward {road_name}"
        if maneuver_type == "merge":
            heading = f" {modifier}" if modifier else ""
            return f"Merge{heading} onto {road_name}".strip()
        if maneuver_type == "fork":
            heading = f" {modifier}" if modifier else ""
            return f"Keep{heading} at the fork toward {road_name}".strip()
        if maneuver_type in {"turn", "continue", "new name"}:
            action = "Continue"
            if maneuver_type == "turn":
                action = "Turn"
            heading = f" {modifier}" if modifier else ""
            return f"{action}{heading} onto {road_name}".strip()
        if maneuver_type == "exit roundabout":
            return f"Exit the roundabout toward {road_name}"
        return f"{maneuver_type.replace('_', ' ').capitalize()} onto {road_name}"
