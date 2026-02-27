import time
import requests
import threading
import os
import csv
from datetime import datetime
import customtkinter as ctk

import concurrent.futures

# ================= Configuration =================
# Fallback to static IPs as requested. 
# Note: These are the CURRENT IPs found on your network right now. Node 1 is offline.
ESP32_IPS = {
    "ESP32_NODE_1": "192.168.8.162",
    "ESP32_NODE_2": "192.168.8.163",
    "ESP32_NODE_3": "192.168.8.164",
    "ESP32_NODE_4": "192.168.8.166"
}

# The folder where we will save our recorded CSV files
DATA_DIR = "dataset"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Global flag to control recording
is_recording = False
current_label = "unknown"
recorded_data = []
frames_recorded = 0
current_fps = 0.0
last_frame_time = 0
nodes_online_count = 0
nodes_status_str = "0/4"

def fetch_csi(node_id, ip):
    """Fetches CSI from a single IP with a strict timeout, returning the true Node ID."""
    try:
        resp = requests.get(f"http://{ip}/csi", timeout=0.15)
        if resp.status_code == 200:
            parts = resp.text.strip().split(',')
            if len(parts) >= 11:
                real_node_id = parts[0]
                return real_node_id, [int(p) for p in parts[1:11]]
    except Exception:
        pass
    return node_id, None

def http_poller(app):
    """Continuously polls ESP32s concurrently in the background"""
    global is_recording, recorded_data, frames_recorded, current_fps, last_frame_time, nodes_online_count, nodes_status_str
    
    # Thread pool for concurrent requests (prevents 1 slow node from halting others)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    
    while True:
        timestamp = time.time()
        snapshot = {"timestamp": timestamp, "label": current_label}
        has_data = False
        online_nodes_list = []
            
        # Fire requests to all configured static IPs concurrently
        futures = {executor.submit(fetch_csi, node_id, ip): node_id for node_id, ip in ESP32_IPS.items() if ip}
            
        for future in concurrent.futures.as_completed(futures):
            node_id, amplitudes = future.result()
            if node_id and amplitudes:
                online_nodes_list.append(node_id)
                if is_recording:
                    snapshot[node_id] = amplitudes
                    has_data = True
        
        nodes_online_count = len(online_nodes_list)
        # Sort node list so they always appear in consistent order (e.g. Node 1, Node 2...)
        online_nodes_list.sort()
        
        if online_nodes_list:
            # e.g "ESP32_NODE_1, ESP32_NODE_3" -> "Node 1, Node 3"
            clean_names = [n.replace("ESP32_NODE_", "Node ") for n in online_nodes_list]
            nodes_status_str = f"[{', '.join(clean_names)}]"
        else:
            nodes_status_str = "[None]"
        
        # Always update the nodes label via app.after
        app.after(0, app.update_nodes_status, nodes_status_str, nodes_online_count)

        if is_recording and has_data:
            recorded_data.append(snapshot)
            frames_recorded += 1
            
            # Calculate FPS
            now = time.time()
            if last_frame_time > 0:
                delta = now - last_frame_time
                if delta > 0:
                    current_fps = 1.0 / delta
            last_frame_time = now
            
            # Update UI periodically so it doesn't freeze
            if frames_recorded % 3 == 0:
                app.after(0, app.update_status, f"🔴 Recording '{current_label}'... ({frames_recorded} frames | {current_fps:.0f} fps)", "red")
                
        time.sleep(0.02) # Poll faster (~50 times/sec loop)

