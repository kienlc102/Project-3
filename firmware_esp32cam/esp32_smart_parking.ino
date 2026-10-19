/**
 * ==============================================================================
 * DỰ ÁN: GIÁM SÁT Ô ĐỖ XE THÔNG MINH - SENSOR FUSION & TINYML (ESP32-CAM)
 * ==============================================================================
 * Luồng hoạt động (Wake-on-Sensor):
 * 1. Vi điều khiển ở trạng thái IDLE_VACANT, định kỳ đọc cảm biến khoảng cách.
 * 2. Nếu có vật cản (khoảng cách < 15cm), bật nguồn/đánh thức camera chụp 1 frame 64x64.
 * 3. Chạy mô hình TinyML CNN INT8 (Depthwise Separable):
 *    - Xác suất Xe >= 0.75: Báo trạng thái "OCCUPIED" (Có xe) qua MQTT.
 *    - Xác suất Xe < 0.75: Giữ "VACANT", ghi log không phát hiện xe.
 * 4. Khi đang có xe, nếu xe rời đi (khoảng cách > 18cm):
 *    - Tự động chuyển về "VACANT" mà KHÔNG CẦN BẬT CAMERA/AI (tiết kiệm năng lượng tối đa).
 * ==============================================================================
 */

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "esp_camera.h"

// Thư viện TensorFlow Lite for Microcontrollers
#include "tensorflow/lite/micro/all_ops_resolver.h"
#include "tensorflow/lite/micro/micro_error_reporter.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "esp32_config.h"
#include "model_data.h"

// ------------------------------------------------------------------------------
// Các trạng thái của máy trạng thái hữu hạn (Finite State Machine)
// ------------------------------------------------------------------------------
enum ParkingSpotState {
  STATE_IDLE_VACANT,          // Ô trống, camera ngủ, chỉ đo khoảng cách định kỳ
  STATE_VERIFYING_CAMERA,     // Phát hiện vật cản, bật camera & chạy AI xác minh
  STATE_OCCUPIED_MONITORING   // Đang có xe, chỉ theo dõi khoảng cách để nhận biết xe rời
};

ParkingSpotState g_current_state = STATE_IDLE_VACANT;

// ------------------------------------------------------------------------------
// Biến toàn cục TensorFlow Lite Micro
// ------------------------------------------------------------------------------
namespace {
  tflite::ErrorReporter* error_reporter = nullptr;
  const tflite::Model* model = nullptr;
  tflite::MicroInterpreter* interpreter = nullptr;
  TfLiteTensor* input_tensor = nullptr;
  TfLiteTensor* output_tensor = nullptr;
  
  // Tensor Arena cấp phát tĩnh trong RAM nội bộ
  uint8_t tensor_arena[TENSOR_ARENA_SIZE];
}

// ------------------------------------------------------------------------------
// WiFi & MQTT Clients
// ------------------------------------------------------------------------------
WiFiClient espClient;
PubSubClient mqttClient(espClient);

unsigned long g_last_sensor_check = 0;
float g_last_distance = 999.0f;
bool g_is_car_present = false;

// ------------------------------------------------------------------------------
// Khởi tạo cảm biến khoảng cách (HC-SR04) với bộ lọc trung vị (Median Filter)
// ------------------------------------------------------------------------------
void init_distance_sensor() {
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  digitalWrite(PIN_TRIG, LOW);
}

float read_single_distance() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  // Đọc thời gian phản hồi xung Echo (giới hạn timeout 25ms ~ 4m)
  long duration = pulseIn(PIN_ECHO, HIGH, 25000);
  if (duration == 0) return 999.0f; // Quá tầm đo hoặc lỗi
  
  float distance_cm = (duration * 0.0343f) / 2.0f;
  return distance_cm;
}

