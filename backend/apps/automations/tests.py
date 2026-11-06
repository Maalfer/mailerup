from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.analytics.views import UnsubscribeView, make_unsubscribe_token
from apps.subscribers.models import Subscriber, SubscriberList
from .models import Automation, AutomationEnrollment, AutomationSend, AutomationStep
from .tasks import process_automation_queue


class UnsubscribeStopsAutomationTests(TestCase):
    """Regresión: darse de baja debe frenar los pasos pendientes de una
    automatización, no solo los de campañas. Reproduce el escenario del
    reporte: enrolado -> baja real vía UnsubscribeView -> vence el delay del
    paso 2 -> process_automation_queue() no debe enviarlo."""

    def setUp(self):
        self.user = User.objects.create_user(email="admin@example.com", password="x")
        self.subscriber_list = SubscriberList.objects.create(user=self.user, name="Lista")
        self.subscriber = Subscriber.objects.create(
            list=self.subscriber_list, email="victima@example.com", status="active",
        )
        self.automation = Automation.objects.create(user=self.user, name="Bienvenida", is_active=True)
        AutomationStep.objects.create(
            automation=self.automation, order=1, subject="Paso 1",
            html_content="hola", delay_amount=0, delay_unit="minutes",
        )
        AutomationStep.objects.create(
            automation=self.automation, order=2, subject="Paso 2",
            html_content="hola otra vez", delay_amount=5, delay_unit="minutes",
        )
        self.enrollment = AutomationEnrollment.objects.create(
            automation=self.automation, subscriber=self.subscriber, status="active",
        )
        # Simula que el paso 1 ya se envió y que ha pasado tiempo suficiente
        # para que el paso 2 (delay=5 min) ya sea exigible.
        AutomationEnrollment.objects.filter(pk=self.enrollment.pk).update(
            enrolled_at=timezone.now() - timezone.timedelta(minutes=10)
        )
        self.enrollment.refresh_from_db()
        AutomationSend.objects.create(enrollment=self.enrollment, step=self.automation.steps.get(order=1))
        self.enrollment.last_step_sent = 1
        self.enrollment.save(update_fields=["last_step_sent"])

    def test_unsubscribe_cancels_the_enrollment(self):
        token = make_unsubscribe_token(self.subscriber.id)
        UnsubscribeView._apply_unsubscribe({"s": str(self.subscriber.id)})

        self.subscriber.refresh_from_db()
        self.enrollment.refresh_from_db()
        self.assertEqual(self.subscriber.status, "unsubscribed")
        self.assertEqual(self.enrollment.status, "cancelled")

    def test_queue_does_not_send_pending_step_after_unsubscribe(self):
        # Baja real por el mismo flujo público que procesa /u/<token>/.
        UnsubscribeView._apply_unsubscribe({"s": str(self.subscriber.id)})

        process_automation_queue()

        step2 = self.automation.steps.get(order=2)
        self.assertFalse(
            AutomationSend.objects.filter(enrollment=self.enrollment, step=step2).exists(),
            "El paso 2 se envió pese a que el suscriptor se había dado de baja",
        )

    def test_queue_still_sends_to_subscribers_who_did_not_unsubscribe(self):
        # Control: sin baja, el paso 2 sí debe enviarse (comportamiento normal).
        process_automation_queue()

        step2 = self.automation.steps.get(order=2)
        self.assertTrue(
            AutomationSend.objects.filter(enrollment=self.enrollment, step=step2).exists()
        )


class ResubscribeAndUnsubscribeHeaderTests(TestCase):
    """Regresión: (1) quien se da de baja y vuelve a confirmar el formulario debe recibir de nuevo
    el recurso; (2) los correos de automatización llevan la cabecera de baja en un clic."""

    def setUp(self):
        from apps.forms.models import SubscriptionForm
        self.user = User.objects.create_user(email="admin2@example.com", password="x")
        self.list = SubscriberList.objects.create(user=self.user, name="Lista")
        self.sub = Subscriber.objects.create(list=self.list, email="vuelve@example.com", status="active")
        self.form = SubscriptionForm.objects.create(user=self.user, name="f", title="t", target_list=self.list)
        self.auto = Automation.objects.create(user=self.user, name="Bienvenida", is_active=True, form=self.form)
        self.step = AutomationStep.objects.create(
            automation=self.auto, order=0, subject="Guía", html_content="<p>hola</p>", delay_amount=0, delay_unit="minutes",
        )
        self.enr = AutomationEnrollment.objects.create(
            automation=self.auto, subscriber=self.sub, status="completed", last_step_sent=0,
        )
        AutomationSend.objects.create(enrollment=self.enr, step=self.step)

    def _trigger(self, restart):
        from unittest import mock
        from .tasks import trigger_automation_for_subscriber, process_automation_queue
        with mock.patch.object(process_automation_queue, "delay") as d:
            trigger_automation_for_subscriber(str(self.sub.id), str(self.form.id), restart)
        self.enr.refresh_from_db()
        return d

    def test_vuelve_tras_baja_reinicia_la_secuencia(self):
        d = self._trigger(True)
        self.assertEqual(self.enr.status, "active")
        self.assertEqual(self.enr.last_step_sent, -1)
        self.assertFalse(AutomationSend.objects.filter(enrollment=self.enr).exists())
        d.assert_called_once()

    def test_sin_reactivacion_no_se_reinicia(self):
        d = self._trigger(False)
        self.assertEqual(self.enr.status, "completed")
        self.assertTrue(AutomationSend.objects.filter(enrollment=self.enr).exists())
        d.assert_not_called()

    def test_correo_de_automatizacion_lleva_baja_en_un_clic(self):
        from unittest import mock
        AutomationEnrollment.objects.filter(pk=self.enr.pk).update(status="active", last_step_sent=-1)
        AutomationSend.objects.filter(enrollment=self.enr).delete()
        sent = []

        class FakeSender:
            def send(self, **kw):
                sent.append(kw)
                return "id"

        with mock.patch("apps.integrations.email_sender.get_sender", return_value=FakeSender()):
            process_automation_queue()
        self.assertEqual(len(sent), 1)
        self.assertIn("/u/", sent[0].get("list_unsubscribe_url", ""))
