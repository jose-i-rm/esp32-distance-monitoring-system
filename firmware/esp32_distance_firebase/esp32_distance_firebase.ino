/*
 * ESP32 Distance Monitoring System - Firmware
 * ESP32-S3 N16R8 + HC-SR04 sobre servo SG90 (radar de barrido) -> Firebase Realtime Database
 *
 * - Servo SG90 en GPIO15 (LEDC 50 Hz) barre de ANGULO_MIN a ANGULO_MAX en pasos de PASO_ANGULO.
 * - HC-SR04 (TRIG GPIO12, ECHO GPIO13, VCC 3V3): mediana de 3 lecturas en cada ángulo.
 * - Detección en el borde por ángulo: si algo aparece dentro de ZONA_CM al menos UMBRAL_CAMBIO_CM más cerca
 *   que todo lo visto en ese ángulo en las últimas pasadas (y se confirma en la siguiente), se registra una
 *   alerta de acercamiento con su angle_deg en /alerts y /stats/last_alert. El backend mueve la cámara PTZ
 *   y toma una foto.
 * - Cada 30 s: lectura del objeto más cercano del último barrido (con angle_deg) en /measurements.
 * - Cada 10 s: barrido completo en /stats/sweep (lo dibuja el radar del dashboard).
 * - Hora NTP (UTC-5); HTTPS a Firebase con la cuenta del dispositivo (Firebase Authentication).
 *
 * Copie secrets.example.h como secrets.h y complete los valores.
 */
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <esp_task_wdt.h>
#include <time.h>
#include "secrets.h"

// ESP32-S3 N16R8: GPIO12/13/15 son de uso general (la PSRAM octal usa GPIO35-37 y la flash GPIO26-32).
const int trigPin = 12;
const int echoPin = 13;
const int servoPin = 15;

// Servo SG90: pulso de 500-2400 µs para 0-180°. El montaje admite el giro completo (probado).
const int SERVO_MIN_US = 500;
const int SERVO_MAX_US = 2400;
const int ANGULO_MIN = 0;
const int ANGULO_MAX = 180;
// Paso fino para dibujar el contorno del entorno en el radar (37 lecturas por barrido, ~11 s).
const int PASO_ANGULO = 5;
const int NUM_ANGULOS = (ANGULO_MAX - ANGULO_MIN) / PASO_ANGULO + 1;
const int ANGULO_REPOSO = 90;
// Tiempo para que el servo llegue a la posición y se estabilice antes de medir.
const unsigned long ASENTAMIENTO_MS = 120;  // 5° tarda ~10 ms; el resto amortigua la vibración del montaje
// Pausa entre disparos del HC-SR04 para que no se mezclen ecos.
const unsigned long PAUSA_ECO_MS = 60;
// Sin eco = nada dentro del alcance útil del sensor.
const float SIN_ECO_CM = 400.0;

const unsigned long INTERVALO_MS = 30000;          // Lectura en /measurements
const unsigned long INTERVALO_BARRIDO_MS = 12000;  // Barrido en /stats/sweep (~1 por barrido completo)
const unsigned long PAUSA_ALERTAS_MS = 10000;      // Mínimo entre alertas (protege la cámara y Firebase)
const long GMT_OFFSET_S = -5 * 3600;
const char* ZONA_ISO = "-05:00";

// Si el loop se bloquea más de este tiempo (p. ej. un handshake TLS colgado) la placa se reinicia sola.
const uint32_t WATCHDOG_MS = 120000;
// Límites de red: sin ellos el handshake TLS puede esperar hasta 120 s por defecto.
const int TLS_HANDSHAKE_S = 15;
const int HTTP_CONNECT_MS = 10000;

// Acercamiento mínimo respecto a lo visto antes en ese ángulo para alertar. Con el servo se usa un margen
// mayor que con el sensor fijo (10 cm): la holgura de los engranajes desplaza el haz 2-3° entre pasadas.
const float UMBRAL_CAMBIO_CM = 15.0;
// Solo se alertan acercamientos dentro de esta distancia.
const float ZONA_CM = 300.0;

String idToken;
unsigned long tokenObtenidoMs = 0;
unsigned long tokenVidaMs = 0;