// Đọc 3 lần lấy giá trị trung vị để loại bỏ nhiễu giật
float read_distance_median() {
  float d[3];
  for (int i = 0; i < 3; i++) {
    d[i] = read_single_distance();
    delay(5);
  }
  // Sắp xếp nổi bọt 3 phần tử
  if (d[0] > d[1]) { float t = d[0]; d[0] = d[1]; d[1] = t; }
  if (d[1] > d[2]) { float t = d[1]; d[1] = d[2]; d[2] = t; }
  if (d[0] > d[1]) { float t = d[0]; d[0] = d[1]; d[1] = t; }
  return d[1]; // Giá trị ở giữa
}

// ------------------------------------------------------------------------------
// Khởi tạo Camera OV2640 (Cấu hình độ phân giải QQVGA hoặc QCIF để resize 64x64)
// ------------------------------------------------------------------------------
bool init_camera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  
  // Định dạng ảnh xám Grayscale (YUV422 hoặc GRAYSCALE)
  config.pixel_format = PIXFORMAT_GRAYSCALE;
  config.frame_size = FRAMESIZE_QQVGA; // 160x120
  config.jpeg_quality = 12;
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[LỖI] Khởi tạo Camera thất bại: 0x%x\n", err);
    return false;
  }
  Serial.println("[CAMERA] Khởi tạo Camera OV2640 thành công (Grayscale)!");
  return true;
}

// ------------------------------------------------------------------------------
// Khởi tạo TensorFlow Lite Micro Interpreter
// ------------------------------------------------------------------------------
bool init_tflite_micro() {
  static tflite::MicroErrorReporter micro_error_reporter;
  error_reporter = &micro_error_reporter;

  model = tflite::GetModel(g_parking_model_data);
  if (model->version() != TFLITE_SCHEMA_VERSION) {
    TF_LITE_REPORT_ERROR(error_reporter, "Schema phiên bản mô hình không tương thích!");
    return false;
  }

  // Khởi tạo Resolver chứa các toán tử đã dùng (Conv2D, DepthwiseConv2D, Relu, MaxPool, GAP...)
  static tflite::AllOpsResolver resolver;

  // Xây dựng Interpreter
  static tflite::MicroInterpreter static_interpreter(
      model, resolver, tensor_arena, TENSOR_ARENA_SIZE, error_reporter);
  interpreter = &static_interpreter;

  TfLiteStatus allocate_status = interpreter->AllocateTensors();
  if (allocate_status != kTfLiteOk) {
    TF_LITE_REPORT_ERROR(error_reporter, "AllocateTensors() thất bại! Kiểm tra kích thước TENSOR_ARENA_SIZE.");
    return false;
  }

  input_tensor = interpreter->input(0);
  output_tensor = interpreter->output(0);

  Serial.printf("[TFLITE] Đã khởi tạo TFLite Micro! Input dims: %d x %d x %d\n",
                input_tensor->dims->data[1], input_tensor->dims->data[2], input_tensor->dims->data[3]);
  return true;
}

