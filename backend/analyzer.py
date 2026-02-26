import socket
import time
import requests
import json
import threading
import numpy as np
import os
import customtkinter as ctk
import tensorflow as tf
from google import genai
import concurrent.futures

# Initialize Local TF Keras Model
tf_model = None
try:
    tf_model = tf.keras.models.load_model("csi_fall_model.keras")
    print("Loaded TF Keras Fall Model successfully.")
except Exception as e:
    print(f"Warning: Could not load TF Keras model: {e}")

# ================= Configuration =================
ESP32_IPS = {
    "ESP32_NODE_1": "192.168.8.168",
    "ESP32_NODE_2": "192.168.8.167",
    "ESP32_NODE_3": "192.168.8.166",
    "ESP32_NODE_4": "192.168.8.169"
}

FIREBASE_URL = "https://gen-lang-client-0281295533-default-rtdb.asia-southeast1.firebasedatabase.app/status.json" 
FIREBASE_MODE_URL = "https://gen-lang-client-0281295533-default-rtdb.asia-southeast1.firebasedatabase.app/mode.json" 
GEMINI_API_KEY = "AIzaSyC8MRFcBp_YJbvSCFie0r64tEiHa7I58Hc" 

client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# ================= Global Variables =================
BUFFER_LIMIT = 100
# Store synchronized snapshots: [{"timestamp": t, "ESP32_NODE_1": [10...], ...}]
synchronized_buffer = []

status_state = "Normal" 
node_last_seen = {
    "ESP32_NODE_1": 0,
    "ESP32_NODE_2": 0,
    "ESP32_NODE_3": 0,
    "ESP32_NODE_4": 0
}
last_known_features = {
    "ESP32_NODE_1": [0]*10,
    "ESP32_NODE_2": [0]*10,
    "ESP32_NODE_3": [0]*10,
    "ESP32_NODE_4": [0]*10
}

# --- NEW: Adjustable Global Setting ---
ANOMALY_THRESHOLD = 80  # ML Fall Certainty Threshold %
CURRENT_MODE = "Falling" # "Falling" or "Motion Detect"
POLLING_RATE_MS = 50
COOLDOWN_SECONDS = 15
SMOOTHING_FRAMES = 3 # Number of frames to average locally
GEMINI_ENABLED = False
# --------------------------------------

def update_firebase_mode(mode_string):
    if not FIREBASE_MODE_URL: return
    try:
        requests.put(FIREBASE_MODE_URL, json={"mode": mode_string})
    except Exception as e:
        print(f"Error updating Firebase Mode: {e}")

def fetch_firebase_mode():
    global CURRENT_MODE
    if not FIREBASE_MODE_URL: return
    try:
        resp = requests.get(FIREBASE_MODE_URL)
        if resp.status_code == 200 and resp.json() is not None:
            data = resp.json()
            if "mode" in data and data["mode"] != CURRENT_MODE:
                CURRENT_MODE = data["mode"]
                print(f"Mode synced from Firebase: {CURRENT_MODE}")
    except Exception as e:
        pass

def update_firebase(status_string):
    if not FIREBASE_URL: return
        
    current_time = time.time()
    nodes_status = {}
    for node, last_seen in node_last_seen.items():
        if current_time - last_seen < 5:
            nodes_status[node] = "online"
        else:
            nodes_status[node] = "offline"

    data = {
        "status": status_string, 
        "timestamp": current_time,
        "nodes": nodes_status
    }
    try:
        requests.put(FIREBASE_URL, json=data)
    except Exception as e:
        print(f"Error updating Firebase: {e}")

last_gemini_call = 0

