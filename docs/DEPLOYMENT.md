# 🚀 Guía de Despliegue - 100toLoose

## 📊 Arquitectura Actual

Tu aplicación está compuesta por:
- **Backend**: FastAPI (Python) - Puerto 8000
- **Frontend**: React + Vite - Puerto 3000
- **Base de Datos**: PostgreSQL - Puerto 5432
- **Cache**: Redis - Puerto 6379
- **Reverse Proxy**: Nginx - Puerto 80
- **WebSockets**: Para actualizaciones en tiempo real
- **Docker Compose**: Todo containerizado

## 🎯 Requisitos de Despliegue

### Críticos:
- ✅ **WebSockets**: Necesita conexiones persistentes (no serverless puro)
- ✅ **Base de Datos Persistente**: PostgreSQL con volúmenes
- ✅ **Redis**: Para cache y WebSocket manager
- ✅ **SSL/HTTPS**: Para producción (certificados)
- ✅ **Variables de Entorno**: API keys, passwords, secrets
- ✅ **Logs Persistentes**: Volúmenes para logs

### Recomendados:
- 🔄 **Auto-restart**: Si el servicio cae
- 📊 **Monitoreo**: Health checks y alertas
- 🔒 **Backups**: Base de datos y configuraciones
- 📈 **Escalabilidad**: Posibilidad de escalar horizontalmente

---

## 🌐 Opciones de Despliegue Recomendadas

### 🥇 **OPCIÓN 1: Railway.app** (Recomendada para empezar)

**Ventajas:**
- ✅ Setup en 5 minutos
- ✅ Docker Compose nativo
- ✅ PostgreSQL y Redis incluidos
- ✅ SSL automático
- ✅ Variables de entorno fáciles
- ✅ $5/mes para empezar (muy económico)
- ✅ WebSockets funcionan perfectamente

