from django.contrib import admin
from django.urls import path, include
from apps.accounts.views import CookieTokenObtainView, CookieTokenRefreshView, CookieTokenLogoutView
from apps.analytics.views import (
    UnsubscribeView, TrackOpenView, TrackClickView,
    TrackAutoOpenView, TrackAutoClickView,
)
from apps.forms.views import SubscribeView, VerifySubscriptionView
from apps.campaigns.views import serve_resource
from apps.subscribers.views import PublicAddSubscriberView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Public endpoints embedded in emails (must be clean URLs)
    path('u/<str:token>/', UnsubscribeView.as_view(), name='public-unsubscribe'),
    path('o/<str:token>/', TrackOpenView.as_view(), name='track-open'),
    path('c/<str:token>/', TrackClickView.as_view(), name='track-click'),
    path('oa/<str:token>/', TrackAutoOpenView.as_view(), name='track-auto-open'),
    path('ca/<str:token>/', TrackAutoClickView.as_view(), name='track-auto-click'),
    # Public resource serving (files attached to campaigns)
    path('recurso/<str:name>/', serve_resource, name='serve-resource'),
    # Public form endpoints
    path('subscribe/<uuid:form_id>/', SubscribeView.as_view(), name='public-subscribe'),
    path('verify-subscription/<str:token>/', VerifySubscriptionView.as_view(), name='verify-subscription'),
    # Auth
    path('api/auth/token/', CookieTokenObtainView.as_view(), name='token_obtain'),
    path('api/auth/token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/logout/', CookieTokenLogoutView.as_view(), name='token_logout'),
    path('api/auth/', include('apps.accounts.urls')),
    # External API-key endpoint: crea suscriptores con Authorization: Bearer <key>
    path('api/public/subscribers/', PublicAddSubscriberView.as_view(), name='public-add-subscriber'),
    # Apps
    path('api/subscribers/', include('apps.subscribers.urls')),
    path('api/campaigns/', include('apps.campaigns.urls')),
    path('api/analytics/', include('apps.analytics.urls')),
    path('api/forms/', include('apps.forms.urls')),
    path('api/automations/', include('apps.automations.urls')),
]