def detect_anomaly_local():
    global last_gemini_call, ANOMALY_THRESHOLD, tf_model, COOLDOWN_SECONDS
    if time.time() - last_gemini_call < COOLDOWN_SECONDS:
        return False 
        
    if not tf_model:
        return False
        
    if len(synchronized_buffer) < 20:
        return False
        
    window = []
    # Grab the last 20 frames chronologically
    recent_frames = synchronized_buffer[-20:]
    
    for frame in recent_frames:
        features = []
        for node in ["ESP32_NODE_1", "ESP32_NODE_2", "ESP32_NODE_3", "ESP32_NODE_4"]:
            # If a node disconnects, pad with its LAST KNOWN values instead of 0s.
            # Padding with 0s causes an artificial 'drop' that the model misclassifies as a fall!
            if node in frame:
                vals = frame[node]
                last_known_features[node] = vals
            else:
                vals = last_known_features[node]
                
            features.extend(vals)
        window.append(features)
        
    # Convert to numpy array for easier smoothing
    window_np = np.array(window, dtype=np.float32)
    
    if CURRENT_MODE == "Motion Detect":
        # Simplified statistical variance check for motion detection
        # Calculate variance across time for each feature
        variance = np.var(window_np, axis=0)
        mean_variance = np.mean(variance)
        
        # If variance is high enough, we consider it motion
        # Adjust scaling of ANOMALY_THRESHOLD to be a variance threshold (e.g. 10 to 100 mapped to somewhat reasonable variance bounds)
        variance_threshold = (100 - ANOMALY_THRESHOLD + 10) * 10
        if mean_variance > variance_threshold:
            current_time_str = time.strftime("%H:%M:%S", time.localtime())
            print(f"\n[{current_time_str}] DEBUG: Edge ML Anomaly! Motion Detected (Variance: {mean_variance:.1f} > Threshold: {variance_threshold})")
            last_gemini_call = time.time()
            return True
        return False
        
    # ---------------------------------------------------------
    # Apply a moving average across the time dimension
    # This aggressively smooths out instantaneous hardware spikes
    # that the Keras model might hallucinate as a sudden "Fall".
    # ---------------------------------------------------------
    smoothed_window = np.copy(window_np)
    
    if SMOOTHING_FRAMES > 1:
        # Calculate moving average, padding the edges
        pad = SMOOTHING_FRAMES // 2
        for i in range(pad, len(window_np) - pad):
            # Sum values around the center index 'i'
            smoothed_window[i] = np.mean(window_np[i-pad : i+pad+1], axis=0)
    # ---------------------------------------------------------
        
    # Standardize scale
    input_data = np.array([smoothed_window], dtype=np.float32) / 255.0
    
    try:
        # Predict using full Keras model
        prediction = tf_model.predict(input_data, verbose=0)
        fall_prob = prediction[0][0] * 100.0 # Convert to percentage
        
        if fall_prob >= ANOMALY_THRESHOLD:
            current_time_str = time.strftime("%H:%M:%S", time.localtime())
            print(f"\n[{current_time_str}] DEBUG: Edge ML Anomaly! Fall Probability: {fall_prob:.1f}% (Threshold: {int(ANOMALY_THRESHOLD)}%)")
            last_gemini_call = time.time()
            return True
            
    except Exception as e:
        pass
            
    return False

