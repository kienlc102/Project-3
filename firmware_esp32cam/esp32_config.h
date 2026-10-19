/**
 * CẤU HÌNH HỆ THỐNG GIÁM SÁT Ô ĐỖ XE TINYML ESP32-CAM
 * Bao gồm cấu hình Camera AI-Thinker, Cảm biến khoảng cách (HC-SR04/VL53L0X),
 * WiFi, MQTT Broker và các ngưỡng thuật toán.
 */

#ifndef ESP32_CONFIG_H_
#define ESP32_CONFIG_H_

// ==============================================================================
// 1. CẤU HÌNH WIFI & MQTT BROKER
// ==============================================================================
#define WIFI_SSID             "Your_WiFi_SSID"
#define WIFI_PASSWORD         "Your_WiFi_Password"

// MQTT Broker (Có thể dùng public broker như broker.emqx.io hoặc Mosquitto local)
#define MQTT_SERVER           "broker.emqx.io"
#define MQTT_PORT             1883
#define MQTT_CLIENT_ID        "ESP32CAM_Parking_Spot_01"
#define MQTT_USER             ""
#define MQTT_PASS             ""

// MQTT Topics
#define SPOT_ID               "spot_01"
#define TOPIC_TELEMETRY       "parking/spot_01/telemetry"
#define TOPIC_STATUS          "parking/spot_01/status"
#define TOPIC_IMAGE           "parking/spot_01/image"

// ==============================================================================
// 2. CẤU HÌNH CHÂN PHẦN CỨNG (AI-THINKER ESP32-CAM PINOUT)
// ==============================================================================
// Chân điều khiển Camera OV2640 (Chuẩn AI-Thinker)
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Chân điều khiển Cảm biến siêu âm HC-SR04 (Hoặc ToF VL53L0X)
// Lưu ý: GPIO 13 dùng làm Trigger; GPIO 12 dùng làm Echo (cần qua cầu phân áp 5V->3.3V)
#define PIN_TRIG          13
#define PIN_ECHO          12

// Đèn Flash LED trên ESP32-CAM (GPIO 4) & LED báo trạng thái đỏ (GPIO 33 nghịch đảo)
#define PIN_LED_FLASH      4
#define PIN_LED_BUILTIN   33

// ==============================================================================
// 3. THUẬT TOÁN & NGƯỠNG KÍCH HOẠT (SENSOR FUSION LOGIC)
// ==============================================================================
// Ngưỡng khoảng cách phát hiện có vật thể che chắn (đơn vị: cm trên sa bàn)
#define DISTANCE_THRESHOLD_CM       15.0f

// Độ trễ trễ (Hysteresis) chống rung nhiễu khi xe mấp mé mép cảm biến
#define DISTANCE_HYSTERESIS_CM      3.0f

// Ngưỡng xác suất AI phân loại "Ô tô" (Confidence > 0.75 -> Có xe)
#define AI_CAR_CONFIDENCE_THRESHOLD 0.75f

// Chu kỳ đọc cảm biến ở trạng thái ngủ/chờ (ms)
#define SENSOR_POLL_INTERVAL_MS     250

// Kích thước Tensor Arena cấp phát cho TensorFlow Lite Micro
#define TENSOR_ARENA_SIZE           (28 * 1024)  // 28 KB

#endif // ESP32_CONFIG_H_
