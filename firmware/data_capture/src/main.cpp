 #include <Arduino.h>
#include <driver/i2s.h>
#include <Adafruit_ADXL345_U.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <ESPmDNS.h>
 #include <WiFiClientSecure.h>
#include <ESPAsyncWebServer.h>
#include <AsyncTCP.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/FreeRTOSConfig.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include "esp_heap_caps.h"
#include <Wire.h>
 #include <SPI.h>
 #include "soc/i2s_reg.h"
 #include <algorithm>
#include <vector>
#include <esp_intr_alloc.h>
#include <esp_task_wdt.h> 
#include <soc/soc.h>  
#include <esp32/clk.h>
#include <numeric>
#include <driver/i2c.h>
#include "esp_timer.h"
#include <esp_sleep.h>

//MICROPHONE SETUP////////////////////////////////////////////////////////////////////////
#define I2S_WS   6   //word Select (LRCL)
#define I2S_BCK  4   //bit Clock (BCLK)
#define I2S_DIN  21  //data Input (DOUT)
#define SAMPLE_RATE 48000
#define I2S_PORT I2S_NUM_0
#define BUFFER_SIZE_AUDIO 128//4096  
#define TOTAL_RECORDING_SECONDS 4
#define TOTAL_SAMPLES (SAMPLE_RATE * TOTAL_RECORDING_SECONDS)
#define TOTAL_BYTES (TOTAL_SAMPLES * sizeof(int32_t))

#define TEMP_BUFFER_SIZE (BUFFER_SIZE_AUDIO)
#define PERIOD_US 1250
int32_t* recordingBuffer;
volatile int recordingIndex = 0;

bool initialDiscardDone = false;
volatile int samples_captured_audio = 0;
uint64_t* audioTimestamps;


//ACCELEROMETER SETUP///////////////////////////////////////////////////////////////////////
Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);
#define SDA_PIN 3
#define SCL_PIN 2
#define ACCEL_SAMPLES_PER_SECOND 800
#define TOTAL_ACCEL_SAMPLES (ACCEL_SAMPLES_PER_SECOND * TOTAL_RECORDING_SECONDS)
#define ACCEL_BUFFER_SIZE (TOTAL_ACCEL_SAMPLES * sizeof(AccelData))


struct __attribute__((packed)) AccelData {
    uint64_t timestamp;
    float accel_x;
    float accel_y;
    float accel_z;
};

#define ACCEL_INT_PIN 6
#define ADXL345_INT_ENABLE  0x2E  //interrupt Enable Control
#define ADXL345_INT_MAP     0x2F  //interrupt Mapping Control
#define ADXL345_INT_SOURCE  0x30  //source of interrupts
const int CHECK_INTERVAL = 1000; //check data rates every second
volatile int accelDataCount = 0;
unsigned long lastCheckTime = 0;

uint8_t* accelBuffer;
volatile int accelIndex = 0;
// Calibration offsets
float x_offset = 0.0;
float y_offset = 0.0;
float z_offset = 0.0;
volatile int samples_captured_accel = 0;
//GENERAL//////////////////////////////////////////////////////////////////////////////////////

volatile bool recording = false;
volatile bool recordingAccel=false;
//have to set yours to go online
const char* ssid = ""; 
const char* password = "";
AsyncWebServer server(80);

volatile bool prep=false;
volatile bool calibrationInProgress = false;
volatile bool calibrationComplete = false;

TaskHandle_t audioTaskHandle = NULL;
TaskHandle_t accelTaskHandle = NULL;

volatile bool tasksNotified = false;  
volatile bool  accelInterruptFlag = false;  
volatile uint64_t commonStartTime_us = 0;
volatile uint64_t accelStartTime_us = 0;
volatile uint64_t audioStartTime_us = 0;
volatile uint64_t  endTime=0;
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;
esp_timer_handle_t accel_timer;
    
#define MAX_SAMPLES 3200   // max number of samples to store in PSRAM

