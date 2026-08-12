// Construye un documento HTML aislado que reproduce cómo se ve un correo al
// destinatario: cuerpo real sobre fondo claro, ancho ~600px centrado y
// responsive. Único punto de verdad para la vista previa: lo usan tanto el
// editor (antes de enviar) como la vista previa de correos ya enviados/en
// curso, para que ambas sean fieles entre sí y al envío real.
export function wrapEmailHtml(rawHtml) {
  const trimmed = (rawHtml || '').trim()
  // Si es un documento HTML completo (modo HTML del editor, o ya viene con su
  // propia maqueta), se muestra tal cual para respetar sus propios estilos.
  if (/<\s*(html|body|!doctype)\b/i.test(trimmed)) {
    return trimmed
  }
  const body = trimmed || '<p style="color:#9ca3af;margin:0">Sin contenido todavía.</p>'
  return `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  html,body{margin:0;padding:0;}
  body{background:#f1f3f5;color:#111827;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.6;}
  .mu-page{padding:24px 12px;}
  .mu-email{max-width:600px;margin:0 auto;background:#ffffff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);overflow:hidden;}
  .mu-inner{padding:24px;}
  .mu-inner img{max-width:100%;height:auto;}
  .mu-inner a{color:#4f46e5;}
  .mu-inner hr{border:none;border-top:1px solid #e5e7eb;margin:16px 0;}
</style>
</head>
<body>
  <div class="mu-page">
    <div class="mu-email">
      <div class="mu-inner">${body}</div>
    </div>
  </div>
</body>
</html>`
}
