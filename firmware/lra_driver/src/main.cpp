/* set up the DA7280 Haptic Driver Library */
#include "Wire.h"
#include "Haptic_Driver.h"
#include "Arduino.h"
#include <SPIFFS.h>
#include <vector>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"

#define interruptPin 42


const char* ssid = "ESP32_AP";
const char* password = "12345678";
WiFiUDP udp;
unsigned int localUdpPort = 12345; //local port to listen on
char incomingPacket[128]; //buffer for incoming packets

Haptic_Driver haptic; 

volatile bool contact = false;
volatile float currentVelocity = 0;
volatile bool currentStateModulation = false;
size_t currentRowIndex = 0; 

float velocity = 0; 
bool loadingCSV = false;
File csvFile;
const unsigned long csvLoadChunkDuration = 1000000; //max duration for each chunk
unsigned long lastPacketTime = 0; //time of the last packet
unsigned long packetInterval = 0; //interval between packets
String currentTextureTag = ""; 

hw_timer_t* timer = NULL; 
TaskHandle_t taskUDPHandle = NULL;
TaskHandle_t taskHapticControlHandle = NULL;
volatile float baseVelocity = 1.0;     
float v_min = 0.05;
float v_max = 0.4;
SemaphoreHandle_t dataRowsMutex;
SemaphoreHandle_t sharedVarMutex;

struct DataRow {
  float frequency;
  int amplitude;
 
};

std::vector<DataRow> dataRows;

void processCSVLine(String line) {
   DataRow row;
  int commaIndex = line.indexOf(',');
  if (commaIndex != -1 ) {
    row.frequency = line.substring(0, commaIndex).toFloat(); //extract frequency
    row.amplitude = line.substring(commaIndex + 1).toInt(); //extract amplitude
    dataRows.push_back(row); //add row to dataRows vector
  } else {
    Serial.println("Malformed CSV line, skipping...");
  }
  
}

void readCSVFile(const char* path) {
  xSemaphoreTake(dataRowsMutex, portMAX_DELAY); //lock the mutex before modifying dataRows
  dataRows.clear(); //clear existing data
  csvFile = SPIFFS.open(path, "r");
  if (!csvFile) {
    Serial.println("Failed to open file for reading");
    xSemaphoreGive(dataRowsMutex); //unlock the mutex in case of failure
    return;
  }
  String headerLine = csvFile.readStringUntil('\n'); //skip the header line
  while (csvFile.available()) {
    String line = csvFile.readStringUntil('\n');
    if (line.length() > 0) {
      processCSVLine(line);
    }
  }
  csvFile.close();
  currentRowIndex = 0; // reset the row index for the new file
  //Serial.printf("CSV file loaded with %u rows.\n", dataRows.size());
  xSemaphoreGive(dataRowsMutex); //unlock the mutex after modifying dataRows
  //loadingCSV = true;
 // Serial.println("Started loading CSV file..");
}

/*void processNextCSVChunk() {
  unsigned long currentMicros = micros();
  unsigned int linesProcessed = 0;

  while (csvFile.available() && (micros() - currentMicros) < csvLoadChunkDuration) {
    String line = csvFile.readStringUntil('\n');
    if (line.length() > 0) { // Ensure we read a valid line
      processCSVLine(line);
      linesProcessed++;
    }
  }
  if (!csvFile.available()) {
    csvFile.close();
    loadingCSV = false;
    currentRowIndex = 0;
    Serial.printf("CSV file loaded with %u rows.\n", dataRows.size());
  }
}*/

/*void csvLoadingTask(void *parameter) {
  while (true) {
    if (loadingCSV) {
      processNextCSVChunk();
      xTaskNotifyGive(taskHapticControlHandle);
      //vTaskDelay(1); 
    } else {
      vTaskDelay(10); //no CSV loading, delay 
    }
  }
}*/

int calculateDelay(float velocity, float baseVelocity, int minDelay = 10, int maxDelay = 50) {
    
    int baseDelay = 20; //aligned with the 20 ms feature extraction window
    //adjust delay based on the ratio of the current velocity to the base velocity
    float delayFactor = baseVelocity / std::max(velocity, 0.001f); //avoid division by zero
    int adjustedDelay = static_cast<int>(baseDelay * delayFactor);
    return std::max(minDelay, std::min(adjustedDelay, maxDelay)); //clamp the delay to ensure it stays within perceptible and stable limits
}

int mapAmplitude(int amplitude, float velocity) {
    return (int)(amplitude * velocity * velocity);
}

float mapFrequency(float frequency, float velocity) {
    return frequency + (velocity * 5);  
}

