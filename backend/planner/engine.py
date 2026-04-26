from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from math import atan2, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder

from .clients import LocationPoint, RouteModel, TripPlanningError


EPSILON = 1e-6
HOURS_PER_BREAK = 0.5
HOURS_PER_FUEL_STOP = 0.5
HOURS_PER_REST = 10.0
HOURS_PER_RESTART = 34.0
HOURS_PER_PICKUP_OR_DROPOFF = 1.0
MAX_DRIVING_BEFORE_BREAK = 8.0
MAX_DRIVING_PER_SHIFT = 11.0
MAX_SHIFT_WINDOW = 14.0
MAX_CYCLE_HOURS = 70.0
FUEL_INTERVAL_MILES = 1000.0


@dataclass(slots=True)
class DutySegment:
    status: str
    start_at: datetime
    end_at: datetime
    start_mile: float
    end_mile: float

    @property
    def duration_hours(self) -> float:
        return (self.end_at - self.start_at).total_seconds() / 3600

    def clip(self, clip_start: datetime, clip_end: datetime) -> "DutySegment | None":
        start_at = max(self.start_at, clip_start)
        end_at = min(self.end_at, clip_end)
        if start_at >= end_at:
            return None

        start_ratio = (
            (start_at - self.start_at).total_seconds()
            / (self.end_at - self.start_at).total_seconds()
            if self.end_at > self.start_at
            else 0
        )
        end_ratio = (
            (end_at - self.start_at).total_seconds()
            / (self.end_at - self.start_at).total_seconds()
            if self.end_at > self.start_at
            else 1
        )
        miles_delta = self.end_mile - self.start_mile
        return DutySegment(
            status=self.status,
            start_at=start_at,
            end_at=end_at,
            start_mile=self.start_mile + miles_delta * start_ratio,
            end_mile=self.start_mile + miles_delta * end_ratio,
        )


@dataclass(slots=True)
class StopEvent:
    stop_type: str
    label: str
    location_name: str
    lat: float
    lng: float
    arrival_at: datetime
    departure_at: datetime
    duty_status: str

    @property
    def duration_minutes(self) -> int:
        return int(round((self.departure_at - self.arrival_at).total_seconds() / 60))


@dataclass(slots=True)
class RouteInterpolator:
    geometry: list[tuple[float, float]]
    route_distance_miles: float
    _cumulative_miles: list[float] = field(init=False, repr=False)
    _geometry_total_miles: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._cumulative_miles = [0.0]
        for index in range(1, len(self.geometry)):
            prev_lng, prev_lat = self.geometry[index - 1]
            lng, lat = self.geometry[index]
            self._cumulative_miles.append(
                self._cumulative_miles[-1] + self._segment_miles(prev_lat, prev_lng, lat, lng)
            )
        self._geometry_total_miles = self._cumulative_miles[-1] if self._cumulative_miles else 0.0

    def point_for_mile(self, route_mile: float) -> tuple[float, float]:
        if not self.geometry:
            return (0.0, 0.0)
        if len(self.geometry) == 1 or self._geometry_total_miles <= EPSILON:
            lng, lat = self.geometry[0]
            return (lat, lng)

        scaled_mile = max(0.0, min(route_mile, self.route_distance_miles))
        scaled_mile = (scaled_mile / self.route_distance_miles) * self._geometry_total_miles

        for index in range(1, len(self._cumulative_miles)):
            if scaled_mile <= self._cumulative_miles[index]:
                segment_start = self._cumulative_miles[index - 1]
                segment_end = self._cumulative_miles[index]
                ratio = (
                    0.0
                    if segment_end - segment_start <= EPSILON
                    else (scaled_mile - segment_start) / (segment_end - segment_start)
                )
                start_lng, start_lat = self.geometry[index - 1]
                end_lng, end_lat = self.geometry[index]
                lat = start_lat + (end_lat - start_lat) * ratio
                lng = start_lng + (end_lng - start_lng) * ratio
                return (lat, lng)

        lng, lat = self.geometry[-1]
        return (lat, lng)

    @staticmethod
    def _segment_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        earth_radius_miles = 3958.7613
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return earth_radius_miles * c


