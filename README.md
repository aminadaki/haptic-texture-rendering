# Multisensory Haptic Texture Rendering System

Implementation of the diploma thesis  
*A Wireless Haptic System for Multisensory Texture Data Capture and Vibrotactile Feedback Representation in Virtual Reality*  
Technical University of Crete

This project explores how real-world texture interactions can be captured and reproduced through vibrotactile feedback in virtual environments.

The system records synchronized audio and acceleration signals during fingertip interaction with physical textures. Signal features are extracted and mapped to vibration parameters that drive a Linear Resonant Actuator (LRA) during real-time interaction in Unity. Instead of replaying full recorded signals, the system uses compact feature representations to generate responsive haptic feedback.

---

## System Overview

The system consists of three main stages:

```
Physical Texture Interaction
        ↓
Audio + Accelerometer Capture
        ↓
Signal Processing & Feature Extraction
        ↓
Feature-to-Vibration Mapping
        ↓
Unity Interaction Environment
        ↓
Real-Time Vibrotactile Feedback
```

The architecture separates data capture, signal processing and rendering, allowing textures to be recorded once and rendered dynamically during user interaction.

---

## Embedded System

Real-world texture interactions are captured using a custom sensing device based on an ESP32-S3.

Hardware components:
- ESP32-S3 microcontroller
- SPH0645 I2S MEMS microphone
- ADXL345 three-axis accelerometer
- DA7280 haptic driver with Linear Resonant Actuator (LRA)

Firmware features:
- FreeRTOS multitasking
- synchronized acquisition of audio and acceleration signals
- wireless data transfer to a host computer
- UDP communication for real-time haptic control

---

## Signal Processing Pipeline

Recorded signals are processed offline using Python.

The pipeline performs:
- signal preprocessing and denoising
- interaction segmentation
- feature extraction from audio and acceleration signals
- mapping of extracted features to vibration parameters

These parameters define the frequency and amplitude used to drive the LRA.

The system supports three feedback modes:
- audio-based feedback
- accelerometer-based feedback
- fusion of both modalities

---

## Haptic Rendering in Unity

The rendering environment is implemented in Unity.

Main features:
- Leap Motion hand tracking
- fingertip interaction with virtual surfaces
- real-time communication with the embedded haptic device via UDP
- velocity-based modulation of vibration parameters

Velocity modulation adjusts vibration frequency and amplitude according to the user's interaction speed to improve realism.

---

## Textures Used

Three representative textures were used for evaluation:

- coarse comb (2 mm spacing)
- fine comb (1 mm spacing)
- sandpaper

The comb textures represent periodic surface structures, while sandpaper represents a stochastic surface.  
This allows the system to evaluate how different sensing modalities contribute to texture representation.

---

## Evaluation

User experiments showed that:

- fusion of audio and accelerometer features produced the most realistic feedback
- accelerometer features worked better for periodic textures
- audio features worked better for stochastic textures
- participants achieved about 80–90% texture identification accuracy using vibrotactile feedback alone

Users also reported that velocity-based modulation improved responsiveness and realism during interaction.