def analyze_with_gemini():
    if not GEMINI_API_KEY:
        print("Gemini API key missing. Skipping AI verification.")
        return "Emergency Detected (Local Fallback)"
        
    print("Calling Gemini API to analyze CSI pattern...")
    sample_data = ""
    if len(synchronized_buffer) >= 10:
        recent = synchronized_buffer[-10:]
        for node in ["ESP32_NODE_1", "ESP32_NODE_2", "ESP32_NODE_3", "ESP32_NODE_4"]:
            # Get the mean of the 10 subcarriers for each of the last 10 frames
            avg_snapshots = []
            for frame in recent:
                if node in frame:
                    avg_snapshots.append(str(int(np.mean(frame[node]))))
                else:
                    avg_snapshots.append(str(int(np.mean(last_known_features[node]))))
            sample_data += f"{node}: [{','.join(avg_snapshots)}]\n"

    system_instruction = ""
    prompt = ""
    
    if CURRENT_MODE == "Falling":
        system_instruction = """
        You are an AI trained to detect life-threatening falls based on Wi-Fi Channel State Information (CSI) amplitude data.
        
        CRITICAL RULES FOR CLASSIFICATION:
        1. FALL: A true fall causes a massive, SYNCHRONIZED disruption across the Wi-Fi field. You will see a sharp, sudden decrease in amplitude across MULTIPLE nodes at the exact same time or in a fast staggering sequence, followed immediately by stillness.
        2. NORMAL: Activities like walking, sitting down, or waving also cause high variance, but the disruption is uncoordinated. Only one node might spike/drop at a time, or the wave pattern will be continuously chaotic without a sudden synchronized flatline. 
        3. There are 4 ESP32 nodes in the room providing spatial coverage.
        
        You MUST output exactly one word: "FALL" or "NORMAL".
        """
        
        prompt = f"""
        The following data represents the average CSI amplitude across 4 ESP32 nodes spanning the last 1 second.
        
        EXAMPLES:
        - Example 1 (True Fall): 
          ESP32_NODE_1: [134,134,69,134,134]
          ESP32_NODE_2: [134,134,134,69,134]
          ESP32_NODE_3: [134,134,134,134,134]
          -> Diagnosis: FALL (A massive, fast sequential/staggered drop in amplitude across the nodes, followed by immediate stillness/recovery back to baseline. This represents a body falling through the field.)
          
        - Example 2 (Normal Noise):
          ESP32_NODE_1: [134,88,134,134,134]
          ESP32_NODE_2: [134,134,110,134,134]
          ESP32_NODE_3: [134,134,134,43,134]
          -> Diagnosis: NORMAL (Nodes are noisy but the variance is continuous, chaotic, or asynchronous over a long period, typical of walking or sitting)
          
        Data:
        {sample_data}
        
        Analyze the temporal synchronization of the drops across the nodes. 
        Predict if this was a FALL or NORMAL activity. Respond with ONLY one word: "FALL" or "NORMAL".
        """
    else:
        system_instruction = """
        You are an AI trained to detect significant motion based on Wi-Fi Channel State Information (CSI) amplitude data.
        
        CRITICAL RULES FOR CLASSIFICATION:
        1. MOTION: Any significant variance in the CSI amplitude across the nodes over time indicates movement.
        2. NORMAL: If the values are mostly static without large jumps or drops, it indicates an empty room or a still environment.
        3. There are 4 ESP32 nodes in the room providing spatial coverage.
        
        You MUST output exactly one word: "MOTION" or "NORMAL".
        """
        
        prompt = f"""
        The following data represents the average CSI amplitude across 4 ESP32 nodes spanning the last 1 second.
        
        Data:
        {sample_data}
        
        Analyze if there are significant changes or variance in the signal indicating movement. 
        Predict if this was a MOTION or NORMAL activity. Respond with ONLY one word: "MOTION" or "NORMAL".
        """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1
            )
        )
        text = response.text.strip().upper()
        print(f"Gemini Prediction: {text}")
        if CURRENT_MODE == "Falling":
            return "Emergency Detected" if "FALL" in text else "Normal"
        else:
            return "Motion Detected" if "MOTION" in text else "Normal"
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "Emergency Detected (AI Error)" if CURRENT_MODE == "Falling" else "Motion Detected (AI Error)"

def fetch_csi(node_id, ip):
    """Fetches CSI from a single node with a strict timeout"""
    try:
        resp = requests.get(f"http://{ip}/csi", timeout=0.15)
        if resp.status_code == 200:
            parts = resp.text.strip().split(',')
            if len(parts) >= 11:
                return node_id, [int(p) for p in parts[1:11]]
    except Exception:
        pass
    return node_id, None

def http_poller():
    print("Starting synchronized HTTP polling to ESP32s...")
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    
    while True:
        timestamp = time.time()
        snapshot = {"timestamp": timestamp}
        has_data = False
        
        futures = {executor.submit(fetch_csi, node_id, ip): node_id for node_id, ip in ESP32_IPS.items() if ip}
        
        for future in concurrent.futures.as_completed(futures):
            node_id, amplitudes = future.result()
            if amplitudes:
                snapshot[node_id] = amplitudes
                node_last_seen[node_id] = timestamp
                has_data = True
                
        if has_data:
            synchronized_buffer.append(snapshot)
            if len(synchronized_buffer) > BUFFER_LIMIT:
                synchronized_buffer.pop(0)
                
        time.sleep(POLLING_RATE_MS / 1000.0)

def backend_loop():
    threading.Thread(target=http_poller, daemon=True).start()
    
    global status_state
    
    update_firebase("Normal")
    
    while True:
        time.sleep(0.5)
        
        # Periodically fetch mode from Firebase (could be updated by frontend)
        if int(time.time()) % 2 == 0:
            fetch_firebase_mode()
            
        if detect_anomaly_local():
            print("Local anomaly detected!")
            if GEMINI_ENABLED:
                print("Triggering Gemini API validation...")
                result = analyze_with_gemini()
            else:
                print("Gemini disabled, trusting local ML...")
                if CURRENT_MODE == "Falling":
                    result = "Emergency Detected"
                else:
                    result = "Motion Detected"
            
            if result != status_state:
                status_state = result
                update_firebase(status_state)
                
                if "Detected" in status_state:
                    time.sleep(10)
                    status_state = "Normal"
                    print("Resetting status to Normal...")
                    update_firebase("Normal")
        else:
            update_firebase(status_state)

