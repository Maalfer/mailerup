from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import ApiKey

User = get_user_model()


ADMIN_ONLY_FIELDS = {
    "email_provider", "smtp_host", "smtp_port", "smtp_user", "smtp_password",
    "smtp_use_tls", "smtp_use_ssl", "brevo_api_key", "sendgrid_api_key",
    "footer_company", "footer_address", "footer_unsubscribe_text", "footer_button_label",
    "footer_forward_text", "footer_subscribe_text", "send_rate_per_hour",
}


def get_admin_user():
    """Return the first staff user, used as source of shared provider/footer config."""
    return User.objects.filter(is_staff=True).order_by("id").first()


# SMTP credentials live in the .env file (not the DB). Map model field -> env key.
SMTP_ENV_KEYS = {
    "smtp_host": "SMTP_HOST",
    "smtp_port": "SMTP_PORT",
    "smtp_user": "SMTP_USER",
    "smtp_use_tls": "SMTP_USE_TLS",
    "smtp_use_ssl": "SMTP_USE_SSL",
}


def _overlay_smtp_from_env(data, instance):
    """Show the SMTP values actually stored in .env (falling back to legacy DB
    values when a key isn't in .env yet, so existing installs keep displaying)."""
    from .env_file import read_env_file

    env = read_env_file()
    if "SMTP_HOST" in env:
        data["smtp_host"] = env["SMTP_HOST"]
    if "SMTP_USER" in env:
        data["smtp_user"] = env["SMTP_USER"]
    if env.get("SMTP_PORT"):
        try:
            data["smtp_port"] = int(env["SMTP_PORT"])
        except (TypeError, ValueError):
            pass
    if "SMTP_USE_TLS" in env:
        data["smtp_use_tls"] = env["SMTP_USE_TLS"] == "True"
    if "SMTP_USE_SSL" in env:
        data["smtp_use_ssl"] = env["SMTP_USE_SSL"] == "True"
    data["smtp_password_set"] = bool(env.get("SMTP_PASSWORD")) or bool(instance.smtp_password)
    return data


