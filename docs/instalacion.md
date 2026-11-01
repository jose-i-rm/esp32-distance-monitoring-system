# Instalación y ejecución local

## Requisitos

| Herramienta | Versión | Uso |
|-------------|---------|-----|
| Python | 3.12+ | Backend FastAPI |
| PostgreSQL | 14+ (o Docker) | Base de datos |
| Docker Desktop | Opcional | Levantar PostgreSQL + API con un comando |
| Navegador moderno | — | Dashboard |
| Git | — | Control de versiones |

## Opción A — Docker Compose (recomendada)

```bash
cd deployment/docker
cp .env.example .env            # Ajuste DEVICE_API_KEY
docker compose up --build
```

| Servicio | URL |
|----------|-----|
| API + Swagger | http://localhost:8000/docs |
| Dashboard | http://localhost:5500 |
| PostgreSQL | localhost:5432 (`esp32` / `esp32`) |

Las migraciones Alembic se aplican automáticamente al iniciar el contenedor de la API.

## Opción B — Entorno Python local

### 1. Base de datos

```bash
# Con PostgreSQL instalado localmente
psql -U postgres -c "CREATE USER esp32 WITH PASSWORD 'esp32';"
psql -U postgres -c "CREATE DATABASE esp32_monitoring OWNER esp32;"
```

> Para pruebas rápidas sin PostgreSQL use `DATABASE_URL=sqlite:///./dev.db` y `AUTO_CREATE_TABLES=true`.

### 2. Backend

**Windows (PowerShell):**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Linux / macOS:**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> `--host 0.0.0.0` permite que la ESP32-CAM, conectada a la misma red WiFi, alcance la API en `http://<IP_DEL_PC>:8000`. Puede requerir permitir el puerto 8000 en el firewall de Windows.

### 3. Frontend

```bash
cd frontend
python -m http.server 5500
```

Abra http://localhost:5500. Por defecto el dashboard apunta a `http://localhost:8000` (editable desde **⚙ Configuración**).

### 4. Enviar datos

- **Con la ESP32-CAM:** configure la URL `http://<IP_DEL_PC>:8000/api/v1/measurements` y la API Key en el firmware (ver [../firmware/README.md](../firmware/README.md)).
- **Sin hardware:** use el simulador:

```bash
cd backend
python scripts/simulate_device.py --api-key <DEVICE_API_KEY> --interval 5
```

## Pruebas automatizadas

```bash
cd backend
pytest -q
```

Las pruebas usan SQLite en memoria y no requieren PostgreSQL.

## Obtener la IP del PC

| Sistema | Comando |
|---------|---------|
| Windows | `ipconfig` → "Dirección IPv4" del adaptador WiFi |
| Linux | `ip addr` o `hostname -I` |
| macOS | `ipconfig getifaddr en0` |