EventGroupHandle_t xEventGroup;
#define EVENT_START (1 << 0)
#define EVENT_STOP (1 << 1)
#define EVENT_TIMER (1 << 2)
#define EVENT_AUDIO_DONE (1 << 3)
#define EVENT_ACCEL_DONE (1 << 4)
#define EVENT_FLUSH_DONE (1 << 5)
//#define configUSE_PREEMPTION 0

volatile uint64_t commonEndTime_us = 0;
volatile uint64_t accelEndTime_us = 0;

void printI2SClockSettings() {
    float i2s_clk = i2s_get_clk(I2S_NUM_0);  // Get the I2S clock frequency

    Serial.print("I2S Clock Frequency: ");
    Serial.print(i2s_clk);
    Serial.println(" Hz");

    // From this clock frequency, you can derive other settings
    // like BCLK, etc., if you know the sample rate and bits per sample.
}

void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName) {
    Serial.printf("Stack overflow detected in task: %s\n", pcTaskName);
    // Add your custom handling code here, like restarting the ESP or logging the error.
    while (1); // Halt the system or reset
}

void monitorHeap() {
    Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
    Serial.printf("Free PSRAM: %d bytes\n", ESP.getFreePsram());
}
//check actual capture rate
void check_capture_rate(unsigned long start_time_us, int samples_captured, const char* sensor_type) {
  unsigned long elapsed_time_ms = (esp_timer_get_time() - start_time_us) / 1000;
  float capture_rate = (float)samples_captured / (elapsed_time_ms / 1000.0);
  Serial.printf("Actual %s capture rate: %.2f samples per second\n", sensor_type, capture_rate);
}

/*void IRAM_ATTR onTimer()  {

    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    vTaskNotifyGiveFromISR(accelTaskHandle, &xHigherPriorityTaskWoken);
    if (xHigherPriorityTaskWoken == pdTRUE) {
        portYIELD_FROM_ISR();
    }
}*/

void onAccelTimer(void* arg) {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
   
    xTaskNotifyGive(accelTaskHandle); 

}

void calibrateAccelerometer() {
    const int num_samples = 1000;
    std::vector<float> x_samples(num_samples), y_samples(num_samples), z_samples(num_samples);

    //discard initial readings to allow sensor stabilization
    for (int i = 0; i < 20; i++) {
        sensors_event_t event;
        accel.getEvent(&event);
        delay(10);  //small delay to stabilize between samples
    }

    for (int i = 0; i < num_samples; i++) {
        sensors_event_t event;
        accel.getEvent(&event);
        x_samples[i] = event.acceleration.x;
        y_samples[i] = event.acceleration.y;
        z_samples[i] = event.acceleration.z;
        delay(10);
    }

    //calculate average values
    float x_sum = std::accumulate(x_samples.begin(), x_samples.end(), 0.0);
    float y_sum = std::accumulate(y_samples.begin(), y_samples.end(), 0.0);
    float z_sum = std::accumulate(z_samples.begin(), z_samples.end(), 0.0);

    float x_avg = x_sum / num_samples;
    float y_avg = y_sum / num_samples;
    float z_avg = z_sum / num_samples;

    //set calibration offsets
    x_offset = x_avg;
    y_offset = y_avg;
    z_offset = z_avg - 9.8;  //subtract gravity

    Serial.print("Calibration Offsets - X: "); Serial.print(x_offset);
    Serial.print(" Y: "); Serial.print(y_offset);
    Serial.print(" Z: "); Serial.println(z_offset);
}