class UserSerializer(serializers.ModelSerializer):
    smtp_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    smtp_password_set = serializers.SerializerMethodField()
    # Las API keys son secretos: se aceptan al escribir pero NUNCA se devuelven
    # en claro al leer (igual que smtp_password). La UI muestra un flag *_set en
    # su lugar. Esto evita que un usuario no-admin reciba la clave del admin en
    # GET /api/auth/me/ a través del overlay de to_representation.
    brevo_api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    sendgrid_api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    brevo_api_key_set = serializers.SerializerMethodField()
    sendgrid_api_key_set = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "email", "username", "company", "timezone", "is_admin",
            "email_provider", "from_email", "from_name",
            "smtp_host", "smtp_port", "smtp_user",
            "smtp_password", "smtp_password_set",
            "smtp_use_tls", "smtp_use_ssl",
            "brevo_api_key", "brevo_api_key_set",
            "sendgrid_api_key", "sendgrid_api_key_set",
            "footer_company", "footer_address",
            "footer_unsubscribe_text", "footer_button_label",
            "footer_forward_text", "footer_subscribe_text",
            "send_rate_per_hour",
        )
        read_only_fields = ("id", "email", "is_admin")

    def get_is_admin(self, obj):
        return obj.is_staff

    @staticmethod
    def _no_newlines(value, field):
        # Estos valores acaban escritos en el .env: un salto de línea permitiría
        # inyectar otra variable de entorno (ver apps.accounts.env_file.update_env).
        if value and ("\n" in value or "\r" in value):
            raise serializers.ValidationError(
                f"El campo {field} no puede contener saltos de línea."
            )
        return value

    def validate_smtp_host(self, value):
        return self._no_newlines(value, "smtp_host")

    def validate_smtp_user(self, value):
        return self._no_newlines(value, "smtp_user")

    def get_smtp_password_set(self, obj):
        return bool(obj.smtp_password)

    def get_brevo_api_key_set(self, obj):
        return bool(obj.brevo_api_key)

    def get_sendgrid_api_key_set(self, obj):
        return bool(obj.sendgrid_api_key)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Non-admin users see the admin's provider/footer config (read-only for them).
        if not instance.is_staff:
            admin = get_admin_user()
            if admin and admin.id != instance.id:
                admin_data = UserSerializer(admin).data
                for f in ADMIN_ONLY_FIELDS:
                    # Las claves write_only no salen en admin_data; nunca se copian
                    # (es justo la fuga que estamos cerrando). Solo se hereda config
                    # no secreta (provider/footer/host/puerto…).
                    if f in admin_data:
                        data[f] = admin_data[f]
                data["smtp_password_set"] = admin_data.get("smtp_password_set", False)
                data["brevo_api_key_set"] = admin_data.get("brevo_api_key_set", False)
                data["sendgrid_api_key_set"] = admin_data.get("sendgrid_api_key_set", False)
                return data
        # Admin (or single-user install): surface the SMTP values from .env.
        return _overlay_smtp_from_env(data, instance)

    def update(self, instance, validated_data):
        from .env_file import read_env_file, update_env

        # Non-admins cannot modify provider/footer/SMTP fields.
        if not instance.is_staff:
            for f in list(validated_data.keys()):
                if f in ADMIN_ONLY_FIELDS:
                    validated_data.pop(f, None)
            validated_data.pop("smtp_password", None)

        # Las API keys son write_only: la UI no recibe el valor guardado, así que
        # al guardar ajustes sin retocarlas envía blanco. Tratar el blanco como
        # "mantener la clave existente" (igual que smtp_password) para no borrarla.
        for key_field in ("brevo_api_key", "sendgrid_api_key"):
            if key_field in validated_data and not validated_data[key_field]:
                validated_data.pop(key_field)

        new_smtp_user = None  # effective SMTP user, for from_email autosync below

        if instance.is_staff:
            # Route SMTP credentials to .env instead of the DB.
            env_updates = {}
            for field, env_key in SMTP_ENV_KEYS.items():
                if field in validated_data:
                    env_updates[env_key] = validated_data.pop(field)
            if "SMTP_USER" in env_updates:
                new_smtp_user = env_updates["SMTP_USER"]

            pw = validated_data.pop("smtp_password", None)
            current_env = read_env_file()
            if pw:
                env_updates["SMTP_PASSWORD"] = pw
            elif "SMTP_PASSWORD" not in current_env and instance.smtp_password:
                # First save after upgrade: migrate the legacy DB password to .env.
                env_updates["SMTP_PASSWORD"] = instance.smtp_password

            if env_updates:
                try:
                    update_env(env_updates)
                except OSError as exc:
                    raise serializers.ValidationError(
                        {"detail": f"No se pudo escribir el archivo .env: {exc}"}
                    )
                # Credentials now live in .env — don't keep the secret in the DB.
                if instance.smtp_password:
                    instance.smtp_password = ""
        else:
            validated_data.pop("smtp_password", None)

        # Si el remitente queda vacío pero hay smtp_user configurado, autosincronizar:
        # el SMTP solo acepta enviar como el usuario autenticado, así que ese es el From correcto.
        if new_smtp_user is None:
            new_smtp_user = read_env_file().get("SMTP_USER", instance.smtp_user)
        new_from_email = validated_data.get("from_email", instance.from_email)
        if not new_from_email and new_smtp_user and "@" in new_smtp_user:
            validated_data["from_email"] = new_smtp_user
        return super().update(instance, validated_data)


class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer for the user-management page (admin-only)."""
    password = serializers.CharField(write_only=True, required=False, min_length=8, allow_blank=True)
    is_admin = serializers.BooleanField(source="is_staff", required=False)

    class Meta:
        model = User
        fields = ("id", "email", "username", "company", "is_admin", "date_joined", "password")
        read_only_fields = ("id", "date_joined")

    def create(self, validated_data):
        pw = validated_data.pop("password", None) or "changeme123"
        is_staff = validated_data.pop("is_staff", False)
        user = User.objects.create_user(password=pw, **validated_data)
        if is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        return user

    def update(self, instance, validated_data):
        pw = validated_data.pop("password", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if pw:
            instance.set_password(pw)
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)


class ApiKeySerializer(serializers.ModelSerializer):
    """Read serializer for API keys. NEVER exposes `hashed_key` nor the raw key
    (the raw value is only returned once, injected by the create view)."""

    class Meta:
        model = ApiKey
        fields = ("id", "name", "prefix", "is_active", "created_at", "last_used_at")
        read_only_fields = fields
