"""Contrato para la futura ingesta de mediciones vía MQTT.

Tópicos propuestos:
    esp32/{device_id}/distance   -> payload JSON {"timestamp": "...", "distance_cm": 12.3}
    esp32/{device_id}/status     -> "online" / "offline" (Last Will and Testament)
    esp32/{device_id}/servo/set  -> ángulo 0-180 para el servo SG90

La implementación usará un cliente como `paho-mqtt` o `aiomqtt` y reutilizará
`app.crud.create_measurement` para persistir los datos.
"""

DISTANCE_TOPIC = "esp32/{device_id}/distance"
STATUS_TOPIC = "esp32/{device_id}/status"
SERVO_TOPIC = "esp32/{device_id}/servo/set"
