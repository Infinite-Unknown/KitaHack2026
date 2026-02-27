# SentinAI

This repository contains all code related to SentinAI.

## 👥 About our team
The Trio is a team dedicated to solve problems in unique ways using technology. We explore how different implementations of technology can elminate different issues that people face around the globe. 

Our team consists of: 

1. Jia Hern (Backend programmer)
2. Ruben Lim (Frontend programmer)
3. Jun Ian (Debugging, documentation)

## 📋 Project overview
### ❗ Problem statement
CCTV cameras have proven to be effective in preventing accidents and bullying cases. However, private areas, such as bathrooms, have long been a blind spot for such surveillance. 

### 💡 Solution

SentinAI is a system that detects and prevents accidents in spots not typically covered by CCTV cameras, including bathrooms, bedrooms and more. 

It achieves this via Channel State Information (CSI) tracking, which uses WiFi signals to track a person's actions. This works even through walls, which solves the problem of surveillance not reaching blind spots.

To acheive CSI tracking, several nodes are place around an area. These nodes are ESP32 devices, which work together to capture the person's movements through triangulation.

The movements are then sent to a cloud AI model to determine their actions. If the AI detects certain accidental movements, such as falling, slipping or bullying actions, the user will be notified through the frontend. 

### 🌍 SDG alignment
This project is aligned with SDG 3 (Good health and well-being). By deploying this project, we hope to safeguard the elderly from the unexpected. We also hope to protect students around the world from bullying. 

This project is also aligned with SDG 16 (Peace, justice and strong institutions). SentinAI can be deployed in peacekeeping missions that require stealthy detection of enemy movement, such as detecting terrorist movements even when they are hidden.

## ✨ Key features
- ### 📡 Privacy-Respecting Surveillance
    SentinAI uses WiFi-based Channel State Information (CSI) tracking instead of cameras, allowing it to monitor spaces like bathrooms and bedrooms without compromising privacy.

- ### 🔍 Real-Time Anomaly Detection
    A 1D CNN model trained with TensorFlow & Keras continuously analyzes CSI data from ESP32 nodes to detect anomalies such as falls and slips as they happen.

- ### 🤖 AI-Powered Verification
    Detected anomalies are cross-verified by Google's Gemini 2.5 Flash API, reducing false positives by confirming complex movement patterns before an alert is raised.

- ### 📲 Instant Alerts
    When a genuine incident is detected, caregivers or guardians are notified immediately through the Flutter frontend dashboard, enabling a fast response.

- ### 🏠 Works Through Walls
    By leveraging WiFi signals for tracking, SentinAI can monitor movement even through walls, covering blind spots that traditional CCTV systems cannot reach.

- ### 🔧 Flexible Deployment
    The system supports multiple ESP32 nodes that work together via triangulation, making it adaptable to spaces of different sizes and layouts.

## 🛠️ Technologies used
### 🔵 Google technologies:
- ### 🔥 Firebase
    Firebase Admin is used on the backend for analytics and to interface with Firebase Realtime Database, which the frontend dashboard connects to for live data.

- ### 🤖 Gemini
    Google's Gemini 2.5 Flash API is used as an LLM to verify complex movement patterns detected by the primary model.

- ### 🧠 Tensorflow
    The AI model is built with TensorFlow & Keras, implementing a 1D CNN architecture for time-series anomaly detection.

## 🔧 Other technologies used
- ### 💙 Flutter
    We chose Flutter as our framework of choice for our frontend. Flutter is a simple yet robust framework that allows us to deploy to multiple platforms using a single codebase.

- ### 🤝 Github Copilot
    Github Copilot has assisted us in creating the frontend code. Using Github Copilot, we cut a lot of time spent on boilerplate code and used the time for other productive tasks.

- ### 🖼️ CustomTkinter
    CustomTkinter is used as the data collection UI, providing a Python-based GUI for controlling the data gathering process.

- ### ⚙️ Hardware/Firmware
    ESP32 nodes run on C++ using the Arduino Core, with FreeRTOS managing concurrent tasks on each device.

- ### 🐍 Backend
    The backend analytics layer is built with Python, using Flask/Requests to handle communication between components.

---

## 🏗️ Project Workflow

SentinAI operates on a robust, multi-stage pipeline:

1. **Signal Generation & Capture (The ESP32 Layer)**
   - The ESP32 nodes (`esp32_csi_sender`) are configured in promiscuous mode to intercept raw Wi-Fi packets.
   - To guarantee constant Wi-Fi traffic, the nodes actively broadcast UDP "ping" packets.
   - The hardware calculates the amplitude of the subcarriers (CSI representations) and serves this formatted data over an HTTP endpoint.