def build_gui():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    app = ctk.CTk()
    app.geometry("550x850")
    app.title("SentinAI Control Panel")
    
    # Enable scrolling if the screen gets too small
    main_scrollable = ctk.CTkScrollableFrame(app)
    main_scrollable.pack(fill="both", expand=True)
    
    title_label = ctk.CTkLabel(main_scrollable, text="SentinAI Backend Dashboard", font=ctk.CTkFont(size=20, weight="bold"))
    title_label.pack(pady=(20, 10))
    
    # --- Node Status Frame ---
    node_status_frame = ctk.CTkFrame(main_scrollable)
    node_status_frame.pack(pady=10, padx=20, fill="x")
    
    node_status_frame.grid_columnconfigure((0,1,2,3), weight=1)
    
    global node_labels
    node_labels = {}
    for i, node_id in enumerate(["ESP32_NODE_1", "ESP32_NODE_2", "ESP32_NODE_3", "ESP32_NODE_4"]):
        lbl = ctk.CTkLabel(node_status_frame, text=f"Node {i+1}\nOffline", text_color="red", font=ctk.CTkFont(weight="bold"))
        lbl.grid(row=0, column=i, padx=5, pady=10)
        node_labels[node_id] = lbl
    
    # --- Settings Frame ---
    settings_frame = ctk.CTkFrame(main_scrollable)
    settings_frame.pack(pady=10, padx=20, fill="both", expand=True)

    # Mode Selection
    mode_label = ctk.CTkLabel(settings_frame, text="Active Detection Mode:", font=ctk.CTkFont(weight="bold"))
    mode_label.pack(pady=(10, 0))
    
    def mode_callback(choice):
        global CURRENT_MODE
        CURRENT_MODE = choice
        print(f"Mode changed to: {CURRENT_MODE}")
        # Update Firebase immediately
        update_firebase_mode(CURRENT_MODE)
        if CURRENT_MODE == "Motion Detect":
            slider_val_label.configure(text=f"Variance Sensitivity: {ANOMALY_THRESHOLD}%")
        else:
            slider_val_label.configure(text=f"Trigger Certainty: {ANOMALY_THRESHOLD}%")

    global mode_dropdown
    mode_dropdown = ctk.CTkOptionMenu(settings_frame, values=["Falling", "Motion Detect"], command=mode_callback)
    mode_dropdown.set(CURRENT_MODE)
    mode_dropdown.pack(pady=(0, 15))
    
    # ML Threshold Slider
    global slider_val_label
    slider_val_label = ctk.CTkLabel(settings_frame, text=f"Trigger Certainty: {ANOMALY_THRESHOLD}%", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00FFAA")
    slider_val_label.pack(pady=(15, 0))
    
    desc_label_1 = ctk.CTkLabel(settings_frame, text="Lower % = Triggers more easily on uncertain movements.\nHigher % = Stricter, prevents false alarms but might miss events.", font=ctk.CTkFont(size=11), text_color="gray")
    desc_label_1.pack()

    def update_threshold(value):
        global ANOMALY_THRESHOLD
        ANOMALY_THRESHOLD = int(value)
        if CURRENT_MODE == "Motion Detect":
            slider_val_label.configure(text=f"Variance Sensitivity: {ANOMALY_THRESHOLD}%")
        else:
            slider_val_label.configure(text=f"Trigger Certainty: {ANOMALY_THRESHOLD}%")
        
    slider = ctk.CTkSlider(settings_frame, from_=10, to=100, command=update_threshold)
    slider.set(ANOMALY_THRESHOLD)
    slider.pack(pady=(5, 10), padx=40, fill="x")
    
    # Smoothing Frames Slider
    global smoothing_label
    smoothing_label = ctk.CTkLabel(settings_frame, text=f"Data Smoothing Frames: {SMOOTHING_FRAMES}", font=ctk.CTkFont(size=14, weight="bold"))
    smoothing_label.pack(pady=(15, 0))
    
    desc_label_smoothing = ctk.CTkLabel(settings_frame, text="Higher = More stable data (less hardware noise), but slower reaction time.\nLower = Faster reaction time, but more prone to false positive spikes.", font=ctk.CTkFont(size=11), text_color="gray")
    desc_label_smoothing.pack()
    
    def update_smoothing(value):
        global SMOOTHING_FRAMES
        SMOOTHING_FRAMES = int(value)
        # Ensure it's an odd number for symmetrical padding
        if SMOOTHING_FRAMES % 2 == 0:
            SMOOTHING_FRAMES += 1
        smoothing_label.configure(text=f"Data Smoothing Frames: {SMOOTHING_FRAMES}")
        
    smooth_slider = ctk.CTkSlider(settings_frame, from_=1, to=9, number_of_steps=4, command=update_smoothing)
    smooth_slider.set(SMOOTHING_FRAMES)
    smooth_slider.pack(pady=(5, 10), padx=40, fill="x")
    
    # Polling Rate Slider
    poll_label = ctk.CTkLabel(settings_frame, text=f"Hardware Polling Interval: {POLLING_RATE_MS} ms", font=ctk.CTkFont(size=14, weight="bold"))
    poll_label.pack(pady=(15, 0))
    
    desc_label_2 = ctk.CTkLabel(settings_frame, text="Lower ms = Higher frequency data collection (more CPU intensive).\nHigher ms = Slower data collection (saves resources).", font=ctk.CTkFont(size=11), text_color="gray")
    desc_label_2.pack()
    
    def update_poll(value):
        global POLLING_RATE_MS
        POLLING_RATE_MS = int(value)
        poll_label.configure(text=f"Hardware Polling Interval: {POLLING_RATE_MS} ms")
        
    poll_slider = ctk.CTkSlider(settings_frame, from_=10, to=500, command=update_poll)
    poll_slider.set(POLLING_RATE_MS)
    poll_slider.pack(pady=(5, 10), padx=40, fill="x")
    
    # Cooldown Slider
    cd_label = ctk.CTkLabel(settings_frame, text=f"Gemini API Cooldown: {COOLDOWN_SECONDS} s", font=ctk.CTkFont(size=14, weight="bold"))
    cd_label.pack(pady=(15, 0))
    
    desc_label_3 = ctk.CTkLabel(settings_frame, text="Higher s = Cheaper API costs, prevents duplicate alerts.\nLower s = Faster re-arming for consecutive events.", font=ctk.CTkFont(size=11), text_color="gray")
    desc_label_3.pack()
    
    def update_cd(value):
        global COOLDOWN_SECONDS
        COOLDOWN_SECONDS = int(value)
        cd_label.configure(text=f"Gemini API Cooldown: {COOLDOWN_SECONDS} s")
        
    cd_slider = ctk.CTkSlider(settings_frame, from_=5, to=60, command=update_cd)
    cd_slider.set(COOLDOWN_SECONDS)
    cd_slider.pack(pady=(5, 10), padx=40, fill="x")
    
    # Gemini Toggle
    def toggle_gemini():
        global GEMINI_ENABLED
        GEMINI_ENABLED = gemini_var.get()
        print(f"Gemini API Enabled: {GEMINI_ENABLED}")
        
    gemini_var = ctk.BooleanVar(value=GEMINI_ENABLED)
    gemini_cb = ctk.CTkCheckBox(settings_frame, text="Enable Gemini AI Verification (Costs Google AI Quota)", variable=gemini_var, command=toggle_gemini)
    gemini_cb.pack(pady=(10, 20))

    # Synchronize UI external state
    def sync_ui():
        # Sync Mode from backend changes
        if mode_dropdown.get() != CURRENT_MODE:
            mode_dropdown.set(CURRENT_MODE)
            if CURRENT_MODE == "Motion Detect":
                slider_val_label.configure(text=f"Variance Sensitivity: {ANOMALY_THRESHOLD}%")
            else:
                slider_val_label.configure(text=f"Trigger Certainty: {ANOMALY_THRESHOLD}%")
        
        # Sync Node Online Status
        current_time = time.time()
        for node_id, lbl in node_labels.items():
            last_seen = node_last_seen.get(node_id, 0)
            if current_time - last_seen < 5:
                lbl.configure(text=f"Node {node_id[-1]}\nOnline", text_color="#00FFAA")
            else:
                lbl.configure(text=f"Node {node_id[-1]}\nOffline", text_color="red")
                
        app.after(1000, sync_ui)
        
    app.after(1000, sync_ui)
    
    return app

if __name__ == "__main__":
    # Start the standard polling loop in the background
    threading.Thread(target=backend_loop, daemon=True).start()
    
    # Run the Tkinter UI on the main thread
    app = build_gui()
    app.mainloop()
