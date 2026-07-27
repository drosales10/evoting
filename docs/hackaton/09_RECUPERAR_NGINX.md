# Recuperación rápida: evoting muestra album (nginx sobrescrito)

## Qué pasó

Al copiar `evoting.dennyrosales.com.conf` se perdió el bloque SSL que Certbot había
añadido. Nginx puede estar sirviendo otro `server` (p. ej. album) como default.

Los certificados **casi nunca se borran** con un `cp` de nginx. Siguen en:

```bash
sudo ls -la /etc/letsencrypt/live/
```

## 1) Diagnóstico (SSH al droplet)

```bash
# Qué sitios están activos
ls -la /etc/nginx/sites-enabled/

# Quién tiene default_server
sudo nginx -T 2>/dev/null | grep -E 'server_name|default_server|listen '

# ¿Sigue el cert de evoting?
sudo ls -la /etc/letsencrypt/live/evoting.dennyrosales.com/

# ¿Sigue el conf de album?
ls -la /etc/nginx/sites-available/ | grep -E 'album|evoting|default'
```

## 2) Restaurar SOLO evoting (no toques album)

En el repo del servidor:

```bash
cd /var/www/html/evoting
# trae el conf nuevo del repo (con SSL completo)
git pull   # o sube deploy/nginx/evoting.dennyrosales.com.conf

# backup de lo actual por si acaso
sudo cp /etc/nginx/sites-available/evoting.dennyrosales.com.conf \
  /etc/nginx/sites-available/evoting.dennyrosales.com.conf.bak.$(date +%s) || true

sudo cp deploy/nginx/evoting.dennyrosales.com.conf \
  /etc/nginx/sites-available/evoting.dennyrosales.com.conf

sudo ln -sf /etc/nginx/sites-available/evoting.dennyrosales.com.conf \
  /etc/nginx/sites-enabled/evoting.dennyrosales.com.conf
```

Si `ssl_dhparam` o `options-ssl-nginx.conf` no existen:

```bash
sudo ls /etc/letsencrypt/options-ssl-nginx.conf
sudo ls /etc/letsencrypt/ssl-dhparams.pem
```

Si faltan, vuelve a emitir/reparar con Certbot (no borra album):

```bash
sudo certbot --nginx -d evoting.dennyrosales.com --force-renewal
```

## 3) Asegurar que album sigue activo

```bash
# Si el archivo de album existe:
ls /etc/nginx/sites-available/album.dennyrosales.com*
sudo ln -sf /etc/nginx/sites-available/album.dennyrosales.com.conf \
  /etc/nginx/sites-enabled/album.dennyrosales.com.conf
```

Si **borraste** el conf de album y no hay backup:

```bash
# Buscar restos
sudo find /etc/nginx -name '*album*' 2>/dev/null
sudo ls /var/lib/dpkg/info/ 2>/dev/null | head
# Snapshots DigitalOcean / backups del panel
# Historial bash: history | grep album
```

Plantilla mínima de album (ajusta puerto/root a tu app real):

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name album.dennyrosales.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name album.dennyrosales.com;

    ssl_certificate     /etc/letsencrypt/live/album.dennyrosales.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/album.dennyrosales.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # AJUSTA ESTO a tu app album (ejemplos):
    # root /var/www/html/album/public;
    # o proxy_pass http://127.0.0.1:PUERTO_ALBUM;

    location / {
        proxy_pass http://127.0.0.1:3000;   # <-- cambia al puerto real de album
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 4) Probar y recargar

```bash
sudo nginx -t
sudo systemctl reload nginx

curl -k -H "Host: evoting.dennyrosales.com" https://127.0.0.1/health
curl -k -H "Host: album.dennyrosales.com" https://127.0.0.1/ -o /dev/null -w "%{http_code}\n"
```

Desde fuera:

- https://evoting.dennyrosales.com/ → eVoting  
- https://album.dennyrosales.com/ → album  

## 5) Si evoting sigue mostrando album

Casi seguro `default_server` apunta a album o falta el `server_name` de evoting:

```bash
sudo nginx -T 2>/dev/null | grep -n 'default_server'
```

Quita `default_server` de album (o déjalo solo en un default inocuo). Cada site debe tener su `server_name` exacto.

## Prevención

```bash
# Antes de tocar nginx:
sudo cp -a /etc/nginx/sites-available /root/nginx-sites-available-$(date +%F)
sudo cp -a /etc/nginx/sites-enabled /root/nginx-sites-enabled-$(date +%F)
```
