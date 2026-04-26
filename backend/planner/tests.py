from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from django.test import Client, TestCase

from .clients import LocationPoint, RouteLeg, RouteModel, RouteStep, TripPlanningError
from .engine import TripPlanner


class FakeMapsClient:
    def __init__(self, route: RouteModel):
        self.route = route

    def geocode(self, query: str) -> LocationPoint:
        mapping = {
            "Current": LocationPoint("Current terminal", 32.7767, -96.7970),
            "Pickup": LocationPoint("Pickup yard", 35.4676, -97.5164),
            "Dropoff": LocationPoint("Dropoff yard", 39.7392, -104.9903),
        }
        return mapping[query]

    def reverse_geocode(self, lat: float, lng: float) -> str:
        return f"Generated stop {lat:.3f},{lng:.3f}"

    def build_route(self, waypoints: list[LocationPoint]) -> RouteModel:
        return self.route


class PlannerEngineTests(TestCase):
    def test_naive_start_time_is_interpreted_in_trip_timezone(self) -> None:
        planner = TripPlanner(FakeMapsClient(_short_route()))

        response = planner.plan_trip(
            current_location_query="Current",
            pickup_location_query="Pickup",
            dropoff_location_query="Dropoff",
            cycle_used_hours=12,
            start_at=datetime(2026, 4, 26, 8, 0),
        )

        self.assertTrue(response["trip"]["startAt"].startswith("2026-04-26T08:00:00-05:00"))

    def test_short_trip_stays_on_single_log(self) -> None:
        planner = TripPlanner(FakeMapsClient(_short_route()))

        response = planner.plan_trip(
            current_location_query="Current",
            pickup_location_query="Pickup",
            dropoff_location_query="Dropoff",
            cycle_used_hours=12,
            start_at=datetime(2026, 4, 26, 8, 0, tzinfo=timezone.utc),
        )

        stop_types = [stop["type"] for stop in response["stops"]]
        self.assertEqual(stop_types, ["current", "pickup", "dropoff"])
        self.assertEqual(response["trip"]["days"], 1)
        self.assertGreater(response["trip"]["totalOnDutyHours"], response["trip"]["totalDriveHours"])

    def test_long_trip_inserts_break_fuel_and_rest(self) -> None:
        planner = TripPlanner(FakeMapsClient(_long_route()))

        response = planner.plan_trip(
            current_location_query="Current",
            pickup_location_query="Pickup",
            dropoff_location_query="Dropoff",
            cycle_used_hours=8,
            start_at=datetime(2026, 4, 26, 6, 0, tzinfo=timezone.utc),
        )

        stop_types = [stop["type"] for stop in response["stops"]]
        self.assertIn("break", stop_types)
        self.assertIn("fuel", stop_types)
        self.assertIn("rest", stop_types)
        self.assertGreaterEqual(len(response["dailyLogs"]), 2)

    def test_cycle_restart_is_inserted_when_needed(self) -> None:
        planner = TripPlanner(FakeMapsClient(_short_route()))

        response = planner.plan_trip(
            current_location_query="Current",
            pickup_location_query="Pickup",
            dropoff_location_query="Dropoff",
            cycle_used_hours=69.5,
            start_at=datetime(2026, 4, 26, 8, 0, tzinfo=timezone.utc),
        )

        stop_types = [stop["type"] for stop in response["stops"]]
        self.assertIn("restart", stop_types)


class PlannerApiTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_healthcheck(self) -> None:
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_rejects_invalid_request_payload(self) -> None:
        response = self.client.post(
            "/api/trips/plan",
            data={"currentLocation": ""},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_surfaces_planning_errors(self) -> None:
        with patch("planner.views.build_trip_planner") as mock_planner:
            mock_planner.return_value.plan_trip.side_effect = TripPlanningError("Route failed")
            response = self.client.post(
                "/api/trips/plan",
                data={
                    "currentLocation": "Dallas, TX",
                    "pickupLocation": "Oklahoma City, OK",
                    "dropoffLocation": "Denver, CO",
                    "cycleUsedHours": 12,
                },
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"], "Route failed")


def _short_route() -> RouteModel:
    current = LocationPoint("Current terminal", 32.7767, -96.7970)
    pickup = LocationPoint("Pickup yard", 35.4676, -97.5164)
    dropoff = LocationPoint("Dropoff yard", 39.7392, -104.9903)
    return RouteModel(
        geometry=[
            (-96.7970, 32.7767),
            (-97.5164, 35.4676),
            (-104.9903, 39.7392),
        ],
        legs=[
            RouteLeg(
                start=current,
                end=pickup,
                distance_miles=200,
                duration_hours=3.75,
                steps=[RouteStep("Head north", 200, 225)],
            ),
            RouteLeg(
                start=pickup,
                end=dropoff,
                distance_miles=300,
                duration_hours=5.25,
                steps=[RouteStep("Continue west", 300, 315)],
            ),
        ],
        total_distance_miles=500,
        total_duration_hours=9.0,
    )


def _long_route() -> RouteModel:
    current = LocationPoint("Current terminal", 32.7767, -96.7970)
    pickup = LocationPoint("Pickup yard", 35.4676, -97.5164)
    dropoff = LocationPoint("Dropoff yard", 39.7392, -104.9903)
    return RouteModel(
        geometry=[
            (-96.7970, 32.7767),
            (-97.5164, 35.4676),
            (-101.8313, 35.2219),
            (-104.9903, 39.7392),
        ],
        legs=[
            RouteLeg(
                start=current,
                end=pickup,
                distance_miles=100,
                duration_hours=2.0,
                steps=[RouteStep("Drive to pickup", 100, 120)],
            ),
            RouteLeg(
                start=pickup,
                end=dropoff,
                distance_miles=1200,
                duration_hours=22.0,
                steps=[RouteStep("Drive to dropoff", 1200, 1320)],
            ),
        ],
        total_distance_miles=1300,
        total_duration_hours=24.0,
    )
