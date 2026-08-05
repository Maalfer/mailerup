# HTTP → HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name newsletter.example.com;
    return 301 https://$host$request_uri;
}

# HTTPS — MailerUp NATIVO (Django uvicorn :8100 + SPA dist) con Cloudflare Origin Certificate
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name newsletter.example.com;

    # Cloudflare Origin Certificate (válido hasta 2041)
    ssl_certificate     /etc/nginx/ssl/example.com/origin.crt;
    ssl_certificate_key /etc/nginx/ssl/example.com/origin.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers off;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # SPA compilado (Vite)
    root /opt/mailerup/frontend/dist;
    index index.html;

    # Necesario para imports CSV/TXT y subida de recursos (adjuntos hasta 25 MB)
    client_max_body_size 25M;

    # API, admin, estáticos de Django, endpoints públicos de tracking y recursos.
    location ~ ^/(api|admin|static|u|o|c|oa|ca|subscribe|verify-subscription|recurso)(/|$) {
        proxy_pass         http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_set_header   Connection        "";
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    # Assets con hash de contenido (Vite): cache inmutable y, si el fichero no
    # existe, 404 en vez de caer al index.html. Devolver el index.html (HTML) para
    # una URL .js/.css hace que un CDN por delante (p.ej. Cloudflare) cachee HTML
    # para esa URL y rompa la SPA tras un despliegue.
    location /assets/ {
        try_files $uri =404;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA (routing en cliente)
    location / {
        try_files $uri $uri/ /index.html;
    }
}