void controlLRA(const DataRow& row, float velocity, float baseVelocity, bool useModulation) {
    int adjustedAmplitude;
    float adjustedFrequency;
    int adjustedDelay;

    if (useModulation) {
        float normalizedVelocity  = std::max(0.0f, std::min(1.0f, (velocity - v_min) / (v_max - v_min)));
        //adjust amplitude and frequency based on velocity
        adjustedAmplitude = mapAmplitude(row.amplitude, normalizedVelocity);
        adjustedFrequency = mapFrequency(row.frequency, normalizedVelocity);
        adjustedDelay = calculateDelay(velocity, baseVelocity); //calculate delay based on velocity
    } else {
        //use default values for static mode
        adjustedAmplitude = row.amplitude;  
        adjustedFrequency = row.frequency; 
        adjustedDelay = 20;                
    }

    haptic.setActuatorLRAfreq(adjustedFrequency);
    haptic.setVibrate(adjustedAmplitude);
    vTaskDelay(adjustedDelay);
}
    
void handleIncomingPacket() {

  int packetSize = udp.parsePacket();
  if (packetSize) {
    int len = udp.read(incomingPacket, sizeof(incomingPacket));
    if (len > 0) {
      incomingPacket[len] = 0;
    }
     
    //parse incoming packet
    String packet = String(incomingPacket);
    int firstCommaIndex = packet.indexOf(',');
    int secondCommaIndex = packet.indexOf(',', firstCommaIndex + 1);
    int thirdCommaIndex = packet.indexOf(',', secondCommaIndex + 1);

    if (firstCommaIndex == -1 || secondCommaIndex == -1 || thirdCommaIndex == -1) {
      Serial.println("Malformed packet");
      Serial.print("Received packet: ");
      Serial.println(packet);
      return;
    }

    String command = packet.substring(0, firstCommaIndex);
    command.trim();
    String textureTag = packet.substring(firstCommaIndex + 1, secondCommaIndex);
    textureTag.trim();
    float receivedVelocity = packet.substring(secondCommaIndex + 1, thirdCommaIndex).toFloat();
    String modulationStateString = packet.substring(thirdCommaIndex + 1);
    modulationStateString.trim();

    bool receivedStateModulation  = false;
    if (modulationStateString == "true") {
        receivedStateModulation  = true;
    } else if (modulationStateString == "false") {
        receivedStateModulation  = false;
    } else {
        Serial.println("Invalid modulation state received, defaulting to false");
    }

    unsigned long currentPacketTime = millis();
    packetInterval = currentPacketTime - lastPacketTime;
    lastPacketTime = currentPacketTime;

    //Serial.printf("Received command: %s, TextureTag: %s, Velocity: %f, Packet Interval: %lu ms\n",command.c_str(), textureTag.c_str(), receivedVelocity, packetInterval);
    //Serial.printf("Received tag: %s (Length: %d)\n", textureTag.c_str(), textureTag.length());
    //Serial.printf("Received command: %s (Length: %d)\n", command.c_str(), command.length());
    //int64_t receivedTimestamp = strtoll(packet.substring(thirdCommaIndex + 1, fourthCommaIndex).c_str(), NULL, 10);
    
    xSemaphoreTake(sharedVarMutex, portMAX_DELAY);
    if (command == "enter" || command == "stay") {
        currentVelocity = receivedVelocity;
        currentStateModulation = receivedStateModulation ;
        contact = true;
      if (textureTag != currentTextureTag) {
        currentTextureTag = textureTag;
        if (textureTag == "1") {
          baseVelocity=0.0146;
          readCSVFile("/1.csv");
        } else if (textureTag == "2") {
          baseVelocity=0.0106;
          readCSVFile("/2.csv");
        } else if (textureTag == "3") {
          baseVelocity=0.0039;
          readCSVFile("/3.csv");
        } else if (textureTag == "4") {
          baseVelocity=0.0146;
          readCSVFile("/4.csv");
        } else if (textureTag == "5") {
          baseVelocity=0.0106;
          readCSVFile("/5.csv");
        } else if (textureTag == "6") {
          baseVelocity=0.0039;
          readCSVFile("/6.csv");
        } else if (textureTag == "7") {
          baseVelocity=0.0146;
          readCSVFile("/7.csv");
        } else if (textureTag == "8") {
          baseVelocity=0.0106;
          readCSVFile("/8.csv");
        } else if (textureTag == "9") {
          baseVelocity=0.0039;
          readCSVFile("/9.csv");
        } else if (textureTag == "10") {
          baseVelocity=0.0146;
          readCSVFile("/10.csv");
        } else if (textureTag == "11") {
          baseVelocity=0.0106;
          readCSVFile("/11.csv");
        } else if (textureTag == "12") {
          baseVelocity=0.0039;
          readCSVFile("/12.csv");
        } else if (textureTag == "13") {
          baseVelocity=0.0146;
          readCSVFile("/13.csv");
        } else if (textureTag == "14") {
          baseVelocity=0.0106;
          readCSVFile("/14.csv");
        } else if (textureTag == "15") {
          baseVelocity=0.0039;
          readCSVFile("/15.csv");
        } else if (textureTag == "16") {
          baseVelocity=0.0146;
          readCSVFile("/16.csv");
        } else if (textureTag == "17") {
          baseVelocity=0.0106;
          readCSVFile("/17.csv");
        } else if (textureTag == "18") {
          baseVelocity=0.0039;
          readCSVFile("/18.csv");
          }
      }
    } else if (command == "exit") {
        contact = false;
        haptic.setVibrate(0); //stop vibration 
    }
      
    xSemaphoreGive(sharedVarMutex);
      //Serial.printf("Received packet: %s, Command: %s, TextureTag: %s, Velocity: %f\n",incomingPacket, command.c_str(), textureTag.c_str(), receivedVelocity, receivedStateModulation);

    udp.beginPacket(udp.remoteIP(), udp.remotePort());
    udp.printf("Acknowledged: %s", incomingPacket);
    udp.endPacket();  
  }
}