// Estado del radar. Historial de las últimas lecturas por sentido de giro (0 = sube, 1 = baja) y ángulo.
const int HISTORIAL = 5;
const int HISTORIAL_MINIMO = 3;  // Pasadas de aprendizaje antes de alertar en un ángulo
float historial[2][NUM_ANGULOS][HISTORIAL];
int numHist[2][NUM_ANGULOS];
int posHist[2][NUM_ANGULOS];
float candidato[NUM_ANGULOS];      // Acercamiento pendiente de confirmar (-1 = ninguno)
float candidatoPrevio[NUM_ANGULOS];
float ultimoBarrido[NUM_ANGULOS];  // Última lectura de cada ángulo (-1 = sin eco)
int indiceActual = 0;
int sentido = 1;
unsigned long ultimaMedicionMs = 0;
unsigned long ultimoBarridoMs = 0;
unsigned long ultimaAlertaMs = 0;
bool hayAlerta = false;

int anguloDe(int indice) { return ANGULO_MIN + indice * PASO_ANGULO; }

void moverServo(int grados) {
  uint32_t us = SERVO_MIN_US + (uint32_t)(SERVO_MAX_US - SERVO_MIN_US) * grados / 180;
  ledcWrite(servoPin, us * 16383UL / 20000UL);  // 14 bits a 50 Hz (periodo 20 000 µs)
}

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
  client.setHandshakeTimeout(TLS_HANDSHAKE_S);
  HTTPClient http;

  String url = String("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=") + FIREBASE_API_KEY;
  if (!http.begin(client, url)) return false;
  http.setConnectTimeout(HTTP_CONNECT_MS);
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

// Mediana de 3 disparos; -1 si menos de 2 tienen eco.
float medirMediana() {
  float v[3];
  int n = 0;
  for (int i = 0; i < 3; i++) {
    float d = medirDistancia();
    if (d > 0) v[n++] = d;
    delay(PAUSA_ECO_MS);
  }
  if (n < 2) return -1;
  if (n == 2) return (v[0] + v[1]) / 2;
  if (v[0] > v[1]) { float t = v[0]; v[0] = v[1]; v[1] = t; }
  if (v[1] > v[2]) { float t = v[1]; v[1] = v[2]; v[2] = t; }
  if (v[0] > v[1]) { float t = v[0]; v[0] = v[1]; v[1] = t; }
  return v[1];
}

bool horaActual(time_t& epoch, char* fechaIso, size_t len) {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return false;
  strftime(fechaIso, len, "%Y-%m-%dT%H:%M:%S", &timeinfo);
  strncat(fechaIso, ZONA_ISO, len - strlen(fechaIso) - 1);
  epoch = time(nullptr);
  return true;
}

String jsonBarrido(time_t epoch, const char* fechaIso) {
  String s = String("{\"epoch\":") + String((long)epoch) + ",\"ts\":\"" + fechaIso + "\",\"start\":" +
             ANGULO_MIN + ",\"step\":" + PASO_ANGULO + ",\"angle\":" + anguloDe(indiceActual) + ",\"d\":[";
  for (int i = 0; i < NUM_ANGULOS; i++) {
    if (i) s += ",";
    s += ultimoBarrido[i] < 0 ? String("-1") : String(ultimoBarrido[i], 1);
  }
  return s + "]}";
}

// Una sola escritura multiruta (atómica). Reintenta una vez si el token caducó.
int patchFirebase(const String& body) {
  conectarWiFi();
  if (WiFi.status() != WL_CONNECTED) return -1;
  if (!tokenVigente() && !iniciarSesionFirebase()) return -1;

  int code = -1;
  for (int intento = 0; intento < 2; intento++) {
    WiFiClientSecure client;
    client.setInsecure();
    client.setHandshakeTimeout(TLS_HANDSHAKE_S);
    HTTPClient http;

    String url = String(FIREBASE_DB_URL) + "/.json?auth=" + idToken;
    if (!http.begin(client, url)) return -1;
    http.setConnectTimeout(HTTP_CONNECT_MS);
    http.setTimeout(15000);
    http.addHeader("Content-Type", "application/json");

    code = http.PATCH(body);
    if (code != 200) {
      Serial.printf("Firebase DB: error HTTP %d\n", code);
      Serial.println(http.getString());
    }
    http.end();
    if (code != 401 || !iniciarSesionFirebase()) break;
  }
  return code;
}

