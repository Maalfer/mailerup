from django.urls import path
from .views import (
    overview, campaign_analytics,
    automations_overview, automation_analytics,
    subscriptions_timeseries,
    deliverability, deliverability_recipients, deliverability_bounces, retry_failed_sends,
)

urlpatterns = [
    path("overview/", overview),
    path("campaign/<uuid:pk>/", campaign_analytics),
    path("automations/overview/", automations_overview),
    path("automation/<uuid:pk>/", automation_analytics),
    path("subscriptions/timeseries/", subscriptions_timeseries),
    path("deliverability/", deliverability),
    path("deliverability/campaign/<uuid:pk>/recipients/", deliverability_recipients),
    path("deliverability/bounces/", deliverability_bounces),
    path("retry-failed/", retry_failed_sends),
]
