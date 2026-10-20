/**
 * Plain ESP32 inference node. No camera driver, JPEG decoder, ultrasonic sensor or MQTT.
 * POST /infer: application/octet-stream, exactly 4096 uint8 grayscale pixels.
 * The gateway crops/resizes using the SAME preprocessing used to train the model.
 * Requires a compatible TensorFlow Lite Micro Arduino library (modern API).
 */
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "esp32_config.h"
#include "model_data.h"

WebServer server(HTTP_PORT);
alignas(16) static uint8_t tensor_arena[TENSOR_ARENA_SIZE];
static tflite::MicroInterpreter* interpreter = nullptr;
static TfLiteTensor* input_tensor = nullptr;
static TfLiteTensor* output_tensor = nullptr;
static bool model_ready = false;
static uint8_t pixel_buffer[INPUT_BYTES];
static size_t received_bytes = 0;
static bool raw_complete = false;
static bool raw_invalid = false;

// Use WebServer's RAW callback: arg("plain") can truncate binary at byte 0.
void receive_pixels() {
  HTTPRaw& raw = server.raw();
  if (raw.status == RAW_START) {
    received_bytes = 0;
    raw_complete = false;
    raw_invalid = false;
  } else if (raw.status == RAW_WRITE) {
    if (raw_invalid || raw.currentSize > INPUT_BYTES - received_bytes) {
      raw_invalid = true;
      return;
    }
    memcpy(pixel_buffer + received_bytes, raw.buf, raw.currentSize);
    received_bytes += raw.currentSize;
  } else if (raw.status == RAW_END) {
    raw_complete = !raw_invalid && received_bytes == INPUT_BYTES;
  } else if (raw.status == RAW_ABORTED) {
    raw_invalid = true;
    raw_complete = false;
  }
}

bool valid_id(const String& value) {
  if (value.length() == 0 || value.length() > 64) return false;
  for (size_t i = 0; i < value.length(); i++) {
    char c = value[i];
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') || c == '_' || c == '-')) return false;
  }
  return true;
}

bool init_model() {
  const tflite::Model* model = tflite::GetModel(g_parking_model_data);
  if (model->version() != TFLITE_SCHEMA_VERSION) return false;
  // These are the six real ops found in run_gpu01; DELEGATE is a desktop-only op.
  static tflite::MicroMutableOpResolver<6> resolver;
  if (resolver.AddConv2D() != kTfLiteOk || resolver.AddDepthwiseConv2D() != kTfLiteOk ||
      resolver.AddMaxPool2D() != kTfLiteOk || resolver.AddMean() != kTfLiteOk ||
      resolver.AddFullyConnected() != kTfLiteOk || resolver.AddLogistic() != kTfLiteOk) return false;
  static tflite::MicroInterpreter instance(model, resolver, tensor_arena, sizeof(tensor_arena));
  interpreter = &instance;
  if (interpreter->AllocateTensors() != kTfLiteOk) return false;
  input_tensor = interpreter->input(0);
  output_tensor = interpreter->output(0);
  if (input_tensor->type != kTfLiteInt8 || output_tensor->type != kTfLiteInt8 ||
      input_tensor->dims->size != 4 || input_tensor->dims->data[0] != 1 ||
      input_tensor->dims->data[1] != 64 || input_tensor->dims->data[2] != 64 ||
      input_tensor->dims->data[3] != 1 || input_tensor->bytes != INPUT_BYTES ||
      output_tensor->bytes != 1 || input_tensor->params.scale <= 0 || output_tensor->params.scale <= 0) return false;
  Serial.printf("[MODEL] ready, arena used: %u bytes; heap free: %u bytes\n",
                (unsigned)interpreter->arena_used_bytes(), ESP.getFreeHeap());
  return true;
}

void handle_health() {
  String body = String("{\"ready\":") + (model_ready ? "true" : "false") +
      ",\"model_sha256\":\"" + g_parking_model_sha256 +
      "\",\"input_bytes\":4096,\"arena_bytes\":" + String(TENSOR_ARENA_SIZE) + "}";
  server.send(model_ready ? 200 : 503, "application/json", body);
}