void enviarAlerta(int angulo, float anterior, float actual) {
  time_t epoch;
  char fechaIso[32];
  if (!horaActual(epoch, fechaIso, sizeof(fechaIso))) return;

  float delta = actual - anterior;
  char evento[340];
  snprintf(evento, sizeof(evento),
           "{\"epoch\":%ld,\"ts\":\"%s\",\"previous_cm\":%.2f,\"distance_cm\":%.2f,"
           "\"delta_cm\":%.2f,\"type\":\"%s\",\"threshold_cm\":%.1f,\"angle_deg\":%d,"
           "\"received_at\":{\".sv\":\"timestamp\"},\"device\":\"%s\"}",
           (long)epoch, fechaIso, anterior, actual, delta,
           delta < 0 ? "acercamiento" : "alejamiento", UMBRAL_CAMBIO_CM, angulo, DEVICE_ID);
  String body = String("{\"alerts/") + String((long)epoch) + "\":" + evento + ",\"stats/last_alert\":" + evento +
                ",\"stats/alert_count\":{\".sv\":{\"increment\":1}},\"stats/sweep\":" +
                jsonBarrido(epoch, fechaIso) + "}";

  Serial.printf("  ** ALERTA %s a %d grados: %.2f -> %.2f cm\n", delta < 0 ? "acercamiento" : "alejamiento",
                angulo, anterior, actual);
  if (patchFirebase(body) == 200) Serial.println("  -> Alerta guardada en Firebase");
}

// Lectura periódica: el objeto más cercano del último barrido, con su ángulo.
void enviarMedicionYBarrido(bool incluirMedicion) {
  time_t epoch;
  char fechaIso[32];
  if (!horaActual(epoch, fechaIso, sizeof(fechaIso))) return;

  String body = String("{\"stats/sweep\":") + jsonBarrido(epoch, fechaIso);
  int iMin = -1;
  for (int i = 0; i < NUM_ANGULOS; i++) {
    if (ultimoBarrido[i] > 0 && (iMin < 0 || ultimoBarrido[i] < ultimoBarrido[iMin])) iMin = i;
  }
  if (incluirMedicion && iMin >= 0) {
    char registro[240];
    snprintf(registro, sizeof(registro),
             "{\"epoch\":%ld,\"ts\":\"%s\",\"distance_cm\":%.2f,\"angle_deg\":%d,"
             "\"received_at\":{\".sv\":\"timestamp\"},\"device\":\"%s\"}",
             (long)epoch, fechaIso, ultimoBarrido[iMin], anguloDe(iMin), DEVICE_ID);
    body += String(",\"measurements/") + String((long)epoch) + "\":" + registro + ",\"stats/latest\":" + registro +
            ",\"stats/count\":{\".sv\":{\"increment\":1}}";
    Serial.printf("%s | Mas cercano: %.2f cm a %d grados\n", fechaIso, ultimoBarrido[iMin], anguloDe(iMin));
  } else if (incluirMedicion) {
    Serial.printf("%s | Sin eco en ningun angulo; lectura no enviada\n", fechaIso);
  }
  body += "}";
  if (patchFirebase(body) == 200 && incluirMedicion && iMin >= 0) Serial.println("  -> Guardado en Firebase");
}

float minimoHistorial(int dir, int i) {
  float m = -1;
  for (int k = 0; k < numHist[dir][i]; k++) {
    if (m < 0 || historial[dir][i][k] < m) m = historial[dir][i][k];
  }
  return m;
}

void guardarHistorial(int dir, int i, float valor) {
  historial[dir][i][posHist[dir][i]] = valor;
  posHist[dir][i] = (posHist[dir][i] + 1) % HISTORIAL;
  if (numHist[dir][i] < HISTORIAL) numHist[dir][i]++;
}

