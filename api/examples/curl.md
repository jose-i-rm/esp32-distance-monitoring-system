# Ejemplos con curl

## Bash (Linux / macOS / Git Bash)

```bash
API=http://localhost:8000
KEY=<DEVICE_API_KEY>

# Estado del servicio
curl -s $API/health

# Registrar medición (equivale a "2026-11-01 11:08:55 | Distancia: 214.05 cm")
curl -s -X POST $API/api/v1/measurements \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"timestamp":"2026-11-01T11:08:55-05:00","distance_cm":214.05}'

# Última medición
curl -s $API/api/v1/measurements/latest

# Historial paginado y filtrado
curl -s "$API/api/v1/measurements?limit=20&offset=0"
curl -s "$API/api/v1/measurements?start=2026-11-01T00:00:00-05:00&end=2026-11-01T23:59:59-05:00"
```

## PowerShell (Windows)

```powershell
$Api = "http://localhost:8000"
$Key = "<DEVICE_API_KEY>"

Invoke-RestMethod "$Api/health"

$body = @{ timestamp = "2026-11-01T11:09:25-05:00"; distance_cm = 4.92 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$Api/api/v1/measurements" `
  -ContentType "application/json" -Headers @{ "X-API-Key" = $Key } -Body $body

Invoke-RestMethod "$Api/api/v1/measurements/latest"
Invoke-RestMethod "$Api/api/v1/measurements?limit=20"
```