// ------------------------------------------------------------------------------
// Chụp 1 frame, Downsample về 64x64x1 và Chạy TFLite Inference
// Trả về xác suất phát hiện Xe (0.0 đến 1.0)
// ------------------------------------------------------------------------------
float run_ai_inference() {
  // Bật đèn flash nếu môi trường tối
  digitalWrite(PIN_LED_FLASH, HIGH);
  delay(30);

  camera_fb_t* fb = esp_camera_fb_get();
  digitalWrite(PIN_LED_FLASH, LOW);

  if (!fb) {
    Serial.println("[LỖI] Không chụp được frame từ Camera!");
    return 0.0f;
  }

  // Tiền xử lý ảnh: Lấy vùng trung tâm 120x120 của QQVGA (160x120) và downsample về 64x64
  int src_w = fb->width;
  int src_h = fb->height;
  int crop_x = (src_w - 120) / 2;
  int crop_y = 0;

  float in_scale = input_tensor->params.scale;
  int32_t in_zero_point = input_tensor->params.zero_point;

  int8_t* model_input = input_tensor->data.int8;

  for (int y = 0; y < 64; y++) {
    for (int x = 0; x < 64; x++) {
      int src_px = crop_x + (x * 120) / 64;
      int src_py = crop_y + (y * 120) / 64;
      uint8_t pixel_gray = fb->buf[src_py * src_w + src_px];

      // Lượng tử hóa pixel về INT8: int8_val = (pixel / 255.0 / scale) + zero_point
      float normalized = (float)pixel_gray / 255.0f;
      int32_t quant_val = (int32_t)round(normalized / in_scale) + in_zero_point;
      if (quant_val < -128) quant_val = -128;
      if (quant_val > 127) quant_val = 127;

      model_input[y * 64 + x] = (int8_t)quant_val;
    }
  }

  // Giải phóng frame buffer
  esp_camera_fb_return(fb);

  // Chạy suy luận TFLite
  unsigned long start_time = millis();
  TfLiteStatus invoke_status = interpreter->Invoke();
  unsigned long infer_time = millis() - start_time;

  if (invoke_status != kTfLiteOk) {
    Serial.println("[LỖI] Inference Invoke() thất bại!");
    return 0.0f;
  }

  // Giải lượng tử hóa kết quả đầu ra INT8 thành float [0.0, 1.0]
  int8_t out_int8 = output_tensor->data.int8[0];
  float out_scale = output_tensor->params.scale;
  int32_t out_zero_point = output_tensor->params.zero_point;

  float car_probability = (float)(out_int8 - out_zero_point) * out_scale;
  if (car_probability < 0.0f) car_probability = 0.0f;
  if (car_probability > 1.0f) car_probability = 1.0f;

  Serial.printf("[AI INFERENCE] Thời gian suy luận: %lu ms | Xác suất Xe (Car Prob): %.3f\n",
                infer_time, car_probability);

  return car_probability;
}

// ------------------------------------------------------------------------------
// Quản lý kết nối WiFi & MQTT
// ------------------------------------------------------------------------------
void connect_wifi_mqtt() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.print("[WIFI] Đang kết nối WiFi: ");
    Serial.println(WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    int retries = 0;
    while (WiFi.status() != WL_CONNECTED && retries < 20) {
      delay(500);
      Serial.print(".");
      retries++;
    }
    if (WiFi.status() == WL_CONNECTED) {
      Serial.printf("\n[WIFI] Đã kết nối! IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
      Serial.println("\n[CẢNH BÁO] Chưa kết nối được WiFi, chạy ở chế độ offline test.");
    }
  }

  if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) {
    mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
    Serial.print("[MQTT] Đang kết nối broker: ");
    Serial.println(MQTT_SERVER);
    if (mqttClient.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASS)) {
      Serial.println("[MQTT] Kết nối thành công!");
      // Gửi bản tin khởi động
      mqttClient.publish(TOPIC_STATUS, "{\"event\":\"ONLINE\",\"spot_id\":\"" SPOT_ID "\"}");
    }
  }
}

void publish_telemetry(const char* state, float confidence, float distance_cm, const char* reason) {
  if (!mqttClient.connected()) return;

  char payload[256];
  snprintf(payload, sizeof(payload),
           "{\"spot_id\":\"%s\",\"state\":\"%s\",\"confidence\":%.2f,\"distance_cm\":%.1f,\"reason\":\"%s\",\"uptime_s\":%lu}",
           SPOT_ID, state, confidence, distance_cm, reason, millis() / 1000);

  mqttClient.publish(TOPIC_TELEMETRY, payload);
  Serial.printf("[MQTT PUB] -> %s: %s\n", TOPIC_TELEMETRY, payload);
}

