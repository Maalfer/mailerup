from django.utils import timezone
from rest_framework import authentication, exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Reads the JWT access token from the 'access' HttpOnly cookie instead of the Authorization header."""

    def authenticate(self, request):
        raw_token = request.COOKIES.get('access')
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Authenticates the external subscriber endpoint via `Authorization: Bearer <key>`.

    The raw key is SHA-256 hashed and matched against an active ApiKey. The key's
    owner becomes request.user (mapping to the shared admin owner). Returns None if
    no Bearer header is present so the request falls through to a normal 401."""

    keyword = "Bearer"

    def authenticate(self, request):
        auth = authentication.get_authorization_header(request).split()
        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None
        if len(auth) != 2:
            raise exceptions.AuthenticationFailed("Cabecera Authorization inválida.")

        from .models import ApiKey, hash_api_key

        try:
            raw = auth[1].decode()
        except UnicodeDecodeError:
            # Bytes no-UTF8 en la cabecera: 401, no un 500 sin controlar.
            raise exceptions.AuthenticationFailed("API key inválida.")
        hashed = hash_api_key(raw)
        key = ApiKey.objects.filter(hashed_key=hashed, is_active=True).select_related("user").first()
        if key is None:
            raise exceptions.AuthenticationFailed("API key inválida o revocada.")

        # update() avoids auto_now churn and races on the row.
        ApiKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return (key.user, key)

    def authenticate_header(self, request):
        return self.keyword
