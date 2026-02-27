#include <WebServer.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_wifi.h>

// --- Configuration ---
const char *ssid = "STEM.MY";
const char *password = "DR6R3FGQ233";

const String device_id =
    "ESP32_NODE_3"; // Change for each Node (e.g., ESP32_NODE_2)

// Built-in LED pin (GPIO 33 for ESP32-CAM, GPIO 2 for standard ESP32)
// ESP32-CAM uses inverted logic for GPIO 33 (LOW = ON, HIGH = OFF)
const int LED_PIN = 33;

WebServer server(80);
WiFiUDP udp;

unsigned long lastPingTime = 0;
unsigned long lastRequestTime = 0; // Track when we last received a request
const int pingInterval =
    20; // Broadcast every 20ms to guarantee constant CSI traffic

volatile bool data_ready = false;
int csi_amplitudes[128];
int num_amplitudes = 0;

// CSI Callback function
void _wifi_csi_cb(void *ctx, wifi_csi_info_t *data) {
  if (data == NULL || data->buf == NULL)
    return;

  // If the main loop hasn't consumed the last packet yet, drop this one to
  // prevent corruption
  if (data_ready)
    return;

  int csi_len = data->len;
  int8_t *csi_buf = data->buf;

  num_amplitudes = csi_len / 2;
  if (num_amplitudes <= 0) {
    return;
  }
  if (num_amplitudes > 128)
    num_amplitudes = 128; // bounds check

  for (int i = 0; i < num_amplitudes; i++) {
    int8_t real = csi_buf[2 * i];
    int8_t imag = csi_buf[2 * i + 1];

    // Quick amplitude calculation
    csi_amplitudes[i] = sqrt((real * real) + (imag * imag));
  }

  // Signal that we have a fresh frame of data
  data_ready = true;
}

void handleCsiRequest() {
  if (!data_ready) {
    server.send(503, "text/plain", "Data not ready");
    return;
  }

  String payload = device_id;
  for (int i = 0; i < num_amplitudes; i++) {
    payload += "," + String(csi_amplitudes[i]);
  }

  server.send(200, "text/plain", payload);
  data_ready = false; // allow next packet to be captured

  // Update LED status
  lastRequestTime = millis();
  digitalWrite(LED_PIN, LOW); // Turn ON LED (ESP32-CAM is inverted)

  Serial.println("Served CSI data to client!");
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n--- SentinAI ESP32 CSI HTTP Server ---");

  // Setup LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH); // Turn OFF LED initially

  // Connect to Wi-Fi
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected! IP Address: ");
  Serial.println(WiFi.localIP());

  // Setup Web Server
  server.on("/csi", HTTP_GET, handleCsiRequest);
  server.begin();
  Serial.println("HTTP Server started on port 80!");

  // Setup UDP for active transmission
  udp.begin(1234);

  // Get the channel of the connected AP
  uint8_t primaryChan = WiFi.channel();
  Serial.print("Router Channel: ");
  Serial.println(primaryChan);

  // Enable promiscuous mode so we can capture CSI packets
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_promiscuous_rx_cb(NULL); // We don't need raw packets, just CSI
  esp_wifi_set_channel(primaryChan, WIFI_SECOND_CHAN_NONE);

  // Configure CSI
  wifi_csi_config_t csi_config = {.lltf_en = true,
                                  .htltf_en = true,
                                  .stbc_htltf2_en = true,
                                  .ltf_merge_en = true,
                                  .channel_filter_en = false,
                                  .manu_scale = false,
                                  .shift = false};

  esp_err_t err;
  err = esp_wifi_set_csi_config(&csi_config);
  if (err != ESP_OK)
    Serial.println("CSI Config failed");

  err = esp_wifi_set_csi_rx_cb(&_wifi_csi_cb, NULL);
  if (err != ESP_OK)
    Serial.println("CSI Callback setup failed");

  err = esp_wifi_set_csi(true);
  if (err != ESP_OK)
    Serial.println("CSI Enable failed");

  Serial.println("CSI Capture Started...");
}

void loop() {
  server.handleClient();

  // Actively blast UDP packets to guarantee high-frequency CSI data.
  // This solves the stuttering/offline false positive issue by creating our own
  // constant traffic pool!
  if (millis() - lastPingTime > pingInterval) {
    udp.beginPacket("255.255.255.255", 1234);
    udp.write((const uint8_t *)"ping", 4);
    udp.endPacket();
    lastPingTime = millis();
  }

  // Turn off LED if we haven't received a request in 1 second
  if (millis() - lastRequestTime > 1000) {
    digitalWrite(LED_PIN, HIGH); // Turn OFF LED
  }
}