// ------------------------------------------------------------------------------
// SETUP & MAIN LOOP
// ------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=================================================");
  Serial.println("  ESP32-CAM TINYML SENSOR FUSION PARKING MONITOR  ");
  Serial.println("=================================================");

  pinMode(PIN_LED_FLASH, OUTPUT);
  pinMode(PIN_LED_BUILTIN, OUTPUT);
  digitalWrite(PIN_LED_FLASH, LOW);
  digitalWrite(PIN_LED_BUILTIN, HIGH); // Builtin LED đảo ngược (HIGH = Tắt)

  init_distance_sensor();
  init_camera();
  init_tflite_micro();
  connect_wifi_mqtt();

  Serial.println("[HỆ THỐNG] Đã sẵn sàng ở trạng thái STANDBY (Chờ xe)!\n");
}

void loop() {
  connect_wifi_mqtt();
  mqttClient.loop();

  unsigned long now = millis();
  if (now - g_last_sensor_check < SENSOR_POLL_INTERVAL_MS) {
    return;
  }
  g_last_sensor_check = now;

  // 1. Đọc cảm biến khoảng cách định kỳ
  float distance = read_distance_median();
  g_last_distance = distance;

  // 2. Máy trạng thái logic Sensor Fusion
  switch (g_current_state) {
    case STATE_IDLE_VACANT: {
      // Nếu có vật thể che chắn (khoảng cách < ngưỡng 15cm)
      if (distance < DISTANCE_THRESHOLD_CM) {
        Serial.printf("[PHÁT HIỆN] Vật cản ở khoảng cách %.1f cm (< %.1f cm). Đánh thức Camera & AI!\n",
                      distance, DISTANCE_THRESHOLD_CM);

        // Chạy suy luận CNN nhị phân
        float car_prob = run_ai_inference();

        if (car_prob >= AI_CAR_CONFIDENCE_THRESHOLD) {
          // XÁC NHẬN LÀ Ô TÔ!
          Serial.printf("[XÁC NHẬN] Ô TÔ ĐỖ! Độ tin cậy: %.2f%% (>= %.0f%%)\n",
                        car_prob * 100.0f, AI_CAR_CONFIDENCE_THRESHOLD * 100.0f);
          g_current_state = STATE_OCCUPIED_MONITORING;
          g_is_car_present = true;
          digitalWrite(PIN_LED_BUILTIN, LOW); // Bật LED báo có xe
          publish_telemetry("OCCUPIED", car_prob, distance, "CAR_DETECTED");
        } else {
          // Nhãn 0: Không có xe; không suy ra danh tính vật cản.
          Serial.printf("[KHÔNG CÓ XE] Xác suất ô tô: %.2f%% < %.0f%%. Giữ VACANT.\n",
                        car_prob * 100.0f, AI_CAR_CONFIDENCE_THRESHOLD * 100.0f);
          publish_telemetry("VACANT", car_prob, distance, "NO_CAR_DETECTED");
          // Giữ nguyên trạng thái STATE_IDLE_VACANT
          delay(800); // Chống kích hoạt liên tiếp khi vật cản còn ở gần
        }
      }
      break;
    }

    case STATE_OCCUPIED_MONITORING: {
      // Đang có xe đỗ. Kiểm tra xem xe đã rời đi chưa (khoảng cách > 15cm + 3cm hysteresis)
      if (distance > (DISTANCE_THRESHOLD_CM + DISTANCE_HYSTERESIS_CM)) {
        Serial.printf("[XE RỜI ĐI] Cảm biến báo khoảng cách %.1f cm. Ô đỗ đã TRỐNG!\n", distance);
        Serial.println("[TIẾT KIỆM NĂNG LƯỢNG] Đặt lại trạng thái TRỐNG mà KHÔNG CẦN BẬT CAMERA/AI!");

        g_current_state = STATE_IDLE_VACANT;
        g_is_car_present = false;
        digitalWrite(PIN_LED_BUILTIN, HIGH); // Tắt LED báo xe
        publish_telemetry("VACANT", 0.0f, distance, "CAR_DEPARTED_SENSOR_ONLY");
      }
      break;
    }

    default:
      g_current_state = STATE_IDLE_VACANT;
      break;
  }
}
