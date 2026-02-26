# SentinAI - Spatial Fall & Motion Detection System

SentinAI is an advanced, non-intrusive spatial tracking and activity monitoring system built for privacy-preserving applications. By leveraging Wi-Fi Channel State Information (CSI) across multiple ESP32 nodes, SentinAI can detect major environmental disruptions like human falls or general motion without using any cameras.

## 🎯 Goals
- **Elderly Care & Monitoring:** To provide a reliable, camera-free fall detection system for the elderly, especially in highly private spaces like bathrooms or bedrooms where cameras are intrusive.
- **Emergency Response:** Ensure that in the event of a dangerous fall, the system can automatically flag emergencies and alert caregivers to contact emergency services immediately.
- **Privacy First:** By using only Wi-Fi signals (CSI) instead of video feeds, absolute privacy is guaranteed while maintaining safety.

## 🔭 Vision & Future
While the current primary focus is healthcare and elderly monitoring, the core technology of spatial disruption detection using Wi-Fi signals has vast future potential:
- **Military & Tactical Applications:** The ability to sense movement through walls and in low-light environments without direct line-of-sight opens up possibilities for tactical room-clearing, hostage rescue, and perimeter security.
- **Smart Home Automation:** Expanding from emergency detection to robust gesture recognition and presence detection without wearing any devices.

---

## ⚙️ Tech Stack & Equipments

### Equipment
- **ESP32 Microcontrollers:** 4x ESP32 nodes (acting as spatial sensors capturing CSI data).
- **Wi-Fi Router:** Standard home Wi-Fi router generating the signal field.
- **Server/PC:** A local machine running the backend aggregation and machine learning models.

### Tech Stack
- **Hardware/Firmware:** C++ (Arduino Core for ESP32), FreeRTOS.
- **Backend Analytics:** Python, Flask/Requests, Firebase Admin.
- **Machine Learning:** TensorFlow & Keras (1D CNN for time-series anomaly detection).
- **AI Verification:** Google Gemini 2.5 Flash API (LLM for complex pattern confirmation).
- **Frontend Dashboard:** HTML, CSS, JavaScript (connecting to Firebase Realtime Database).
- **Data Collection UI:** CustomTkinter (Python GUI).

---

## 🔄 Project Workflow

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

## 🚀 Getting Started

1. **Flash ESP32s:** Flash the `esp32_csi_sender.ino` to your 4 ESP32 boards. Ensure the `device_id` and Wi-Fi credentials match your environment.
2. **Setup Python Environment:** `pip install -r backend/requirements.txt`
3. **Configure IP Addresses:** Edit `ESP32_IPS` in `backend/analyzer.py` and `train/data_collector.py` with the IPs of your ESP32 boards.
4. **(Optional) Train Model:** Run `data_collector.py` to get samples, then run `train_tf_model.py` to generate your `csi_fall_model.keras`.
5. **Run System:** Execute `backend/analyzer.py` to start monitoring.
6. **View Dashboard:** Open `frontend/index.html` in your browser.