class RouteProgress:
    def __init__(self, route: RouteModel):
        self.route = route
        self.leg_index = 0
        self.total_driven_miles = 0.0
        self.leg_remaining_miles = route.legs[0].distance_miles if route.legs else 0.0
        self.leg_remaining_hours = route.legs[0].duration_hours if route.legs else 0.0

    @property
    def has_active_leg(self) -> bool:
        return self.leg_index < len(self.route.legs)

    @property
    def current_leg(self):
        if not self.has_active_leg:
            return None
        return self.route.legs[self.leg_index]

    def hours_until_miles(self, miles_target: float) -> float:
        if miles_target <= EPSILON:
            return 0.0

        miles_left = miles_target
        hours = 0.0
        leg_index = self.leg_index
        remaining_miles = self.leg_remaining_miles
        remaining_hours = self.leg_remaining_hours

        while miles_left > EPSILON and leg_index < len(self.route.legs):
            if remaining_miles <= miles_left + EPSILON:
                hours += remaining_hours
                miles_left -= remaining_miles
                leg_index += 1
                if leg_index < len(self.route.legs):
                    remaining_miles = self.route.legs[leg_index].distance_miles
                    remaining_hours = self.route.legs[leg_index].duration_hours
            else:
                speed = remaining_miles / remaining_hours if remaining_hours > EPSILON else 0.0
                if speed <= EPSILON:
                    return float("inf")
                hours += miles_left / speed
                miles_left = 0.0

        if miles_left > EPSILON:
            return float("inf")
        return hours

    def advance(self, hours: float) -> float:
        remaining_hours = hours
        distance_driven = 0.0

        while remaining_hours > EPSILON and self.has_active_leg:
            if self.leg_remaining_hours <= remaining_hours + EPSILON:
                distance_driven += self.leg_remaining_miles
                remaining_hours -= self.leg_remaining_hours
                self.total_driven_miles += self.leg_remaining_miles
                self.leg_index += 1
                if self.has_active_leg:
                    self.leg_remaining_miles = self.current_leg.distance_miles
                    self.leg_remaining_hours = self.current_leg.duration_hours
                else:
                    self.leg_remaining_miles = 0.0
                    self.leg_remaining_hours = 0.0
                continue

            speed = self.leg_remaining_miles / self.leg_remaining_hours if self.leg_remaining_hours > EPSILON else 0.0
            miles_chunk = speed * remaining_hours
            distance_driven += miles_chunk
            self.total_driven_miles += miles_chunk
            self.leg_remaining_miles -= miles_chunk
            self.leg_remaining_hours -= remaining_hours
            remaining_hours = 0.0

        return distance_driven


