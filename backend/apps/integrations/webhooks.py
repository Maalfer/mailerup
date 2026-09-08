import hmac
from django.conf import settings
from django.http import Http404
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class PurchaseWebhookView(APIView):
    """Webhook genérico de compra (no atado a Stripe ni a ninguna plataforma
    concreta): cualquier sistema externo (Stripe, Gumroad, un CSV manual vía
    Zapier/n8n...) que sepa el secreto compartido puede marcar un email como
    `lifecycle_stage=cliente`, para poder excluirlo de campañas de venta.

    POST /api/webhooks/purchase/
    Header: X-Webhook-Secret: <PURCHASE_WEBHOOK_SECRET>
    Body:   {"email": "..."}   (cualquier otro campo se ignora por ahora)

    Sin autenticación DRF: el "auth" es la comparación de secreto en tiempo
    constante, igual de simple que el resto de secretos comparados en este
    proyecto (no hace falta hmac de firma, es un secreto compartido plano).
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "purchase_webhook"

    def post(self, request):
        secret = settings.PURCHASE_WEBHOOK_SECRET
        if not secret:
            # Feature desactivada por defecto: no revelar que la ruta existe.
            raise Http404
        provided = request.headers.get("X-Webhook-Secret", "")
        if not hmac.compare_digest(provided, secret):
            return Response({"detail": "secreto inválido"}, status=401)

        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response({"detail": "email requerido"}, status=400)

        from apps.subscribers.models import Subscriber
        updated = Subscriber.objects.filter(email=email).update(
            lifecycle_stage="cliente", last_purchase_at=timezone.now()
        )
        return Response({"matched": updated > 0, "updated": updated})
