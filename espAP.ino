// ESP8266 Code
#include <ESP8266WiFi.h>
#include <WiFiClient.h>
#include <ESP8266WiFiMulti.h>

ESP8266WiFiMulti wifiMulti;
WiFiServer server(80);
WiFiClient client;

const char *ssid = "espcar";
const char *password = "55617710";

void setup() {
    Serial.begin(115200);
    WiFi.softAP(ssid, password); //create wifi network
    server.begin(); //start server
}

void loop() {
    if (!client || !client.connected()) {
        client = server.available();
        return; // Wait for a client to connect before proceeding
    }

    if (client.available()) {
        String msg = client.readStringUntil('\n'); //read from wifi
        msg.trim();
        if (msg.length() > 0) {
            Serial.println(msg); //TX to Arduino
            
        }
    }

    if (Serial.available()) {
        String arduinoMsg = Serial.readStringUntil('\n');
        arduinoMsg.trim();
        client.println(arduinoMsg);
    }
}
