# SentinAI Client
This is the repository for SentiAI's frontend. 

SentiAI consists of this frontend and other backend functions.

## About our team
The Trio is a team dedicated to solve problems in unique ways using technology. We explore with how different implementations of technology can elminate different issues that people face around the globe. 

Our team consists of: 

1. Jia Hern (Backend programmer)
2. Ruben Lim (Frontend programmer)
3. Jun Ian (Debugging, documentation)

## Project overview
### Problem statement
CCTV cameras have proven to be effective in preventing accidents and bullying cases. However, private areas, such as bathrooms, have long been a blind spot for such surveillance. 

### Solution

SentiAI is a system that detects and prevents accidents in spots not typically covered by CCTV cameras, including bathrooms, bedrooms and more. 

It achieves this via Channel State Information (CSI) tracking, which uses WiFi signals to track a person's actions. This works even through walls, which solves the problem of surveillance not reaching blind spots.

To acheive CSI tracking, several nodes are place around an area. These nodes are ESP32 devices, which work together to capture the person's movements through triangulation.

The movements are then sent to a cloud AI model to determine their actions. If the AI detects certain accidental movements, such as falling, slipping or bullying actions, the user will be notified through the frontend. 

### SDG alignment
This project is aligned with SDG 3 (Good health and well-being). By deploying this project, we hope to safeguard the elderly from the unexpected. We also hope to protect students around the world from bullying. 

This project is also aligned with SDG 

## Key features

## Technologies used
### Google technologies:
- ### Firebase
    Firebase is used to transmit data to and from the backend to the client. It is also used to communicate to the ESP32 nodes.

- ### Gemini
    Google's Gemini model is used to analyze the movement positions, as it has been tested to work well with images.

- ### Tensorflow
    The AI model was first trained with Tensorflow, using a mix of locally generated data and other public data sources.

## Other technologies used
- ### Flutter
    We chose Flutter as our framework of choice for our frontend. Flutter is a simple yet robust framework that allows us to deploy to multiple platforms using a single codebase.

- ### Github Copilot
    Github Copilot has assisted us in creating the frontend code. Using Github Copilot, we cut a lot of time spent on boilerplate code and used the time for other productive tasks.

- ### Tkinter
    Tkinter is used on the Python backend as a simple UI to control the sensitivity of the AI model.

## System architecture

## Challenges Faced
The detection model was originally planned to be run locally, however due to time and technical constraints it was migrated to using Gemini as our detection model.

There were multiple issues faced when porting the frontend to mobile devices, some of which are still undergoing fixing as of writing.

## Prerequisites
Ensure that you have the following software and hardware needed:

**Hardware**:

1. 4x ESP32 modules
2. Local WiFi network with WiFi Router

**Software**:

1. Python 3.13+
2. Flutter 3.41+
3. Arduino IDE with ESP32 board configs installed

## Installation and setup
1. Clone the repository: `git clone --recursive https://github.com/Infinite-Unknown/KitaHack2026.git`
2. Flash the ESP32s with `esp32_csi_sender/esp32_csi_sender.ino` using the Arduino IDE
    - Note: When flashing, 

## Future roadmap
someone pls help