2. **Data Collection & Training (The Setup Phase)**
   - `train/data_collector.py` provides a GUI to record CSI data from the 4 nodes simultaneously. It allows researchers to label activities (e.g., "falling", "walking", "empty_room") and save them as synchronized CSV files.
   - `backend/train_tf_model.py` uses this CSV dataset to train a lightweight 1D Convolutional Neural Network (CNN). By analyzing sliding windows of the multivariate time-series data, the model learns the specific spatial perturbations indicative of a fall or significant motion.

3. **Backend Polling & Edge ML (The Core Execution)**
   - Start the core system via `backend/analyzer.py`.
   - A background thread concurrently polls all 4 ESP32 nodes at high frequency to maintain a synchronized spatial buffer of the room.
   - The buffer is smoothed and passed into the locally hosted Keras model.
   - The Edge ML model evaluates the incoming frames. If the anomaly score (probability of a fall/motion) crosses a customizable threshold, a local trigger is tripped.

4. **Gemini AI Verification (The Brains)**
   - If the local Keras model suspects a fall, it sends the recent 1-second synchronized CSI amplitude matrix to the **Google Gemini 2.5 Flash API**.
   - With strict system instructions, Gemini acts as the ultimate verifier. It checks for the hallmark sign of a true fall: a massive, synchronized disruption across multiple nodes followed by immediate stillness.
   - Gemini responds with `FALL`, `MOTION`, or `NORMAL`, effectively filtering out localized hardware noise and reducing false positives.

5. **Realtime Frontend Alerts (The Output)**
   - Based on Gemini's verdict, the backend updates the system state (`"Normal"`, `"Emergency Detected"`) in a **Firebase Realtime Database**.
   - The frontend (`frontend/index.html` & `app.js`) listens for these Firebase state changes, immediately alerting users via the glowing UI dashboard if an emergency event occurs.

---

## 🚀 Installation and setup
### 📦 Prerequisites
Ensure that you have the following software and hardware needed:

- ### 🔩 Hardware:

    1. 4x ESP32 modules
    2. Local WiFi network with WiFi Router
    3. Computer for backend software

- ### 💻 Software:

    1. [Python 3.13+](https://www.python.org/downloads/)
    2. [Flutter 3.41+](https://docs.flutter.dev/install)
    3. [Arduino IDE](https://www.arduino.cc/en/software/) with ESP32 board configurations installed.

---

### Setup:

1. ### ⚙️ Backend
    1. Clone the repository: `git clone --recursive https://github.com/Infinite-Unknown/KitaHack2026.git`
    2. **HIGHLY RECOMMENDED**: Create and activate a virtual environment to keep dependencies isolated: `python3 -m venv ./backend && source ./backend/bin/activate`
    3. Install the required Python libraries: `pip3 install -r ./backend/requirements.txt`
    4. Open `backend/analyzer.py` and `train/data_collector.py`, then update the `ESP32_IPS` variable with the IP addresses of your ESP32 devices.
    5. *(Optional)* To train your own model, run `data_collector.py` to gather samples, then run `train_tf_model.py` to produce a `csi_fall_model.keras` file.
    6. You're all set! Start the backend by running: `python3 ./backend/analyzer.py`

2. ### 📡 ESP32 Nodes
    1. Open `esp32_csi_sender/esp32_csi_sender.ino` in the Arduino IDE and make the following changes:
        - **Lines 7 & 8** — Enter your WiFi network name and password
        - **Line 11** — Set a unique node ID for each ESP32
    2. Flash the updated sketch onto each of your ESP32 devices using the Arduino IDE.
    3. Once flashed, connect each ESP32 to a power source and position them around the area you wish to monitor.

3. ### 📱 Frontend
    1. Navigate to the frontend directory: `cd frontend/wifisentinel`
    2. Fetch and install the required dependencies: `flutter pub get`
    3. Launch the app: `flutter run lib/main.dart`

---
## ⚠️ Challenges Faced
**Model deployment**: The detection model was originally planned to be run locally, however due to time and technical constraints it was migrated to using Gemini as our detection model.

**CSI data synchronization**: Ensuring that CSI data from all 4 ESP32 nodes was captured and processed in sync proved challenging, as network latency between nodes could skew the spatial buffer and affect detection accuracy.

**Threshold tuning**: Finding the right anomaly score threshold for the Keras model required extensive trial and error, as a threshold too low would cause frequent false positives, while one too high risked missing genuine incidents.

**Mobile porting**: Multiple issues were encountered when porting the frontend to mobile devices, some of which are still undergoing fixing as of writing.

## 🗺️ Future roadmap
While the current primary focus is healthcare and elderly monitoring, the core technology of spatial disruption detection using Wi-Fi signals has vast future potential:

- **Peacekeeping & Tactical Applications**: The ability to sense movement through walls and in low-light environments without direct line-of-sight opens up possibilities for tactical room-clearing, hostage rescue, and perimeter security.
- **Smart Home Automation**: Expanding from emergency detection to robust gesture recognition and presence detection without wearing any devices.