**Pasos:**
1. Crear cuenta en [Railway.app](https://railway.app)
2. Conectar repositorio GitHub
3. Railway detecta `docker-compose.yml` automáticamente
4. Configurar variables de entorno
5. Deploy automático

**Costo:** ~$5-20/mes (depende del uso)

---

### 🥈 **OPCIÓN 2: DigitalOcean App Platform**

**Ventajas:**
- ✅ Similar a Railway pero más control
- ✅ PostgreSQL managed incluido
- ✅ SSL automático
- ✅ Auto-scaling
- ✅ Muy estable y confiable

**Pasos:**
1. Crear cuenta en [DigitalOcean](https://www.digitalocean.com)
2. App Platform → Create App
3. Conectar GitHub
4. Detectar Docker Compose
5. Configurar servicios y variables

**Costo:** ~$12-25/mes

---

### 🥉 **OPCIÓN 3: VPS + Docker Compose** (Más económico)

**Ventajas:**
- ✅ Control total
- ✅ Muy económico (~$5-10/mes)
- ✅ Aprendes mucho
- ✅ Sin límites de recursos (dentro del VPS)

**Desventajas:**
- ⚠️ Necesitas configurar SSL manualmente (Let's Encrypt)
- ⚠️ Mantenimiento manual
- ⚠️ Backups manuales

**Proveedores recomendados:**
1. **Hetzner** (Europa) - €4-10/mes
2. **Contabo** (Global) - $5-10/mes
3. **DigitalOcean Droplets** - $6-12/mes

**Pasos:**
```bash
# 1. Conectar por SSH
ssh root@tu-servidor

# 2. Instalar Docker y Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 3. Clonar repositorio
git clone https://github.com/Folkenciyo/100toloose.git
cd 100toloose

# 4. Configurar .env
cp .env.example .env
nano .env  # Editar variables

# 5. Levantar servicios
docker-compose up -d

# 6. Configurar SSL con Certbot
apt install certbot python3-certbot-nginx
certbot --nginx -d tu-dominio.com
```

---

### 🏆 **OPCIÓN 4: AWS/GCP/Azure** (Para producción seria)

**Ventajas:**
- ✅ Máxima escalabilidad
- ✅ Servicios managed (RDS, ElastiCache)
- ✅ Alta disponibilidad
- ✅ Monitoreo avanzado

**Desventajas:**
- ⚠️ Más complejo de configurar
- ⚠️ Más caro (~$50-200/mes mínimo)
- ⚠️ Curva de aprendizaje

**Recomendación:** Solo si esperas mucho tráfico o necesitas alta disponibilidad.

---

## 🔧 Configuración para Producción

### 1. Variables de Entorno (.env)

Crea un archivo `.env` en la raíz:

```env
# Database
DATABASE_URL=postgresql://usuario:password@db:5432/100toloose-db
POSTGRES_USER=tu_usuario_seguro
POSTGRES_PASSWORD=password_super_seguro_aqui
POSTGRES_DB=100toloose-db

# Security
SECRET_KEY=genera-una-clave-super-segura-aqui-minimo-32-caracteres

# Binance (opcional, se configuran en perfil)
BINANCE_API_KEY=
BINANCE_SECRET_KEY=
BINANCE_TESTNET=true

# Frontend
VITE_API_URL=https://tu-dominio.com
VITE_WS_URL=wss://tu-dominio.com/ws

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-app-password

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### 2. Generar SECRET_KEY segura

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Actualizar docker-compose.yml para producción

```yaml
# Cambiar:
- SECRET_KEY=${SECRET_KEY:-supersecretkey123changeinthisproduction}
# Por:
- SECRET_KEY=${SECRET_KEY}

# Cambiar puertos expuestos (solo Nginx):
nginx:
  ports:
    - "443:443"  # HTTPS
    - "80:80"    # HTTP (redirect a HTTPS)

# Agregar volúmenes para certificados SSL:
nginx:
  volumes:
    - ./nginx/ssl:/etc/nginx/ssl:ro
    - nginx_logs:/var/log/nginx
```

### 4. Configurar Nginx para HTTPS

Actualizar `nginx/nginx.conf`:

```nginx
server {
    listen 80;
    server_name tu-dominio.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tu-dominio.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # ... resto de configuración
}
```

---

## 📋 Checklist Pre-Deploy

- [ ] Cambiar `SECRET_KEY` por una generada aleatoriamente
- [ ] Cambiar passwords de PostgreSQL
- [ ] Configurar dominio y DNS
- [ ] Configurar SSL/HTTPS
- [ ] Revisar variables de entorno sensibles
- [ ] Configurar backups de base de datos
- [ ] Configurar monitoreo/logs
- [ ] Probar en entorno de staging primero
- [ ] Documentar credenciales de forma segura

---

## 🚨 Seguridad en Producción

### Crítico:
1. **Nunca** commitees `.env` o passwords al repositorio
2. Usa **secrets management** (Railway, DO App Spec, etc.)
3. Habilita **firewall** (solo puertos 80, 443, 22)
4. Usa **SSH keys** en lugar de passwords
5. Configura **fail2ban** para prevenir ataques
6. Habilita **rate limiting** en Nginx

### Recomendado:
- Usar **2FA** en todas las cuentas
- **Backups automáticos** diarios
- **Monitoreo** de recursos (CPU, RAM, disco)
- **Alertas** por email si algo falla

---

## 💰 Comparativa de Costos (Aproximado)

| Opción | Costo/Mes | Complejidad | Escalabilidad |
|--------|-----------|------------|---------------|
| **Railway** | $5-20 | ⭐ Fácil | Media |
| **DigitalOcean App** | $12-25 | ⭐⭐ Media | Alta |
| **VPS (Hetzner)** | $5-10 | ⭐⭐⭐ Difícil | Media |
| **AWS/GCP** | $50-200+ | ⭐⭐⭐⭐ Muy difícil | Muy Alta |

---

## 🎯 Recomendación Final

**Para empezar:** Railway.app
- Setup rápido
- Precio razonable
- Todo funciona out-of-the-box

**Para producción seria:** DigitalOcean App Platform
- Más control
- Mejor para escalar
- Muy estable

**Para aprender/ahorrar:** VPS (Hetzner/Contabo)
- Máximo control
- Muy económico
- Aprendes mucho

---

## 📚 Recursos Útiles

- [Railway Docs](https://docs.railway.app)
- [DigitalOcean App Platform](https://www.digitalocean.com/products/app-platform)
- [Docker Compose Production](https://docs.docker.com/compose/production/)
- [Let's Encrypt](https://letsencrypt.org/)
- [Nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)

---

## ❓ ¿Necesitas ayuda?

Si necesitas ayuda con el despliegue específico, puedo:
1. Crear scripts de deploy automatizados
2. Configurar CI/CD (GitHub Actions)
3. Optimizar docker-compose para producción
4. Configurar monitoreo y alertas