void captureAudio(void *parameter) {
    size_t bytesRead = 0;
    size_t flushBytesRead = 0;
    int32_t tempBuffer[BUFFER_SIZE_AUDIO];
    int32_t tempBufferFlush[64];

    //allocate memory for timestamps
    audioTimestamps = (uint64_t*)malloc(TOTAL_SAMPLES * sizeof(uint64_t));
    if (audioTimestamps == NULL) {
        Serial.println("Failed to allocate memory for audioTimestamps");
        while (1);
    }

    while (true) {
        xEventGroupWaitBits(xEventGroup, EVENT_START, pdTRUE, pdFALSE, portMAX_DELAY);
     
        for (int i = 0; i < 6; i++) {
            i2s_read(I2S_PORT, (void*)tempBufferFlush, sizeof(tempBufferFlush), &flushBytesRead, portMAX_DELAY);
        }
        xEventGroupSetBits(xEventGroup, EVENT_FLUSH_DONE); 

        recording = true;

        while (recording) {
            uint64_t  startTimestamp = esp_timer_get_time() - commonStartTime_us;
            esp_err_t err = i2s_read(I2S_PORT, (uint8_t*)tempBuffer, BUFFER_SIZE_AUDIO * sizeof(int32_t), &bytesRead, portMAX_DELAY);
            if (err != ESP_OK) {
                Serial.println("Error reading from microphone");
                recording = false;
                break;
            }

            size_t samplesRead = bytesRead / sizeof(int32_t); //number of samples read
            float timePerSample = 1000000.0 / SAMPLE_RATE; //time per sample in microseconds
            //interpolate timestamps for each sample in the buffer
            for (size_t i = 0; i < samplesRead; i++) {
                audioTimestamps[recordingIndex + i] = startTimestamp + (uint64_t)(i * timePerSample);
            }

            size_t remainingSamples = TOTAL_SAMPLES - recordingIndex;

            if (samplesRead > remainingSamples) {
                memcpy(recordingBuffer + recordingIndex, tempBuffer, remainingSamples * sizeof(int32_t));
                recordingIndex += remainingSamples;
                samples_captured_audio += remainingSamples;
                recording = false;
                xEventGroupSetBits(xEventGroup, EVENT_AUDIO_DONE);
                break;
            } else {
                memcpy(recordingBuffer + recordingIndex, tempBuffer, samplesRead * sizeof(int32_t));
                recordingIndex += samplesRead;
                samples_captured_audio += samplesRead;
            }

            //stop event or buffer overflow
            EventBits_t uxBits = xEventGroupGetBits(xEventGroup);
            if (recordingIndex >= TOTAL_SAMPLES || (uxBits & EVENT_STOP)) {
                recording = false;
                xEventGroupSetBits(xEventGroup, EVENT_AUDIO_DONE);
                break;
            }
            
        }
        
    }
}

void discardInitialAccelReadings() {
     sensors_event_t event;
    
    //discard initial accelerometer readings (for stabilization)
    for (int i = 0; i < 2000; i++) {
        if (accel.getEvent(&event)) {
            
        }
        delay(3);  
    }
}

void checkDataRates() {
    unsigned long currentTime = millis();
    if (currentTime - lastCheckTime >= CHECK_INTERVAL) {
        Serial.printf("Accelerometer data: expected %d, got %d\n", 1600, accelDataCount);
        accelDataCount = 0;
        lastCheckTime = currentTime;
    }
}

void captureAccel(void *parameter) {
    uint64_t timestamp = 0;
    while (true) {
        xEventGroupWaitBits(xEventGroup, EVENT_FLUSH_DONE, pdTRUE, pdFALSE, portMAX_DELAY);
        timestamp = esp_timer_get_time() - commonStartTime_us;
            sensors_event_t event;
            accel.getEvent(&event);
            esp_timer_start_periodic(accel_timer, 1250);
            AccelData accel_data = {
                timestamp,
                event.acceleration.x - x_offset,
                event.acceleration.y - y_offset,
                event.acceleration.z - z_offset
            };
            memcpy(accelBuffer + accelIndex, &accel_data, sizeof(AccelData));
            accelIndex += sizeof(AccelData);
            recordingAccel=true;
        while (recordingAccel) {
            ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
            timestamp = esp_timer_get_time() - commonStartTime_us;
            sensors_event_t event;
            accel.getEvent(&event);
            AccelData accel_data = {
                timestamp,
                event.acceleration.x - x_offset,
                event.acceleration.y - y_offset,
                event.acceleration.z - z_offset
            };
            memcpy(accelBuffer + accelIndex, &accel_data, sizeof(AccelData));
            accelIndex += sizeof(AccelData);
            
            EventBits_t uxBits = xEventGroupWaitBits(xEventGroup, EVENT_STOP, pdTRUE, pdFALSE, 0);
            if (accelIndex >= MAX_SAMPLES * sizeof(AccelData) || (uxBits & EVENT_STOP)) {
                recordingAccel = false;
                xEventGroupSetBits(xEventGroup, EVENT_ACCEL_DONE);
                break;
            }
        }
    
    }
}

