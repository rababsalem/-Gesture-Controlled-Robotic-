#include "esp_camera.h"
#include <WiFi.h>

// Replace with your Wi-Fi credentials
const char* ssid = "espcar";
const char* password = "55617710";

// Camera pins for ESP32-CAM AI-THINKER
#define PWDN_GPIO_NUM     32  // Modified from -1
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

#define FLASH_GPIO_NUM     4  // Flash LED pin

WiFiServer server(80);

bool startCamera() {
    // Add some initial delay
    delay(100);
  
    // Configure I2C pins with internal pullups
    pinMode(SIOD_GPIO_NUM, INPUT_PULLUP);
    pinMode(SIOC_GPIO_NUM, INPUT_PULLUP);
    
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
    config.pixel_format = PIXFORMAT_JPEG;
    
    // Try lower resolution first
    config.frame_size = FRAMESIZE_VGA;  // 640x480 
    config.jpeg_quality = 12;
    config.fb_count = 2;  // Increased from 1 to 2
    
    // Attempt hardware reset before initialization
    if (PWDN_GPIO_NUM != -1) {
        pinMode(PWDN_GPIO_NUM, OUTPUT);
        digitalWrite(PWDN_GPIO_NUM, LOW);
        delay(10);
        digitalWrite(PWDN_GPIO_NUM, HIGH);
        delay(10);
    }
    
    // Initialize camera with detailed error reporting
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed with error 0x%x\n", err);
        
        // Try with even lower resolution if first attempt failed
        if (err == ESP_ERR_NOT_FOUND) {
            Serial.println("Retrying with lower settings...");
            config.frame_size = FRAMESIZE_QVGA;  // 320x240
            config.xclk_freq_hz = 10000000;  // Lower clock frequency
            err = esp_camera_init(&config);
            
            if (err != ESP_OK) {
                Serial.printf("Second attempt failed with error 0x%x\n", err);
                return false;
            }
        } else {
            return false;
        }
    }
    
    Serial.println("Camera initialized successfully");
    return true;
}

void handleClient(WiFiClient client) {
    if (!client.connected()) {
        return;
    }
    
    String request = client.readStringUntil('\r');
    client.flush();
    
    if (request.indexOf("GET /capture") >= 0) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("Camera capture failed");
            client.println("HTTP/1.1 500 Internal Server Error");
            client.println("Content-Type: text/plain");
            client.println();
            client.println("Camera capture failed");
            return;
        }
        
        client.println("HTTP/1.1 200 OK");
        client.println("Content-Type: image/jpeg");
        client.println("Content-Length: " + String(fb->len));
        client.println();
        client.write(fb->buf, fb->len);
        
        esp_camera_fb_return(fb);
    } else {
        // Serve a simple HTML page with a button to capture
        client.println("HTTP/1.1 200 OK");
        client.println("Content-Type: text/html");
        client.println();
        client.println("<html><body>");
        client.println("<h1>ESP32-CAM Web Server</h1>");
        client.println("<a href='/capture'><button>Capture Image</button></a>");
        client.println("</body></html>");
    }
    
    client.stop();
}

void setup() {
    Serial.begin(115200);
    Serial.println("ESP32-CAM Web Server");
    
    // Set flash LED as output and turn it off
    pinMode(FLASH_GPIO_NUM, OUTPUT);
    digitalWrite(FLASH_GPIO_NUM, LOW);
    
    // Connect to WiFi
    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi");
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("\nFailed to connect to WiFi. Check credentials.");
        return;
    }
    
    Serial.println("\nWiFi connected.");
    Serial.print("ESP32-CAM IP Address: ");
    Serial.println(WiFi.localIP());
    
    // Initialize camera
    if (!startCamera()) {
        Serial.println("Failed to initialize camera. Please check hardware.");
        return;
    }
    
    // Start web server
    server.begin();
    Serial.println("HTTP server started");
}

void loop() {
    WiFiClient client = server.available();
    if (client) {
        Serial.println("New client connected");
        handleClient(client);
    }
}