// Alerta solo si algo aparece dentro de la zona MÁS CERCA que todo lo visto en ese ángulo en las últimas
// HISTORIAL pasadas (por sentido de giro: el servo no llega al mismo punto desde la izquierda que desde la
// derecha) y se confirma en la visita siguiente. Así se ignoran bordes de objetos y ecos irregulares.
void evaluarAngulo(int dir, int i, float lectura) {
  float efectiva = lectura < 0 ? SIN_ECO_CM : min(lectura, SIN_ECO_CM);
  float minimo = minimoHistorial(dir, i);
  bool pendiente = candidato[i] >= 0 && fabs(efectiva - candidato[i]) < UMBRAL_CAMBIO_CM;

  if (pendiente) {
    float anterior = candidatoPrevio[i];
    candidato[i] = -1;
    // El objeto pasa a ser "conocido" en ambos sentidos de giro: si se queda quieto no vuelve a alertar.
    guardarHistorial(0, i, efectiva);
    guardarHistorial(1, i, efectiva);
    if (millis() - ultimaAlertaMs < PAUSA_ALERTAS_MS && hayAlerta) {
      Serial.printf("  (acercamiento a %d grados sin alerta: pausa entre alertas)\n", anguloDe(i));
      return;
    }
    ultimaAlertaMs = millis();
    hayAlerta = true;
    enviarAlerta(anguloDe(i), anterior, efectiva);
    return;
  }
  candidato[i] = -1;
  if (numHist[dir][i] >= HISTORIAL_MINIMO && efectiva < ZONA_CM && efectiva <= minimo - UMBRAL_CAMBIO_CM) {
    candidato[i] = efectiva;
    candidatoPrevio[i] = minimo;
    return;  // No entra al historial hasta confirmarse
  }
  guardarHistorial(dir, i, efectiva);
}
void iniciarWatchdog() {
  esp_task_wdt_config_t config = {};
  config.timeout_ms = WATCHDOG_MS;
  config.idle_core_mask = 0;
  config.trigger_panic = true;
  // El core de Arduino ya inicia el watchdog de tareas; si no, se inicia aquí.
  if (esp_task_wdt_reconfigure(&config) != ESP_OK) esp_task_wdt_init(&config);
  esp_task_wdt_add(NULL);
}

void setup() {
  Serial.begin(115200);
  // Con "USB CDC On Boot" habilitado, espera brevemente al monitor serie USB nativo del S3.
  unsigned long inicioSerie = millis();
  while (!Serial && millis() - inicioSerie < 3000) delay(10);

  iniciarWatchdog();
  Serial.printf("\nMotivo del reinicio: %d\n", (int)esp_reset_reason());

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  digitalWrite(trigPin, LOW);
  ledcAttach(servoPin, 50, 14);
  moverServo(ANGULO_REPOSO);
  for (int i = 0; i < NUM_ANGULOS; i++) {
    candidato[i] = candidatoPrevio[i] = ultimoBarrido[i] = -1;
    numHist[0][i] = numHist[1][i] = posHist[0][i] = posHist[1][i] = 0;
  }

  conectarWiFi();
  while (WiFi.status() != WL_CONNECTED) {
    esp_task_wdt_reset();
    delay(5000);
    conectarWiFi();
  }

  configTime(GMT_OFFSET_S, 0, "pool.ntp.org", "time.google.com");

  Serial.println("Esperando sincronizacion NTP...");
  struct tm timeinfo;
  while (!getLocalTime(&timeinfo)) {
    esp_task_wdt_reset();
    Serial.print(".");
    delay(1000);
  }
  Serial.println();
  Serial.println("Hora sincronizada");

  iniciarSesionFirebase();
  Serial.printf("Radar: %d-%d grados en pasos de %d (%d posiciones)\n", ANGULO_MIN, ANGULO_MAX, PASO_ANGULO,
                NUM_ANGULOS);
  ultimaMedicionMs = millis();
  ultimoBarridoMs = millis();
}

void loop() {
  esp_task_wdt_reset();

  moverServo(anguloDe(indiceActual));
  delay(ASENTAMIENTO_MS);
  float lectura = medirMediana();
  ultimoBarrido[indiceActual] = lectura;
  evaluarAngulo(sentido > 0 ? 0 : 1, indiceActual, lectura);

  // Avanza y rebota en los extremos (sin repetir el extremo).
  if (indiceActual + sentido < 0 || indiceActual + sentido >= NUM_ANGULOS) sentido = -sentido;
  indiceActual += sentido;

  unsigned long ahora = millis();
  bool tocaMedicion = ahora - ultimaMedicionMs >= INTERVALO_MS;
  if (tocaMedicion || ahora - ultimoBarridoMs >= INTERVALO_BARRIDO_MS) {
    if (tocaMedicion) ultimaMedicionMs = ahora;
    ultimoBarridoMs = ahora;
    enviarMedicionYBarrido(tocaMedicion);
  }
}