void discardInitialAudioReadings() {
    int32_t tempBuffer[1000];
    size_t bytesRead;
    for (int i = 0; i < 1000; i++) {
        i2s_read(I2S_PORT, (void*)tempBuffer, 1000 * sizeof(int32_t), &bytesRead, portMAX_DELAY);
    }
}

void serveRecordedData(AsyncWebServerRequest *request) {
    if (!recording && recordingIndex > 0) {
        size_t dataSize = recordingIndex * sizeof(int32_t);
        AsyncWebServerResponse *response = request->beginResponse_P(200, "application/octet-stream", (const uint8_t*)recordingBuffer, dataSize);
        response->addHeader("Content-Disposition", "attachment; filename=recording.raw");
        response->addHeader("X-File-Size", String(dataSize));
        response->addHeader("X-Common-Start-Time", String(commonStartTime_us));
        response->addHeader("X-Common-End-Time", String(commonEndTime_us)); 
        request->send(response);
        Serial.println("Audio buffer sent and cleared, ready for new recording");
    } else {
        request->send(400, "text/plain", "No recording available or still recording");
    }
}

void serveAudioTimestamps(AsyncWebServerRequest *request) {
    if (!recording && recordingIndex > 0) {
        size_t dataSize = recordingIndex * sizeof(uint64_t);
        AsyncWebServerResponse *response = request->beginResponse_P(200, "application/octet-stream", (const uint8_t*)audioTimestamps, dataSize);
        response->addHeader("Content-Disposition", "attachment; filename=audio_timestamps.txt");
        response->addHeader("X-File-Size", String(dataSize));
        request->send(response);
        Serial.println("Audio timestamps sent.");
    } else {
        request->send(400, "text/plain", "No timestamps available or still recording");
    }
}

void serveAccelData(AsyncWebServerRequest *request) {
     if (!recordingAccel && accelIndex > 0) {
        size_t dataSize = accelIndex;  //# of bytes in the buffer
        Serial.printf("Sending %d bytes of accelerometer data\n", dataSize);
        //serve the data as an octet stream
        AsyncWebServerResponse *response = request->beginResponse_P(200, "application/octet-stream", (const uint8_t*)accelBuffer, dataSize);
        response->addHeader("Content-Disposition", "attachment; filename=accelerometer.dat");
        response->addHeader("X-File-Size", String(dataSize));
        request->send(response);  
        Serial.println("Accelerometer data sent");
    } else {
        request->send(400, "text/plain", "No accelerometer data available or still recording");
        Serial.println("Failed to serve accelerometer data. Either still recording or no data available.");
    }
}

void printBinary(int32_t value) {
    for (int i = 31; i >= 0; i--) {
        Serial.print((value >> i) & 1);
    }
}

void captureAndPrintAudio() {
    int32_t i2s_buffer[512];
    size_t bytes_read;

    i2s_read(I2S_PORT, (void*)i2s_buffer, 512 * sizeof(int32_t), &bytes_read, portMAX_DELAY);
    int num_samples = bytes_read / sizeof(int32_t);
    //print the binary values of both channels
    for (int i = 0; i < num_samples; i += 2) {
        int32_t left_channel = i2s_buffer[i];
        int32_t right_channel = i2s_buffer[i + 1];

        Serial.print("Left: ");
        printBinary(left_channel);
        Serial.print(" | Right: ");
        printBinary(right_channel);
        Serial.println();
    }
}

