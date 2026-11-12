/*
 * ESP32 Distance Monitoring System - Firmware
 * ESP32-S3 N16R8 + HC-SR04 -> Firebase Realtime Database
 * (origen de datos migrado desde la ESP32-CAM AI Thinker; mismo contrato Firebase)
 *
 * - Lectura del HC-SR04 cada 30 s (TRIG GPIO12, ECHO GPIO13, VCC 3V3).
 * - Hora real sincronizada por NTP (UTC-5).
 * - Envío HTTPS a Firebase autenticado con la cuenta del dispositivo
 *   (Firebase Authentication, correo/contraseña). No requiere librerías externas.
 * - v3: detección de cambios en el borde. Si |distancia - anterior| >= UMBRAL_CAMBIO_CM
 *   se registra un evento en /alerts y en /stats/last_alert (misma escritura atómica).
 *
 * Copie secrets.example.h como secrets.h y complete los valores.
 */
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include "secrets.h"

// ESP32-S3 N16R8: GPIO12/13 son de uso general (la PSRAM octal usa GPIO35-37 y la flash GPIO26-32).
const int trigPin = 12;
const int echoPin = 13;

const unsigned long INTERVALO_MS = 30000;
const long GMT_OFFSET_S = -5 * 3600;
const char* ZONA_ISO = "-05:00";

// Cambio mínimo entre lecturas consecutivas que genera una alerta (el ruido del sensor es < 1 cm).
const float UMBRAL_CAMBIO_CM = 10.0;

String idToken;
float distanciaAnterior = -1;  // -1: aún no hay lectura previa (no se alerta tras reiniciar)
unsigned long tokenObtenidoMs = 0;
unsigned long tokenVidaMs = 0;
unsigned long ultimaLecturaMs = 0;
bool primeraLectura = true;

void conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println("Conectando a WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 20000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi conectado");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("No fue posible conectar al WiFi; se reintentara");
  }
}

// Extrae el valor de un campo de primer nivel de una respuesta JSON simple.
String extraerCampo(const String& json, const char* campo) {
  String clave = String("\"") + campo + "\"";
  int i = json.indexOf(clave);
  if (i < 0) return "";
  i = json.indexOf(':', i + clave.length());
  if (i < 0) return "";
  i++;
  while (i < (int)json.length() && isspace((unsigned char)json[i])) i++;

  if (json[i] == '"') {
    int fin = json.indexOf('"', i + 1);
    return fin < 0 ? "" : json.substring(i + 1, fin);
  }
  int fin = i;
  while (fin < (int)json.length() && json[fin] != ',' && json[fin] != '}' && !isspace((unsigned char)json[fin])) fin++;
  return json.substring(i, fin);
}

bool iniciarSesionFirebase() {
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;

  String url = String("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=") + FIREBASE_API_KEY;
  if (!http.begin(client, url)) return false;
  http.setTimeout(15000);
  http.addHeader("Content-Type", "application/json");

  String body = String("{\"email\":\"") + DEVICE_EMAIL + "\",\"password\":\"" + DEVICE_PASSWORD +
                "\",\"returnSecureToken\":true}";
  int code = http.POST(body);
  String respuesta = http.getString();
  http.end();

  if (code != 200) {
    Serial.printf("Firebase Auth: error HTTP %d\n", code);
    Serial.println(respuesta);
    return false;
  }

  idToken = extraerCampo(respuesta, "idToken");
  long expiraSeg = extraerCampo(respuesta, "expiresIn").toInt();
  if (idToken.isEmpty() || expiraSeg <= 0) {
    Serial.println("Firebase Auth: respuesta inesperada");
    return false;
  }

  tokenObtenidoMs = millis();
  // Renueva el token 5 minutos antes de que expire (dura 1 hora).
  tokenVidaMs = (unsigned long)(expiraSeg > 600 ? expiraSeg - 300 : expiraSeg / 2) * 1000UL;
  Serial.println("Firebase Auth: sesion iniciada");
  return true;
}

bool tokenVigente() {
  return idToken.length() > 0 && (millis() - tokenObtenidoMs) < tokenVidaMs;
}

