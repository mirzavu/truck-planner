from django.urls import path

from .views import healthcheck_view, plan_trip_view


urlpatterns = [
    path("health/", healthcheck_view, name="healthcheck"),
    path("trips/plan", plan_trip_view, name="plan-trip"),
]
