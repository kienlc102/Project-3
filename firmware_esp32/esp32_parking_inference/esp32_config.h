#pragma once

// ESP32 DevKit / ESP32-WROOM, external wide-angle camera handled by gateway.
#define WIFI_SSID "Your_WiFi_SSID"
#define WIFI_PASSWORD "Your_WiFi_Password"
#define HTTP_PORT 80
#define DEFAULT_CAR_THRESHOLD 0.75f

// Initial budget, NOT a measured requirement. Check AllocateTensors and free heap.
#define TENSOR_ARENA_SIZE (160 * 1024)
#define INPUT_BYTES (64 * 64)
