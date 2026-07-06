// Arduino Code
#include <SoftwareSerial.h>
SoftwareSerial espSerial(10, 11); // RX, TX
unsigned long lastReceivedTime = 0;

// Motor A connections
int enA = 9; //speed control
int in1 = 8; //direction control
int in2 = 7;

// Motor B connections
int enB = 3;
int in3 = 5;
int in4 = 4;

void Stop() {
    analogWrite(enA, 0);
    analogWrite(enB, 0);
    digitalWrite(in1, LOW);
    digitalWrite(in2, LOW);
    digitalWrite(in3, LOW);
    digitalWrite(in4, LOW);
}

void Move_Forward(int speed) {
    digitalWrite(in1, HIGH);
    digitalWrite(in2, LOW);
    digitalWrite(in3, HIGH);
    digitalWrite(in4, LOW);
    analogWrite(enA, speed);
    analogWrite(enB, speed);
}

void Move_Back(int speed) {
    digitalWrite(in1, LOW);
    digitalWrite(in2, HIGH);
    digitalWrite(in3, LOW);
    digitalWrite(in4, HIGH);
    analogWrite(enA, speed);
    analogWrite(enB, speed);
}

void Move_Right(int speed) {
    digitalWrite(in1, HIGH);
    digitalWrite(in2, LOW);
    digitalWrite(in3, LOW);
    digitalWrite(in4, LOW);
    analogWrite(enA, speed);
    analogWrite(enB, speed);
}

void Move_Left(int speed) {
    digitalWrite(in1, LOW);
    digitalWrite(in2, LOW);
    digitalWrite(in3, HIGH);
    digitalWrite(in4, LOW);
    analogWrite(enA, speed);
    analogWrite(enB, speed);
}

void setup() {
    Serial.begin(115200); //connect to the computer 
    espSerial.begin(115200); //connect to the ESP8266
    pinMode(in1, OUTPUT);
    pinMode(in2, OUTPUT);
    pinMode(in3, OUTPUT);
    pinMode(in4, OUTPUT);
    pinMode(enA, OUTPUT);
    pinMode(enB, OUTPUT);
    Stop();
}

void loop() {
    if (espSerial.available()) {
        String command = espSerial.readStringUntil('\n');
        command.trim();
        Serial.println("Received: " + command);
        espSerial.println("Received: " + command);
        
        if (command == "0") Stop();
        else if (command == "1") Move_Forward(64); //low speed 
        else if (command == "2") Move_Forward(128);
        else if (command == "3") Move_Forward(192);
        else if (command == "4") Move_Forward(255); //high speed
        else if (command == "5") Move_Back(64);
        else if (command == "6") Move_Back(128);
        else if (command == "7") Move_Back(192);
        else if (command == "8") Move_Back(255);
        else if (command == "9") Move_Right(64);
        else if (command == "a") Move_Right(128);
        else if (command == "b") Move_Right(192);
        else if (command == "c") Move_Right(255);
        else if (command == "d") Move_Left(64);
        else if (command == "e") Move_Left(128);
        else if (command == "f") Move_Left(192);
        else if (command == "g") Move_Left(255);
        else {
            Serial.println("Invalid Command: " + command); 
            espSerial.println("Invalid Command"+ command);
        }
        lastReceivedTime = millis();
    }

    if (millis() - lastReceivedTime > 1000) {
        Stop(); //safety stop if no command received for 1 second
        Serial.println("Car Disconnected!");
        espSerial.println("Car Disconnected");
        lastReceivedTime = millis();
    }
}