void handle_infer() {
  if (!model_ready) {
    server.send(503, "application/json", "{\"error\":\"MODEL_NOT_READY\"}");
    return;
  }
  if (server.header("Content-Type") != "application/octet-stream") {
    server.send(415, "application/json", "{\"error\":\"EXPECTED_RAW_UINT8\"}");
    return;
  }
  if (server.header("X-Model-Sha256") != g_parking_model_sha256) {
    server.send(409, "application/json", "{\"error\":\"MODEL_MISMATCH\"}");
    return;
  }
  const String request_id = server.header("X-Request-Id");
  const String slot_id = server.header("X-Slot-Id");
  if (!valid_id(request_id) || !valid_id(slot_id)) {
    server.send(400, "application/json", "{\"error\":\"INVALID_REQUEST_OR_SLOT_ID\"}");
    return;
  }
  float threshold = DEFAULT_CAR_THRESHOLD;
  const String threshold_header = server.header("X-Threshold");
  if (threshold_header.length()) {
    char* end = nullptr;
    threshold = strtof(threshold_header.c_str(), &end);
    if (end == threshold_header.c_str() || *end != '\0' || !isfinite(threshold) || threshold < 0 || threshold > 1) {
      server.send(400, "application/json", "{\"error\":\"INVALID_THRESHOLD\"}");
      return;
    }
  }
  if (!raw_complete || raw_invalid || received_bytes != INPUT_BYTES) {
    server.send(400, "application/json", "{\"error\":\"EXPECTED_4096_BYTES\"}");
    return;
  }
  const uint8_t* pixels = pixel_buffer;
  raw_complete = false;
  for (size_t i = 0; i < INPUT_BYTES; i++) {
    // Rescaling /255 is already in the model. Do NOT divide pixels by 255 here.
    int32_t q = (int32_t)roundf(pixels[i] / input_tensor->params.scale) + input_tensor->params.zero_point;
    if (q < -128) q = -128;
    if (q > 127) q = 127;
    input_tensor->data.int8[i] = (int8_t)q;
  }
  uint32_t started = micros();
  if (interpreter->Invoke() != kTfLiteOk) {
    server.send(500, "application/json", "{\"error\":\"INFERENCE_FAILED\"}");
    return;
  }
  float elapsed_ms = (micros() - started) / 1000.0f;
  float score = (output_tensor->data.int8[0] - output_tensor->params.zero_point) * output_tensor->params.scale;
  if (!isfinite(score)) {
    server.send(500, "application/json", "{\"error\":\"INVALID_SCORE\"}");
    return;
  }
  score = constrain(score, 0.0f, 1.0f);
  int label = score >= threshold ? 1 : 0;
  String response = String("{\"request_id\":\"") + request_id + "\",\"slot_id\":\"" + slot_id +
      "\",\"model_sha256\":\"" + g_parking_model_sha256 + "\",\"label\":" + String(label) +
      ",\"car_score\":" + String(score, 8) + ",\"threshold\":" + String(threshold, 8) +
      ",\"latency_ms\":" + String(elapsed_ms, 3) + "}";
  server.send(200, "application/json", response);
}

void setup() {
  Serial.begin(115200);
  model_ready = init_model();
  if (!model_ready) Serial.println("[MODEL] initialization failed; /infer will return 503.");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  const char* headers[] = {"Content-Type", "X-Model-Sha256", "X-Request-Id", "X-Slot-Id", "X-Threshold"};
  server.collectHeaders(headers, 5);
  server.on("/health", HTTP_GET, handle_health);
  // Modern Arduino-ESP32 WebServer invokes this callback for raw POST bodies.
  server.on("/infer", HTTP_POST, handle_infer, receive_pixels);
  server.begin();
}

void loop() {
  static bool announced = false;
  if (WiFi.status() == WL_CONNECTED) {
    if (!announced) {
      Serial.printf("[HTTP] http://%s:%d; model ready=%d\n", WiFi.localIP().toString().c_str(), HTTP_PORT, model_ready);
      announced = true;
    }
    server.handleClient();
  } else {
    announced = false;
  }
  delay(1);
}