// Guarda la lectura en /measurements/<epoch> y actualiza /stats en una sola petición.
// Si hay alerta, la añade en /alerts/<epoch> y /stats/last_alert dentro de la misma escritura.
int enviarMedicion(time_t epoch, const char* fechaIso, float distancia, bool alerta, float anterior) {
  char registro[220];
  snprintf(registro, sizeof(registro),
           "{\"epoch\":%ld,\"ts\":\"%s\",\"distance_cm\":%.2f,"
           "\"received_at\":{\".sv\":\"timestamp\"},\"device\":\"%s\"}",
           (long)epoch, fechaIso, distancia, DEVICE_ID);

  String body = String("{\"measurements/") + String((long)epoch) + "\":" + registro +
                ",\"stats/latest\":" + registro +
                ",\"stats/count\":{\".sv\":{\"increment\":1}}";

  if (alerta) {
    float delta = distancia - anterior;
    char evento[300];
    snprintf(evento, sizeof(evento),
             "{\"epoch\":%ld,\"ts\":\"%s\",\"previous_cm\":%.2f,\"distance_cm\":%.2f,"
             "\"delta_cm\":%.2f,\"type\":\"%s\",\"threshold_cm\":%.1f,"
             "\"received_at\":{\".sv\":\"timestamp\"},\"device\":\"%s\"}",
             (long)epoch, fechaIso, anterior, distancia, delta,
             delta < 0 ? "acercamiento" : "alejamiento", UMBRAL_CAMBIO_CM, DEVICE_ID);
    body += String(",\"alerts/") + String((long)epoch) + "\":" + evento +
            ",\"stats/last_alert\":" + evento +
            ",\"stats/alert_count\":{\".sv\":{\"increment\":1}}";
  }
  body += "}";

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;

  String url = String(FIREBASE_DB_URL) + "/.json?auth=" + idToken;
  if (!http.begin(client, url)) return -1;
  http.setTimeout(15000);
  http.addHeader("Content-Type", "application/json");

  int code = http.PATCH(body);
  if (code != 200) {
    Serial.printf("Firebase DB: error HTTP %d\n", code);
    Serial.println(http.getString());
  }
  http.end();
  return code;
}

float medirDistancia() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000);
  if (duration == 0) return -1;
  return duration * 0.0343 / 2;
}

void setup() {
  Serial.begin(115200);
  // Con "USB CDC On Boot" habilitado, espera brevemente al monitor serie USB nativo del S3.
  unsigned long inicioSerie = millis();
  while (!Serial && millis() - inicioSerie < 3000) delay(10);

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  digitalWrite(trigPin, LOW);

  Serial.println();
  conectarWiFi();
  while (WiFi.status() != WL_CONNECTED) {
    delay(5000);
    conectarWiFi();
  }

  configTime(GMT_OFFSET_S, 0, "pool.ntp.org", "time.google.com");

  Serial.println("Esperando sincronizacion NTP...");
  struct tm timeinfo;
  while (!getLocalTime(&timeinfo)) {
    Serial.print(".");
    delay(1000);
  }
  Serial.println();
  Serial.println("Hora sincronizada");

  iniciarSesionFirebase();
}

void loop() {
  if (!primeraLectura && millis() - ultimaLecturaMs < INTERVALO_MS) {
    delay(50);
    return;
  }
  primeraLectura = false;
  ultimaLecturaMs = millis();

  float distance = medirDistancia();

  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("Hora no disponible; lectura omitida");
    return;
  }

  char fechaHora[30];
  strftime(fechaHora, sizeof(fechaHora), "%Y-%m-%d %H:%M:%S", &timeinfo);

  if (distance < 0) {
    Serial.print(fechaHora);
    Serial.println(" | Sin eco del sensor (fuera de rango); lectura no enviada");
    return;
  }

  Serial.print(fechaHora);
  Serial.print(" | Distancia: ");
  Serial.print(distance);
  Serial.println(" cm");

  char fechaIso[32];
  strftime(fechaIso, sizeof(fechaIso), "%Y-%m-%dT%H:%M:%S", &timeinfo);
  strncat(fechaIso, ZONA_ISO, sizeof(fechaIso) - strlen(fechaIso) - 1);
  time_t epoch = time(nullptr);

  // Detección de cambio en el borde: se compara con la última lectura válida.
  bool alerta = distanciaAnterior >= 0 && fabs(distance - distanciaAnterior) >= UMBRAL_CAMBIO_CM;
  float anterior = distanciaAnterior;
  distanciaAnterior = distance;
  if (alerta) {
    Serial.printf("  ** ALERTA: cambio de %.2f cm (%.2f -> %.2f cm)\n", distance - anterior, anterior, distance);
  }

  conectarWiFi();
  if (WiFi.status() != WL_CONNECTED) return;

  if (!tokenVigente() && !iniciarSesionFirebase()) return;

  int code = enviarMedicion(epoch, fechaIso, distance, alerta, anterior);
  if (code == 401 && iniciarSesionFirebase()) {
    code = enviarMedicion(epoch, fechaIso, distance, alerta, anterior);
  }

  if (code == 200) {
    Serial.println(alerta ? "  -> Guardado en Firebase (con alerta)" : "  -> Guardado en Firebase");
  }
}