void handleUdpTask(void *parameter) {
  while (true) {
    handleIncomingPacket();
    vTaskDelay(1);
  }
}

void hapticControlTask(void *parameter) {
  while (true) {
    //lock shared variables
    xSemaphoreTake(sharedVarMutex, portMAX_DELAY);
    bool isContact = contact;
    float velocity = currentVelocity;
    bool useModulation = currentStateModulation;
    xSemaphoreGive(sharedVarMutex);

    if (isContact && !dataRows.empty()) {
        //lock dataRows
        xSemaphoreTake(dataRowsMutex, portMAX_DELAY);
        DataRow row = dataRows[currentRowIndex];
        xSemaphoreGive(dataRowsMutex);
        controlLRA(row, velocity, baseVelocity, useModulation); //control LRA based on current row and velocity
        xSemaphoreTake(sharedVarMutex, portMAX_DELAY);
        currentRowIndex = (currentRowIndex + 1) % dataRows.size();
        xSemaphoreGive(sharedVarMutex);
    } else {
      //noo contact or dataRows empty; stop feedback
      haptic.setVibrate(0);
      vTaskDelay(pdMS_TO_TICKS(1));
    }
  }
}

void initializeHapticDriver() {
  if (!haptic.begin()) {
    Serial.println("Could not communicate with Haptic Driver.");
    return;  
  }

  Serial.println("Qwiic Haptic Driver DA7280 found!");

  if (!haptic.defaultMotor()) {
    Serial.println("Could not set default settings.");
  }

  haptic.setActuatorType(LRA_TYPE);
  haptic.setOperationMode(DRO_MODE);
  haptic.enableAcceleration(false);
  haptic.enableRapidStop(false);
  haptic.enableFreqTrack(false);
  haptic.setBemf(0);
}

bool checkLRAStatus() {
    Wire.beginTransmission(DEF_ADDR);
    byte error = Wire.endTransmission();
    return (error == 0);  
  }

void setup() {

  pinMode(3, PULLUP);
  pinMode(2, PULLUP);
  
  Serial.begin(115200);
  Serial.println("Tick rate: " + String(configTICK_RATE_HZ));

  //initialize Wi-Fi as an AP
  WiFi.softAP(ssid, password);
  IPAddress IP = WiFi.softAPIP();
  Serial.print("AP IP address: ");
  Serial.println(IP);

  if (!udp.begin(localUdpPort)) {
    Serial.println("Failed to start UDP");
    return;
  }

  Serial.printf("Now listening at IP %s, UDP port %d\n", IP.toString().c_str(), localUdpPort);

  if (!Wire.begin(3,2,400000)) {
    Serial.println("Failed to initialize I2C bus.");  
  }

  initializeHapticDriver();

  //initialize SPIFFS
  if (!SPIFFS.begin(true)) {
   Serial.println("An error has occurred while mounting SPIFFS");
    return;
  }

  Serial.println("SPIFFS mounted successfully");

  haptic.setVibrate(0);

  sharedVarMutex = xSemaphoreCreateMutex();  //initialize the mutex for shared variables
  dataRowsMutex = xSemaphoreCreateMutex();   //initialize the mutex for dataRows access
  if (sharedVarMutex == NULL || dataRowsMutex == NULL) {
    Serial.println("Failed to create mutex");
    return;
  }

  xTaskCreatePinnedToCore(handleUdpTask, "Handle UDP Task", 4096, NULL, 10, &taskUDPHandle, 0);
  xTaskCreatePinnedToCore(hapticControlTask, "Haptic Control Task", 4096, NULL, 10, &taskHapticControlHandle, 1);
  //xTaskCreatePinnedToCore(csvLoadingTask, "CSV Loading Task", 4096, NULL, 1, NULL, 1);
}

void loop() {

  haptic.clearIrq(haptic.getIrqEvent());
  
  if (!checkLRAStatus()) {
    Serial.println("Lost communication with DA7280. Attempting reconnection...");
    while (!checkLRAStatus()) {
      delay(1000);  
      Wire.begin(3, 2, 100000);  //re-initialize I2C bus
    }
    Serial.println("DA7280 reconnected. Reinitializing...");
    initializeHapticDriver();  
  }

  vTaskDelay(1);
} 

