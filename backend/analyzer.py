import socket
import time
import requests
import json
import threading
import numpy as np
import os
from google import genai

# ================= Configuration =================
# Replace these IPs with the actual IPs printed by your ESP32s in the Arduino Serial Monitor
ESP32_IPS = {
    "ESP32_NODE_1": "192.168.8.168", # Example IP from your screenshot
    "ESP32_NODE_2": "192.168.8.167",
    "ESP32_NODE_3": "192.168.8.166"
}

FIREBASE_URL = "https://gen-lang-client-0281295533-default-rtdb.asia-southeast1.firebasedatabase.app/status.json" # e.g., "https://your-project.firebaseio.com/status.json"
GEMINI_API_KEY = "AIzaSyCW9Ub5MRtDrvCWhO4yUT01lo-afOPdr00" # Your Gemini API Key

# Configure Gemini
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# ================= Global Variables =================
# Stores the history of CSI amplitudes for the 3 nodes
# We store the latest 100 snapshots (~2-3 seconds of data)
BUFFER_LIMIT = 100
csi_buffers = {
    "ESP32_NODE_1": [],
    "ESP32_NODE_2": [],
    "ESP32_NODE_3": []
}

status_state = "Emergency" # Normal or Emergency

node_last_seen = {
    "ESP32_NODE_1": 0,
    "ESP32_NODE_2": 0,
    "ESP32_NODE_3": 0
}

def update_firebase(status_string):
    """Update Firebase Realtime Database with the current status"""
    if not FIREBASE_URL:
        return
        
    current_time = time.time()
    nodes_status = {}
    for node, last_seen in node_last_seen.items():
        # Consider a node offline if it hasn't sent data in 5 seconds
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
        print(f"Firebase updated: {status_string} | Nodes: {nodes_status}")
    except Exception as e:
        print(f"Error updating Firebase: {e}")

last_gemini_call = 0
COOLDOWN_SECONDS = 15

def detect_anomaly_local():
    """
    A lightweight statistical check to avoid spamming the Gemini API.
    If the variance across the subcarriers suddenly spikes compared to a baseline,
    we trigger AI validation.
    """
    global last_gemini_call
    if time.time() - last_gemini_call < COOLDOWN_SECONDS:
        return False # Rate limit Gemini API

    for node, buf in csi_buffers.items():
        if len(buf) < 20: continue
        
        # Calculate a baseline variance from older data to adapt to the room
        baseline = np.array(buf[-20:-10])[:, :10]
        recent = np.array(buf[-10:])[:, :10] 
        
        baseline_var = np.var(baseline)
        recent_var = np.var(recent)
        
        # Trigger if the variance suddenly spikes massively compared to background noise
        if recent_var > (baseline_var * 3) and recent_var > 3000:
            last_gemini_call = time.time()
            return True
    return False

def analyze_with_gemini():
    """
    If a sudden spike is detected locally, we send the recent window to Gemini 
    to classify the nature of the movement (e.g. Fall vs Sitting down)
    """
    if not GEMINI_API_KEY:
        print("Gemini API key missing. Skipping AI verification.")
        return "Emergency Detected (Local Fallback)"
        
    print("Calling Gemini API to analyze CSI pattern...")
    
    # We serialize a smaller sample of the data to keep prompt size reasonable
    sample_data = ""
    for node, buf in csi_buffers.items():
        if len(buf) > 0:
            # take average of subcarriers for the last 10 snapshots
            avg_snapshots = [str(int(np.mean(snap))) for snap in buf[-10:]]
            sample_data += f"{node}: [{','.join(avg_snapshots)}]\n"

    prompt = f"""
    You are an AI trained to detect falls and emergencies based on Wi-Fi Channel State Information (CSI) amplitude data.
    The following data represents the average CSI amplitude across 3 ESP32 nodes spanning the last 1 second.
    A sudden, sharp decrease followed by stillness often indicates a fall. Normal walking has periodic variations.
    
    Data:
    {sample_data}
    
    Predict if this was a FALL or NORMAL activity. Respond with ONLY one word: "FALL" or "NORMAL".
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        text = response.text.strip().upper()
        print(f"Gemini Prediction: {text}")
        return "Emergency Detected" if "FALL" in text else "Normal"
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "Emergency Detected (AI Error)"

def http_poller():
    """Polls the ESP32 units for their latest CSI data via HTTP GET"""
    print("Starting HTTP polling to ESP32s...")
    while True:
        for node_id, ip in ESP32_IPS.items():
            if not ip: continue
            try:
                # 500ms timeout so we don't stall the thread if a node goes offline
                resp = requests.get(f"http://{ip}/csi", timeout=0.5) 
                
                if resp.status_code == 200:
                    payload = resp.text.strip()
                    parts = payload.split(',')
                    
                    if len(parts) > 10:
                        parsed_id = parts[0]
                        try:
                            # Safely parse amplitudes and force a consistent length of 10
                            amplitudes = [int(p) for p in parts[1:]]
                        except ValueError:
                            continue # Ignore garbled packets
                            
                        if len(amplitudes) >= 10:
                            if parsed_id in csi_buffers:
                                csi_buffers[parsed_id].append(amplitudes[:10])
                                node_last_seen[parsed_id] = time.time()
                                print(f"DEBUG: Fetched CSI from {parsed_id} via HTTP!")
                                
                                if len(csi_buffers[parsed_id]) > BUFFER_LIMIT:
                                    csi_buffers[parsed_id].pop(0)
            except Exception as e:
                pass # Node might be offline or unreachable, will reflect in timeout
        
        # Small delay to prevent hammering the network constantly
        time.sleep(0.1)

def main():
    threading.Thread(target=http_poller, daemon=True).start()
    
    global status_state
    last_update = 0
    
    update_firebase("Normal")
    
    while True:
        time.sleep(2) # Check every 2 seconds
        
        if detect_anomaly_local():
            print("Local anomaly detected! Triggering Gemini API validation...")
            
            result = analyze_with_gemini()
            
            if result != status_state:
                status_state = result
                update_firebase(status_state)
                
                # If emergency, we hold it for 10 seconds to avoid flap
                if status_state == "Emergency Detected":
                    time.sleep(10)
                    status_state = "Normal"
                    print("Resetting status to Normal...")
                    update_firebase("Normal")
        else:
            # Keep Firebase updated with the node heartbeats every 2 seconds
            update_firebase(status_state)

if __name__ == "__main__":
    main()