void setup() {

    setCpuFrequencyMhz(240);

    Serial.begin(115200);
    Wire.begin(SDA_PIN, SCL_PIN,400000);
    
    Serial.println("Initializing WiFi...");
    WiFi.begin(ssid, password);

    unsigned long startTime = millis();
    unsigned long timeout = 30000; // 30 seconds timeout

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
        if (millis() - startTime >= timeout) {
            Serial.println("\nFailed to connect to WiFi within the timeout period");
            return;
        }
        yield(); // allow background tasks to run
    }

    esp_wifi_set_ps(WIFI_PS_NONE);

    Serial.println("\nConnected to WiFi");
    
    //initialize accelerometer
    Wire.setClock(400000);
    if (!accel.begin()) {
        Serial.println("No ADXL345 detected ... Check your wiring!");
        while (1);
    }

    accel.setDataRate(ADXL345_DATARATE_800_HZ);
    accel.setRange(ADXL345_RANGE_2_G);
    accel.writeRegister(ADXL345_REG_BW_RATE, ADXL345_DATARATE_800_HZ);
    Wire.setClock(400000);
    Serial.println("ADXL345 setup complete.");
    dataRate_t rate = accel.getDataRate();
    Serial.print("Current data rate: ");
    Serial.println(rate);
    
    //initialize I2S
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,  //Use LEFT channel configuration
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 3,
        .dma_buf_len = BUFFER_SIZE_AUDIO,
        .use_apll = true,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 12288000, //BCLK of 3.072 MHz required for 48kHz with 32 bit stereo
    };


    i2s_pin_config_t pin_config = {
        .bck_io_num = I2S_BCK,
        .ws_io_num = I2S_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_DIN
    };

    if (i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL) != ESP_OK) {
        Serial.println("Failed to install I2S driver");
        while (1);
    }

    //Delay by falling edge
    REG_SET_BIT(I2S_RX_TIMING_REG(I2S_PORT), BIT(9));
    //Force Philips mode
    REG_SET_BIT(I2S_RX_CONF1_REG(I2S_PORT), I2S_RX_MSB_SHIFT);

    if (i2s_set_pin(I2S_PORT, &pin_config) != ESP_OK) {
        Serial.println("Failed to set I2S pin configuration");
        while (1);
    }

    if (i2s_set_sample_rates(I2S_PORT, SAMPLE_RATE) != ESP_OK) {
        Serial.println("Failed to set I2S sample rate");
        while (1);
    }

    i2s_set_clk(I2S_PORT, SAMPLE_RATE, I2S_BITS_PER_SAMPLE_32BIT, I2S_CHANNEL_MONO);

    //allocate the recording buffer in PSRAM
    recordingBuffer = (int32_t*)heap_caps_malloc(TOTAL_BYTES, MALLOC_CAP_SPIRAM);
    if (recordingBuffer == NULL) {
        Serial.println("Failed to allocate audio buffer in PSRAM");
        while (1); 
    } else {
        Serial.printf("Allocated audio buffer at address: %p\n", recordingBuffer);
    }

   accelBuffer = (uint8_t*) malloc(MAX_SAMPLES * (8 + 4 * 3));
    if (accelBuffer == nullptr) {
        Serial.println("Failed to allocate memory for accelBuffer in SRAM");
        while (true);  
    }

    // Set up HTTP server
    server.on("/prep", HTTP_GET, [](AsyncWebServerRequest *request){
        if (!calibrationInProgress) {
            prep = true;  //set flag to start calibration in loop
            calibrationInProgress = true;
            calibrationComplete = false;
            request->send(200, "text/plain", "Calibration started.");
        } else {
            request->send(200, "text/plain", "Calibration already in progress.");
        }
    });

    server.on("/status", HTTP_GET, [](AsyncWebServerRequest *request){
        if (calibrationComplete) {
            request->send(200, "text/plain", "Calibration complete.");
        } else if (calibrationInProgress) {
            request->send(200, "text/plain", "Calibration in progress.");
        } else {
            request->send(200, "text/plain", "No calibration in progress.");
        }
    });

    server.on("/start", HTTP_GET, [](AsyncWebServerRequest *request){
        if (calibrationComplete) {
            recordingIndex = 0;
            accelIndex = 0;
            samples_captured_accel=0;
            samples_captured_audio=0;
            xEventGroupClearBits(xEventGroup, EVENT_START | EVENT_STOP | EVENT_AUDIO_DONE | EVENT_ACCEL_DONE |EVENT_FLUSH_DONE);
            esp_timer_stop(accel_timer);  
            if (xEventGroup != NULL) {
                commonStartTime_us = esp_timer_get_time();
                xEventGroupSetBits(xEventGroup, EVENT_START);
            }
            request->send(200, "text/plain", "Recording started");
        } else {
            request->send(400, "text/plain", "Calibration not complete. Cannot start recording.");
        }
    });

    server.on("/stop", HTTP_GET, [](AsyncWebServerRequest *request){
        if (xEventGroup != NULL) {
        xEventGroupSetBits(xEventGroup, EVENT_STOP);
        //wait until both tasks are done
        xEventGroupWaitBits(xEventGroup, EVENT_AUDIO_DONE | EVENT_ACCEL_DONE, pdTRUE, pdTRUE, portMAX_DELAY);
        commonEndTime_us = esp_timer_get_time();
    
        
    }
        request->send(200, "text/plain", "Recording stopped");
    });

    server.on("/download", HTTP_GET, [](AsyncWebServerRequest *request){
        serveRecordedData(request);
    });

    server.on("/download_audio_timestamps", HTTP_GET, [](AsyncWebServerRequest *request){
        serveAudioTimestamps(request);
    });

    server.on("/download_accel", HTTP_GET, [](AsyncWebServerRequest *request){
        serveAccelData(request);
        
    });

    server.begin();

    
   
    discardInitialAudioReadings();
    discardInitialAccelReadings();
    initialDiscardDone = true;

    
    xEventGroup = xEventGroupCreate();
    if (xEventGroup == NULL) {
        Serial.println("Failed to create event group!");
        while(1); 
    }
   
    BaseType_t result;
    result = xTaskCreatePinnedToCore(captureAudio, "CaptureAudio", 8192 , NULL, 10 , &audioTaskHandle, 1);
    if (result != pdPASS) {
        Serial.println("Failed to create CaptureAudio task");
        while (1); 
    }
    result = xTaskCreatePinnedToCore(captureAccel, "CaptureAccel", 4096, NULL,configMAX_PRIORITIES - 1, &accelTaskHandle, 0);
    if (result != pdPASS) {
        Serial.println("Failed to create CaptureAccel task");
        while (1); 
    }

    esp_timer_create_args_t timer_args = {
        .callback = &onAccelTimer,   //function to call when the timer triggers
        .arg = NULL,                 
        .name = "accel_timer"       
    };

    esp_timer_create(&timer_args, &accel_timer);
    esp_timer_start_periodic(accel_timer, 1250);  //set the timer to trigger periodically at 1250 microseconds (800 Hz)

    float i2s_clk = i2s_get_clk(I2S_PORT);
    Serial.printf("I2S Clock Frequency: %.2f Hz\n", i2s_clk);

}

void loop() {


    if(prep && initialDiscardDone){
        
        calibrateAccelerometer();
        
        prep=false;
        calibrationInProgress = false;
        calibrationComplete = true;
        Serial.println("Calibration and initial discard done.");
      
    }

  
   
}