def save_data_to_csv(label, data):
    """Saves the recorded session to a CSV file inside its own subfolder"""
    if not data:
        return False, "No data recorded! Make sure ESP32s are online."
        
    # Create subfolder based on the label
    label_dir = os.path.join(DATA_DIR, label)
    if not os.path.exists(label_dir):
        os.makedirs(label_dir)
        
    filename = os.path.join(label_dir, f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    
    # Define CSV headers
    headers = ["timestamp", "label"]
    for node in ESP32_IPS.keys():
        for i in range(10): # We save 10 subcarriers per node
            headers.append(f"{node}_sub_{i}")
            
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for row in data:
            csv_row = [row["timestamp"], row["label"]]
            for node in ESP32_IPS.keys():
                if node in row:
                    csv_row.extend(row[node])
                else:
                    csv_row.extend([""] * 10) # Empty cells if node missed this frame
            writer.writerow(csv_row)
            
    return True, f"✅ Saved {len(data)} frames to {filename}"

class DataCollectorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SentinAI - CSI Data Collector")
        self.geometry("450x400")
        self.resizable(False, False)
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)

        # Title
        self.title_label = ctk.CTkLabel(self, text="CSI Data Collector", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 5))

        # Nodes Online Badge
        self.nodes_label = ctk.CTkLabel(self, text="Nodes Online: 0/4", font=ctk.CTkFont(size=14))
        self.nodes_label.grid(row=1, column=0, padx=20, pady=(0, 10))

        # Label Selection Area
        self.label_frame = ctk.CTkFrame(self)
        self.label_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.label_frame.grid_columnconfigure(1, weight=1)

        self.action_lbl = ctk.CTkLabel(self.label_frame, text="Action Label:")
        self.action_lbl.grid(row=0, column=0, padx=10, pady=10)

        # Pre-defined actions dropdown
        self.action_var = ctk.StringVar(value="falling")
        self.action_menu = ctk.CTkOptionMenu(
            self.label_frame, 
            variable=self.action_var,
            values=["falling", "walking", "sitting", "standing", "waving", "empty_room", "Custom"],
            command=self.on_label_change
        )
        self.action_menu.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Custom tag entry box (hidden by default)
        self.custom_entry = ctk.CTkEntry(self.label_frame, placeholder_text="Type custom label here...")
        
        # Binary Trigger Checkbox for Custom Labels (hidden by default)
        self.trigger_var = ctk.BooleanVar(value=False)
        self.trigger_checkbox = ctk.CTkCheckBox(self.label_frame, text="Is this a Fall/Trigger condition?", variable=self.trigger_var)
        
        # Don't grid them yet — only shown when "Custom" is selected

        # Start / Stop Buttons
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        self.btn_frame.grid_columnconfigure((0, 1), weight=1)

        self.start_btn = ctk.CTkButton(self.btn_frame, text="▶ START RECORDING", fg_color="green", hover_color="darkgreen", font=ctk.CTkFont(weight="bold"), command=self.start_recording)
        self.start_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.stop_btn = ctk.CTkButton(self.btn_frame, text="⏹ STOP RECORDING", fg_color="red", hover_color="darkred", font=ctk.CTkFont(weight="bold"), state="disabled", command=self.stop_recording)
        self.stop_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Live Status Monitor
        self.status_label = ctk.CTkLabel(self, text="Ready to record. Select a label and press Start.", font=ctk.CTkFont(size=14))
        self.status_label.grid(row=4, column=0, padx=20, pady=20)

    def on_label_change(self, choice):
        if choice == "Custom":
            self.custom_entry.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
            self.trigger_checkbox.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        else:
            self.custom_entry.grid_forget()
            self.trigger_checkbox.grid_forget()

    def start_recording(self):
        global is_recording, current_label, recorded_data, frames_recorded, current_fps, last_frame_time
        
        # Priority to custom entry if filled
        custom_val = self.custom_entry.get().strip()
        if custom_val and self.action_var.get() == "Custom":
            sanitized = custom_val.replace(" ", "_").lower()
            # If the checkbox is checked, append '_fall' so the trainer knows to label it 1
            if self.trigger_var.get():
                current_label = f"{sanitized}_fall"
            else:
                current_label = f"{sanitized}_normal"
        else:
            current_label = self.action_var.get()

        recorded_data = []
        frames_recorded = 0
        current_fps = 0.0
        last_frame_time = 0
        is_recording = True

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.action_menu.configure(state="disabled")
        self.custom_entry.configure(state="disabled")
        self.trigger_checkbox.configure(state="disabled")
        
        self.update_status(f"🔴 Recording '{current_label}'... (0 frames)", "red")

    def stop_recording(self):
        global is_recording
        is_recording = False
        
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.action_menu.configure(state="normal")
        self.custom_entry.configure(state="normal")
        self.trigger_checkbox.configure(state="normal")
        
        self.update_status("Saving data...", "white")
        
        # Save payload
        success, msg = save_data_to_csv(current_label, recorded_data)
        
        color = "#2ecc71" if success else "#e67e22" # Using nice hex colors
        self.update_status(msg, color)
        if success:
            self.flash_success()

    def flash_success(self):
        # Briefly flash the background to give a stark visual sign it was saved
        original_color = self._fg_color
        self.configure(fg_color="#143621") # Dark green
        self.after(250, lambda: self.configure(fg_color=original_color))
        self.after(500, lambda: self.configure(fg_color="#143621"))
        self.after(750, lambda: self.configure(fg_color=original_color))

    def update_status(self, text, color="white"):
        self.status_label.configure(text=text, text_color=color)

    def update_nodes_status(self, status_str, count):
        total = len(ESP32_IPS)
        color = "#2ecc71" if count >= total else "#e67e22" if count > 0 else "red"
        self.nodes_label.configure(text=f"Nodes Online: {status_str}", text_color=color)

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    
    app = DataCollectorApp()
    
    print("Starting background ESP32 HTTP Poller thread...")
    threading.Thread(target=http_poller, args=(app,), daemon=True).start()
    
    print("Opening CustomTkinter UI...")
    app.mainloop()
