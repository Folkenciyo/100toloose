# 🚀 Guía de Despliegue con NO-IP (IP Dinámica)

## 📋 Requisitos Previos

- ✅ Servidor (laptop) con Docker y Docker Compose instalados
- ✅ Router con acceso de administrador
- ✅ Cuenta en [NO-IP.com](https://www.noip.com) (gratis)
- ✅ Dominio NO-IP configurado (ej: `tu-app.ddns.net`)

---

## 🔧 Paso 1: Configurar NO-IP

### 1.1 Crear cuenta en NO-IP

1. Ve a [https://www.noip.com/sign-up](https://www.noip.com/sign-up)
2. Crea una cuenta gratuita
3. **Importante**: La cuenta gratuita requiere confirmar el host cada 30 días (recibirás email)

### 1.2 Crear un hostname

1. Inicia sesión en NO-IP
2. Ve a **Dynamic DNS** → **Hostnames**
3. Click en **"Create Hostname"**
4. Configura:
   - **Hostname**: `tu-app` (o el nombre que quieras)
   - **Domain**: Selecciona uno disponible (ej: `ddns.net`, `myddns.me`)
   - **IP Address**: Déjalo vacío (se actualizará automáticamente)
   - **Record Type**: `A Record`
5. Click en **"Create Hostname"**

**Resultado**: Tendrás algo como `tu-app.ddns.net`

---

## 📥 Paso 2: Instalar Cliente DUC (Dynamic Update Client)

El cliente DUC actualiza automáticamente tu IP en NO-IP cuando cambia.

### 2.1 Para Linux (Ubuntu/Debian)

```bash
# 1. Descargar el cliente DUC
cd /tmp
wget https://www.noip.com/client/linux/noip-duc-linux.tar.gz

# 2. Extraer
tar -xzf noip-duc-linux.tar.gz
cd noip-2.1.9-1/

# 3. Compilar e instalar
make
sudo make install

# 4. Configurar (te pedirá usuario y contraseña de NO-IP)
sudo /usr/local/bin/noip2 -C

# 5. Iniciar el servicio
sudo /usr/local/bin/noip2

# 6. Verificar que está corriendo
sudo /usr/local/bin/noip2 -S
```

### 2.2 Configurar como servicio systemd (auto-inicio)

Crea el archivo de servicio:

```bash
sudo nano /etc/systemd/system/noip.service
```

Contenido:

```ini
[Unit]
Description=NO-IP Dynamic DNS Update Client
After=network.target

[Service]
Type=forking
ExecStart=/usr/local/bin/noip2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activar el servicio:

```bash
sudo systemctl daemon-reload
sudo systemctl enable noip.service
sudo systemctl start noip.service
sudo systemctl status noip.service
```

### 2.3 Alternativa: Usar script Python (más simple)

Si prefieres algo más simple, crea un script Python:

```bash
sudo nano /usr/local/bin/noip-update.py
```

Contenido:

```python
#!/usr/bin/env python3
import requests
import time

# Configuración
NOIP_USERNAME = "tu-email@ejemplo.com"
NOIP_PASSWORD = "tu-password"
NOIP_HOSTNAME = "tu-app.ddns.net"

def update_noip():
    try:
        # Obtener IP actual
        current_ip = requests.get('https://api.ipify.org').text
        
        # Actualizar NO-IP
        url = f"https://dynupdate.no-ip.com/nic/update"
        params = {
            'hostname': NOIP_HOSTNAME,
            'myip': current_ip
        }
        auth = (NOIP_USERNAME, NOIP_PASSWORD)
        
        response = requests.get(url, params=params, auth=auth)
        
        if 'good' in response.text or 'nochg' in response.text:
            print(f"✅ NO-IP actualizado: {current_ip}")
        else:
            print(f"❌ Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Error actualizando NO-IP: {e}")

if __name__ == "__main__":
    update_noip()
```

Hacer ejecutable y crear cron job:

```bash
sudo chmod +x /usr/local/bin/noip-update.py
sudo chmod 600 /usr/local/bin/noip-update.py  # Solo root puede leer

# Agregar a crontab (actualiza cada 5 minutos)
sudo crontab -e
# Agregar esta línea:
*/5 * * * * /usr/bin/python3 /usr/local/bin/noip-update.py >> /var/log/noip-update.log 2>&1
```

---

## 🔌 Paso 3: Configurar Port Forwarding en el Router

Necesitas redirigir los puertos desde tu router a tu servidor (laptop).

### 3.1 Obtener IP local del servidor

En tu servidor (laptop):

```bash
# Linux
ip addr show | grep "inet " | grep -v 127.0.0.1

# O más simple
hostname -I
```

Anota la IP local (ej: `192.168.1.100`)

### 3.2 Configurar Router

1. Accede a tu router (normalmente `192.168.1.1` o `192.168.0.1`)
2. Busca **"Port Forwarding"** o **"Virtual Server"** o **"NAT"**
3. Crea las siguientes reglas:

| Puerto Externo | Puerto Interno | IP Interna | Protocolo | Descripción |
|----------------|----------------|------------|-----------|-------------|
| 80 | 80 | 192.168.1.100 | TCP | HTTP |
| 443 | 443 | 192.168.1.100 | TCP | HTTPS |
| 8000 | 8000 | 192.168.1.100 | TCP | Backend (opcional, solo si quieres acceso directo) |

4. Guarda la configuración

**Nota**: Si tu ISP bloquea puertos 80/443, usa puertos alternativos (ej: 8080, 8443) y configura Nginx para escuchar en esos puertos.

---

## 🐳 Paso 4: Configurar la Aplicación

### 4.1 Actualizar docker-compose.yml

Modifica el archivo `docker-compose.yml` para usar tu dominio NO-IP:

```yaml
services:
  nginx:
    # ... configuración existente ...
    ports:
      - "80:80"
      - "443:443"  # Si configuras SSL
    # ... resto de configuración ...

  backend:
    environment:
      - DATABASE_URL=postgresql://Folkencillo:7887Folkencillo!@db:5432/100toloose-db
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}  # Cambiar en producción
      # ... resto de variables ...
```

### 4.2 Actualizar Nginx para tu dominio

Modifica `nginx/nginx.conf`:

```nginx
server {
    listen 80;
    server_name tu-app.ddns.net;  # ← Tu dominio NO-IP aquí

    # ... resto de configuración ...
}
```

### 4.3 Actualizar variables de entorno del frontend

Crea/actualiza `.env` en la raíz:

```env
# Frontend
VITE_API_URL=http://tu-app.ddns.net
VITE_WS_URL=ws://tu-app.ddns.net/ws
```

O si usas HTTPS:

```env
VITE_API_URL=https://tu-app.ddns.net
VITE_WS_URL=wss://tu-app.ddns.net/ws
```

### 4.4 Reconstruir frontend con nuevas variables

```bash
cd frontend
docker-compose down
docker-compose build --no-cache frontend
docker-compose up -d
```

---

## 🔒 Paso 5: Configurar SSL/HTTPS (Opcional pero Recomendado)

### 5.1 Usar Let's Encrypt con Certbot

```bash
# Instalar Certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx

# Obtener certificado (ajusta el dominio)
sudo certbot --nginx -d tu-app.ddns.net

# Renovación automática (ya viene configurada)
sudo certbot renew --dry-run
```

### 5.2 Actualizar Nginx para HTTPS

Certbot modificará automáticamente tu `nginx.conf`, pero verifica que tenga:

```nginx
server {
    listen 80;
    server_name tu-app.ddns.net;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tu-app.ddns.net;

    ssl_certificate /etc/letsencrypt/live/tu-app.ddns.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tu-app.ddns.net/privkey.pem;

    # ... resto de configuración ...
}
```

### 5.3 Montar certificados en Docker

Actualiza `docker-compose.yml`:

```yaml
nginx:
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - /etc/letsencrypt:/etc/letsencrypt:ro  # ← Montar certificados
    - nginx_logs:/var/log/nginx
```

---

## ✅ Paso 6: Verificar que Todo Funciona

### 6.1 Verificar NO-IP

```bash
# Verificar que el dominio apunta a tu IP actual
nslookup tu-app.ddns.net

# O
dig tu-app.ddns.net
```

### 6.2 Verificar Port Forwarding

Desde fuera de tu red (móvil con datos, por ejemplo):

```bash
# Probar HTTP
curl http://tu-app.ddns.net/health

# Probar HTTPS (si configuraste SSL)
curl https://tu-app.ddns.net/health
```

### 6.3 Verificar que el cliente DUC está funcionando

```bash
# Si usaste el cliente oficial
sudo /usr/local/bin/noip2 -S

# Si usaste el script Python, revisa logs
tail -f /var/log/noip-update.log
```

---

## 🔄 Paso 7: Mantenimiento

### 7.1 Renovar hostname NO-IP (cada 30 días)

La cuenta gratuita de NO-IP requiere confirmar el hostname cada 30 días:

1. Recibirás un email de NO-IP
2. Click en el enlace de confirmación
3. O ve a NO-IP → Dynamic DNS → Hostnames → Click en "Confirm"

**Alternativa**: Actualiza a cuenta "Enhanced" ($2.50/mes) para evitar esto.

### 7.2 Monitorear cambios de IP

Crea un script de monitoreo:

```bash
sudo nano /usr/local/bin/check-ip-change.sh
```

Contenido:

```bash
#!/bin/bash
CURRENT_IP=$(curl -s https://api.ipify.org)
STORED_IP=$(cat /tmp/last-ip.txt 2>/dev/null || echo "")

if [ "$CURRENT_IP" != "$STORED_IP" ]; then
    echo "$(date): IP cambió de $STORED_IP a $CURRENT_IP" >> /var/log/ip-changes.log
    echo "$CURRENT_IP" > /tmp/last-ip.txt
    # Forzar actualización NO-IP
    sudo /usr/local/bin/noip2 -i  # Si usas cliente oficial
    # O ejecutar tu script Python
fi
```

Agregar a crontab (cada 5 minutos):

```bash
sudo crontab -e
# Agregar:
*/5 * * * * /usr/local/bin/check-ip-change.sh
```

---

## 🐛 Solución de Problemas

### Problema: El dominio no resuelve

**Solución:**
```bash
# Verificar que NO-IP tiene tu IP actual
nslookup tu-app.ddns.net

# Si no coincide, forzar actualización
sudo /usr/local/bin/noip2 -i
```

### Problema: No puedo acceder desde fuera

**Solución:**
1. Verificar port forwarding en router
2. Verificar firewall del servidor:
   ```bash
   sudo ufw status
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```
3. Verificar que Docker está escuchando:
   ```bash
   docker ps
   docker logs 100toloose-nginx
   ```

### Problema: ISP bloquea puertos 80/443

**Solución:**
1. Usar puertos alternativos (8080, 8443)
2. Actualizar port forwarding en router
3. Acceder como: `http://tu-app.ddns.net:8080`
4. O usar Cloudflare Tunnel (no requiere abrir puertos)

### Problema: Certificado SSL no funciona

**Solución:**
```bash
# Verificar certificado
sudo certbot certificates

# Renovar manualmente
sudo certbot renew

# Verificar que Nginx puede leer los certificados
sudo ls -la /etc/letsencrypt/live/tu-app.ddns.net/
```

---

## 📝 Checklist Final

- [ ] Cuenta NO-IP creada
- [ ] Hostname NO-IP configurado
- [ ] Cliente DUC instalado y funcionando
- [ ] Port forwarding configurado en router
- [ ] Firewall del servidor configurado
- [ ] Nginx configurado con dominio NO-IP
- [ ] Variables de entorno actualizadas
- [ ] SSL configurado (opcional pero recomendado)
- [ ] Acceso desde fuera verificado
- [ ] Script de monitoreo configurado

---

## 💡 Tips Adicionales

1. **IP estática local**: Configura IP estática en tu laptop dentro de la red local para que el port forwarding siempre funcione
2. **Wake on LAN**: Si el laptop se apaga, configura Wake on LAN para encenderlo remotamente
3. **Monitoreo**: Usa UptimeRobot o similar para monitorear que tu servidor esté online
4. **Backups**: Configura backups automáticos de la base de datos
5. **Notificaciones**: Configura alertas si el servidor cae o la IP cambia

---

## 🔗 Enlaces Útiles

- [NO-IP Dashboard](https://www.noip.com/members/dns/)
- [NO-IP DUC Download](https://www.noip.com/download)
- [Let's Encrypt](https://letsencrypt.org/)
- [Port Forwarding Guide](https://portforward.com/)

---

¡Listo! Tu aplicación debería estar accesible desde `http://tu-app.ddns.net` (o `https://` si configuraste SSL).

