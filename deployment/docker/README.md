# Entorno local con Docker Compose

Levanta **PostgreSQL 16**, la **API FastAPI** y el **dashboard** (Nginx) con un solo comando.

```bash
cd deployment/docker
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
docker compose up --build -d
docker compose logs -f api
```

| Servicio | URL |
|----------|-----|
| Dashboard | http://localhost:5500 |
| API / Swagger | http://localhost:8000/docs |
| PostgreSQL | `postgresql://esp32:esp32@localhost:5432/esp32_monitoring` |

Cargar datos de prueba:

```bash
cd ../../backend
python scripts/simulate_device.py --api-key cambie-esta-clave --count 30 --interval 0
```

Detener y eliminar datos:

```bash
docker compose down        # conserva el volumen
docker compose down -v     # elimina también la base de datos
```
