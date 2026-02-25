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
    "ESP32_NODE_3": "192.168.8.166"
}

FIREBASE_URL = "https://gen-lang-client-0281295533-default-rtdb.asia-southeast1.firebasedatabase.app/status.json" 
GEMINI_API_KEY = "AIzaSyCW9Ub5MRtDrvCWhO4yUT01lo-afOPdr00" 

client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# ================= Global Variables =================
BUFFER_LIMIT = 100
csi_buffers = {
    "ESP32_NODE_1": [],
    "ESP32_NODE_2": [],
    "ESP32_NODE_3": []
}
status_state = "Normal" 
node_last_seen = {
    "ESP32_NODE_1": 0,
    "ESP32_NODE_2": 0,
    "ESP32_NODE_3": 0
}

# --- NEW: Adjustable Global Setting ---
ANOMALY_THRESHOLD = 80  # ML Fall Certainty Threshold %
# --------------------------------------

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
COOLDOWN_SECONDS = 15

def detect_anomaly_local():
    global last_gemini_call, ANOMALY_THRESHOLD, tf_model
    if time.time() - last_gemini_call < COOLDOWN_SECONDS:
        return False 
        
    if not tf_model:
        return False

    buf1 = csi_buffers.get("ESP32_NODE_1", [])
    buf2 = csi_buffers.get("ESP32_NODE_2", [])
    buf3 = csi_buffers.get("ESP32_NODE_3", [])
    
    if len(buf1) < 20 or len(buf2) < 20 or len(buf3) < 20:
        return False
        
    window = []
    # Grab the last 20 frames chronologically
    for i in range(20, 0, -1):
        # Flatten the 3 nodes into a 30-feature vector for the ML model
        frame = list(buf1[-i]) + list(buf2[-i]) + list(buf3[-i])
        window.append(frame)
        
    # Standardize scale
    input_data = np.array([window], dtype=np.float32) / 255.0
    
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
    for node, buf in csi_buffers.items():
        if len(buf) > 0:
            avg_snapshots = [str(int(np.mean(snap))) for snap in buf[-10:]]
            sample_data += f"{node}: [{','.join(avg_snapshots)}]\n"

    system_instruction = """
    You are an AI trained to detect life-threatening falls based on Wi-Fi Channel State Information (CSI) amplitude data.
    
    CRITICAL RULES FOR CLASSIFICATION:
    1. FALL: A true fall causes a massive, SYNCHRONIZED disruption across the Wi-Fi field. You will see a sharp, sudden decrease in amplitude across MULTIPLE nodes at the exact same time or in a fast staggering sequence, followed immediately by stillness.
    2. NORMAL: Activities like walking, sitting down, or waving also cause high variance, but the disruption is uncoordinated. Only one node might spike/drop at a time, or the wave pattern will be continuously chaotic without a sudden synchronized flatline. 
    
    You MUST output exactly one word: "FALL" or "NORMAL".
    """
    
    prompt = f"""
    The following data represents the average CSI amplitude across 3 ESP32 nodes spanning the last 1 second.
    
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
        return "Emergency Detected" if "FALL" in text else "Normal"
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "Emergency Detected (AI Error)"

def http_poller():
    print("Starting HTTP polling to ESP32s...")
    while True:
        for node_id, ip in ESP32_IPS.items():
            if not ip: continue
            try:
                resp = requests.get(f"http://{ip}/csi", timeout=0.5) 
                
                if resp.status_code == 200:
                    payload = resp.text.strip()
                    parts = payload.split(',')
                    
                    if len(parts) > 10:
                        parsed_id = parts[0]
                        try:
                            amplitudes = [int(p) for p in parts[1:]]
                        except ValueError:
                            continue 
                            
                        if len(amplitudes) >= 10:
                            if parsed_id in csi_buffers:
                                csi_buffers[parsed_id].append(amplitudes[:10])
                                node_last_seen[parsed_id] = time.time()
                                
                                if len(csi_buffers[parsed_id]) > BUFFER_LIMIT:
                                    csi_buffers[parsed_id].pop(0)
            except Exception as e:
                pass 
        time.sleep(0.1)

def backend_loop():
    threading.Thread(target=http_poller, daemon=True).start()
    
    global status_state
    
    update_firebase("Normal")
    
    while True:
        time.sleep(0.5)
        if detect_anomaly_local():
            print("Local anomaly detected! Triggering Gemini API validation...")
            result = analyze_with_gemini()
            
            if result != status_state:
                status_state = result
                update_firebase(status_state)
                
                if status_state == "Emergency Detected":
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
    app.geometry("400x250")
    app.title("SentinAI Control Panel")
    
    title_label = ctk.CTkLabel(app, text="SentinAI Backend Dashboard", font=ctk.CTkFont(size=20, weight="bold"))
    title_label.pack(pady=(20, 10))
    
    info_label = ctk.CTkLabel(app, text="Edge ML Certainty Threshold\n(Lower = Triggers easier on uncertain movements)")
    info_label.pack(pady=(0, 20))
    
    slider_val_label = ctk.CTkLabel(app, text=f"Trigger Certainty: {ANOMALY_THRESHOLD}%", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00FFAA")
    slider_val_label.pack()

    def update_threshold(value):
        global ANOMALY_THRESHOLD
        ANOMALY_THRESHOLD = int(value)
        slider_val_label.configure(text=f"Trigger Certainty: {ANOMALY_THRESHOLD}%")
        
    slider = ctk.CTkSlider(app, from_=10, to=100, command=update_threshold)
    slider.set(ANOMALY_THRESHOLD)
    slider.pack(pady=10, padx=40, fill="x")
    
    return app

if __name__ == "__main__":
    # Start the standard polling loop in the background
    threading.Thread(target=backend_loop, daemon=True).start()
    
    # Run the Tkinter UI on the main thread
    app = build_gui()
    app.mainloop()
