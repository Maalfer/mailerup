from django.test import SimpleTestCase

from apps.integrations.email_sender import html_to_text


class HtmlToTextTests(SimpleTestCase):
    def test_enlaces_y_entidades(self):
        t = html_to_text('<p>Hola&nbsp;<b>Ana</b></p><a href="https://x.es/c?a=1&amp;b=2">Ver</a>')
        self.assertIn("Hola", t)
        self.assertIn("Ver (https://x.es/c?a=1&b=2)", t)

    def test_preheader_oculto_no_aparece(self):
        t = html_to_text('<div style="display:none;max-height:0">RELLENO</div><p>Cuerpo</p>')
        self.assertNotIn("RELLENO", t)
        self.assertIn("Cuerpo", t)

    def test_vacio(self):
        self.assertEqual(html_to_text(""), "")