class TripPlanner:
    def __init__(self, maps_client, timezone_finder: TimezoneFinder | None = None) -> None:
        self.maps_client = maps_client
        self.timezone_finder = timezone_finder or TimezoneFinder()

    def plan_trip(
        self,
        current_location_query: str,
        pickup_location_query: str,
        dropoff_location_query: str,
        cycle_used_hours: float,
        start_at: datetime,
    ) -> dict:
        current_location = self.maps_client.geocode(current_location_query)
        pickup_location = self.maps_client.geocode(pickup_location_query)
        dropoff_location = self.maps_client.geocode(dropoff_location_query)
        route = self.maps_client.build_route(
            [current_location, pickup_location, dropoff_location]
        )
        timezone_name = self._resolve_timezone(current_location)
        start_at = self._normalize_start_at(start_at, timezone_name)
        interpolator = RouteInterpolator(route.geometry, route.total_distance_miles)
        schedule = self._build_schedule(
            current_location=current_location,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            route=route,
            interpolator=interpolator,
            cycle_used_hours=cycle_used_hours,
            start_at=start_at,
        )

        trip_end = schedule["segments"][-1].end_at if schedule["segments"] else start_at
        total_on_duty_hours = sum(
            segment.duration_hours
            for segment in schedule["segments"]
            if segment.status in {"driving", "on_duty_not_driving"}
        )

        daily_logs = self._build_daily_logs(
            timezone_name=timezone_name,
            segments=schedule["segments"],
            stops=schedule["stops"],
            current_location=current_location,
            trip_start=start_at,
            trip_end=trip_end,
        )

        return {
            "trip": {
                "startAt": start_at.isoformat(),
                "endAt": trip_end.isoformat(),
                "timezone": timezone_name,
                "totalDistanceMiles": round(route.total_distance_miles, 1),
                "totalDriveHours": round(route.total_duration_hours, 2),
                "totalOnDutyHours": round(total_on_duty_hours, 2),
                "cycleHoursStart": round(cycle_used_hours, 2),
                "cycleHoursEnd": round(schedule["cycle_hours_end"], 2),
                "days": len(daily_logs),
            },
            "route": {
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lng, lat] for lng, lat in route.geometry],
                },
                "legs": [
                    {
                        "from": leg.start.name,
                        "to": leg.end.name,
                        "distanceMiles": round(leg.distance_miles, 1),
                        "durationHours": round(leg.duration_hours, 2),
                        "steps": [
                            {
                                "instruction": step.instruction,
                                "distanceMiles": step.distance_miles,
                                "durationMinutes": step.duration_minutes,
                            }
                            for step in leg.steps
                        ],
                    }
                    for leg in route.legs
                ],
            },
            "stops": [
                {
                    "type": stop.stop_type,
                    "label": stop.label,
                    "locationName": stop.location_name,
                    "lat": round(stop.lat, 6),
                    "lng": round(stop.lng, 6),
                    "arrivalAt": stop.arrival_at.isoformat(),
                    "departureAt": stop.departure_at.isoformat(),
                    "durationMinutes": stop.duration_minutes,
                    "dutyStatus": stop.duty_status,
                }
                for stop in schedule["stops"]
            ],
            "dailyLogs": daily_logs,
        }

    def _build_schedule(
        self,
        current_location: LocationPoint,
        pickup_location: LocationPoint,
        dropoff_location: LocationPoint,
        route: RouteModel,
        interpolator: RouteInterpolator,
        cycle_used_hours: float,
        start_at: datetime,
    ) -> dict:
        if not route.legs:
            raise TripPlanningError("Route did not contain any drivable legs.")

        progress = RouteProgress(route)
        now = start_at
        shift_start = start_at
        driving_since_break = 0.0
        driving_since_shift_reset = 0.0
        cycle_remaining = max(0.0, MAX_CYCLE_HOURS - cycle_used_hours)
        miles_since_fuel = 0.0
        segments: list[DutySegment] = []
        stops: list[StopEvent] = [
            StopEvent(
                stop_type="current",
                label="Current location",
                location_name=current_location.name,
                lat=current_location.lat,
                lng=current_location.lng,
                arrival_at=start_at,
                departure_at=start_at,
                duty_status="off_duty",
            )
        ]

        def add_stop(
            *,
            stop_type: str,
            label: str,
            duration_hours: float,
            duty_status: str,
            lat: float,
            lng: float,
            location_name: str,
        ) -> None:
            nonlocal now, shift_start, driving_since_break, driving_since_shift_reset, cycle_remaining

            arrival_at = now
            departure_at = now + timedelta(hours=duration_hours)
            segments.append(
                DutySegment(
                    status=duty_status,
                    start_at=arrival_at,
                    end_at=departure_at,
                    start_mile=progress.total_driven_miles,
                    end_mile=progress.total_driven_miles,
                )
            )
            stops.append(
                StopEvent(
                    stop_type=stop_type,
                    label=label,
                    location_name=location_name,
                    lat=lat,
                    lng=lng,
                    arrival_at=arrival_at,
                    departure_at=departure_at,
                    duty_status=duty_status,
                )
            )
            now = departure_at

            if duty_status == "on_duty_not_driving":
                cycle_remaining = max(0.0, cycle_remaining - duration_hours)
            if duration_hours >= HOURS_PER_BREAK:
                driving_since_break = 0.0
            if duty_status == "off_duty" and duration_hours >= HOURS_PER_REST:
                driving_since_shift_reset = 0.0
                driving_since_break = 0.0
                shift_start = now
            if stop_type == "restart":
                cycle_remaining = MAX_CYCLE_HOURS

        def current_position() -> tuple[float, float]:
            return interpolator.point_for_mile(progress.total_driven_miles)

        def stop_at_current_position(stop_type: str, label: str, duration_hours: float, duty_status: str) -> None:
            lat, lng = current_position()
            location_name = self.maps_client.reverse_geocode(lat, lng)
            add_stop(
                stop_type=stop_type,
                label=label,
                duration_hours=duration_hours,
                duty_status=duty_status,
                lat=lat,
                lng=lng,
                location_name=location_name,
            )

        def add_drive(hours_to_drive: float) -> None:
            nonlocal now, driving_since_break, driving_since_shift_reset, cycle_remaining, miles_since_fuel

            start_mile = progress.total_driven_miles
            distance_driven = progress.advance(hours_to_drive)
            end_mile = progress.total_driven_miles
            segments.append(
                DutySegment(
                    status="driving",
                    start_at=now,
                    end_at=now + timedelta(hours=hours_to_drive),
                    start_mile=start_mile,
                    end_mile=end_mile,
                )
            )
            now = now + timedelta(hours=hours_to_drive)
            driving_since_break += hours_to_drive
            driving_since_shift_reset += hours_to_drive
            cycle_remaining = max(0.0, cycle_remaining - hours_to_drive)
            miles_since_fuel += distance_driven

        for stop_type, terminal_location in (
            ("pickup", pickup_location),
            ("dropoff", dropoff_location),
        ):
            current_leg_index = progress.leg_index
            while progress.has_active_leg and progress.leg_index == current_leg_index:
                if cycle_remaining <= EPSILON:
                    stop_at_current_position(
                        stop_type="restart",
                        label="34-hour restart",
                        duration_hours=HOURS_PER_RESTART,
                        duty_status="off_duty",
                    )
                    continue

                window_remaining = MAX_SHIFT_WINDOW - ((now - shift_start).total_seconds() / 3600)
                break_remaining = MAX_DRIVING_BEFORE_BREAK - driving_since_break
                shift_drive_remaining = MAX_DRIVING_PER_SHIFT - driving_since_shift_reset
                fuel_remaining = FUEL_INTERVAL_MILES - miles_since_fuel if miles_since_fuel > EPSILON else FUEL_INTERVAL_MILES
                hours_until_fuel = progress.hours_until_miles(fuel_remaining)

                allowed_drive = min(
                    progress.leg_remaining_hours,
                    max(0.0, break_remaining),
                    max(0.0, shift_drive_remaining),
                    max(0.0, window_remaining),
                    cycle_remaining,
                    hours_until_fuel,
                )

                if allowed_drive > EPSILON:
                    add_drive(allowed_drive)
                    continue

                if hours_until_fuel <= EPSILON:
                    stop_at_current_position(
                        stop_type="fuel",
                        label="Fuel stop",
                        duration_hours=HOURS_PER_FUEL_STOP,
                        duty_status="on_duty_not_driving",
                    )
                    miles_since_fuel = 0.0
                    continue

                if break_remaining <= EPSILON:
                    stop_at_current_position(
                        stop_type="break",
                        label="30-minute break",
                        duration_hours=HOURS_PER_BREAK,
                        duty_status="off_duty",
                    )
                    continue

                if shift_drive_remaining <= EPSILON or window_remaining <= EPSILON:
                    stop_at_current_position(
                        stop_type="rest",
                        label="10-hour rest",
                        duration_hours=HOURS_PER_REST,
                        duty_status="off_duty",
                    )
                    continue

                if cycle_remaining <= EPSILON:
                    continue

                raise TripPlanningError("Unable to advance the trip schedule.")

            service_duration = HOURS_PER_PICKUP_OR_DROPOFF
            if cycle_remaining < service_duration:
                stop_at_current_position(
                    stop_type="restart",
                    label="34-hour restart",
                    duration_hours=HOURS_PER_RESTART,
                    duty_status="off_duty",
                )

            add_stop(
                stop_type=stop_type,
                label="Pickup service" if stop_type == "pickup" else "Dropoff service",
                duration_hours=service_duration,
                duty_status="on_duty_not_driving",
                lat=terminal_location.lat,
                lng=terminal_location.lng,
                location_name=terminal_location.name,
            )

        return {
            "segments": self._merge_adjacent_segments(segments),
            "stops": stops,
            "cycle_hours_end": MAX_CYCLE_HOURS - cycle_remaining,
        }

    def _build_daily_logs(
        self,
        *,
        timezone_name: str,
        segments: list[DutySegment],
        stops: list[StopEvent],
        current_location: LocationPoint,
        trip_start: datetime,
        trip_end: datetime,
    ) -> list[dict]:
        zone = ZoneInfo(timezone_name)
        local_start = trip_start.astimezone(zone)
        local_end = trip_end.astimezone(zone)
        day_start = datetime.combine(local_start.date(), time.min, tzinfo=zone)
        final_day_start = datetime.combine(local_end.date(), time.min, tzinfo=zone)
        logs: list[dict] = []

        while day_start <= final_day_start:
            day_end = day_start + timedelta(days=1)
            clipped_segments = [
                clipped
                for segment in segments
                if (clipped := segment.clip(day_start.astimezone(segment.start_at.tzinfo), day_end.astimezone(segment.start_at.tzinfo)))
            ]
            day_segments = self._fill_off_duty_gaps(
                day_start=day_start.astimezone(trip_start.tzinfo),
                day_end=day_end.astimezone(trip_start.tzinfo),
                segments=clipped_segments,
            )
            duty_totals = {
                "offDuty": 0.0,
                "sleeperBerth": 0.0,
                "driving": 0.0,
                "onDutyNotDriving": 0.0,
            }
            total_miles = 0.0
            for segment in day_segments:
                if segment.status == "off_duty":
                    duty_totals["offDuty"] += segment.duration_hours
                elif segment.status == "sleeper_berth":
                    duty_totals["sleeperBerth"] += segment.duration_hours
                elif segment.status == "driving":
                    duty_totals["driving"] += segment.duration_hours
                    total_miles += segment.end_mile - segment.start_mile
                else:
                    duty_totals["onDutyNotDriving"] += segment.duration_hours

            remarks = []
            for stop in stops:
                stop_local = stop.arrival_at.astimezone(zone)
                if day_start <= stop_local < day_end:
                    remarks.append(
                        {
                            "at": stop.arrival_at.isoformat(),
                            "label": f"{stop.label} - {stop.location_name}",
                        }
                    )

            logs.append(
                {
                    "date": day_start.date().isoformat(),
                    "timezone": timezone_name,
                    "totalMiles": round(total_miles, 1),
                    "dutyTotals": {
                        key: round(value, 2)
                        for key, value in duty_totals.items()
                    },
                    "segments": [
                        {
                            "status": segment.status,
                            "startAt": segment.start_at.isoformat(),
                            "endAt": segment.end_at.isoformat(),
                        }
                        for segment in day_segments
                    ],
                    "remarks": remarks,
                    "header": {
                        "carrierName": "Assessment Demo Carrier",
                        "mainOfficeAddress": current_location.name,
                        "homeTerminalAddress": current_location.name,
                        "truckNumber": "TRK-001",
                        "trailerNumber": "TRL-001",
                        "shippingDocument": "LOAD-DEMO",
                        "driverName": "Demo Driver",
                        "coDriverName": "",
                    },
                }
            )
            day_start = day_end

        return logs

    def _resolve_timezone(self, location: LocationPoint) -> str:
        timezone_name = self.timezone_finder.timezone_at(lat=location.lat, lng=location.lng)
        if timezone_name:
            return timezone_name
        timezone_name = self.timezone_finder.closest_timezone_at(lat=location.lat, lng=location.lng)
        return timezone_name or "UTC"

    def _normalize_start_at(self, start_at: datetime, timezone_name: str) -> datetime:
        zone = ZoneInfo(timezone_name)
        if start_at.tzinfo is None:
            return start_at.replace(tzinfo=zone)
        return start_at.astimezone(zone)

    def _fill_off_duty_gaps(
        self,
        *,
        day_start: datetime,
        day_end: datetime,
        segments: list[DutySegment],
    ) -> list[DutySegment]:
        if not segments:
            return [
                DutySegment(
                    status="off_duty",
                    start_at=day_start,
                    end_at=day_end,
                    start_mile=0.0,
                    end_mile=0.0,
                )
            ]

        filled: list[DutySegment] = []
        cursor = day_start
        for segment in sorted(segments, key=lambda item: item.start_at):
            if segment.start_at > cursor:
                filled.append(
                    DutySegment(
                        status="off_duty",
                        start_at=cursor,
                        end_at=segment.start_at,
                        start_mile=segment.start_mile,
                        end_mile=segment.start_mile,
                    )
                )
            filled.append(segment)
            cursor = segment.end_at
        if cursor < day_end:
            filled.append(
                DutySegment(
                    status="off_duty",
                    start_at=cursor,
                    end_at=day_end,
                    start_mile=filled[-1].end_mile,
                    end_mile=filled[-1].end_mile,
                )
            )
        return self._merge_adjacent_segments(filled)

    def _merge_adjacent_segments(self, segments: list[DutySegment]) -> list[DutySegment]:
        if not segments:
            return []

        merged = [segments[0]]
        for segment in segments[1:]:
            previous = merged[-1]
            if (
                previous.status == segment.status
                and abs((segment.start_at - previous.end_at).total_seconds()) < 1
            ):
                merged[-1] = DutySegment(
                    status=previous.status,
                    start_at=previous.start_at,
                    end_at=segment.end_at,
                    start_mile=previous.start_mile,
                    end_mile=segment.end_mile,
                )
                continue
            merged.append(segment)
        return merged
