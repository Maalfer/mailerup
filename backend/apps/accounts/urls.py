from django.urls import path
from .views import (
    MeView, ChangePasswordView, email_providers, test_email,
    AdminUserListView, AdminUserDetailView, db_export,
    ApiKeyListCreateView, ApiKeyDetailView,
)

urlpatterns = [
    # No hay registro público: las cuentas las crea solo el admin vía /users/
    # (AdminUserListView, IsAdminUser) o `manage.py createsuperuser` para el bootstrap.
    path("me/", MeView.as_view()),
    path("change-password/", ChangePasswordView.as_view()),
    path("email-providers/", email_providers),
    path("test-email/", test_email),
    # admin-only
    path("users/", AdminUserListView.as_view()),
    path("users/<int:pk>/", AdminUserDetailView.as_view()),
    path("api-keys/", ApiKeyListCreateView.as_view()),
    path("api-keys/<uuid:pk>/", ApiKeyDetailView.as_view()),
    path("db-export/", db_export),
]
