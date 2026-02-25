import time
import requests
import threading
import os
import csv
from datetime import datetime
import customtkinter as ctk

# ================= Configuration =================
ESP32_IPS = {
    "ESP32_NODE_1": "192.168.8.168",
    "ESP32_NODE_2": "192.168.8.167",
    "ESP32_NODE_3": "192.168.8.166"
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

def http_poller(app):
    """Continuously polls ESP32s in the background, only saves data if recording is active"""
    global is_recording, recorded_data, frames_recorded
    
    while True:
        if is_recording:
            timestamp = time.time()
            snapshot = {"timestamp": timestamp, "label": current_label}
            has_data = False
            
            for node_id, ip in ESP32_IPS.items():
                if not ip: continue
                try:
                    resp = requests.get(f"http://{ip}/csi", timeout=0.2) 
                    if resp.status_code == 200:
                        payload = resp.text.strip()
                        parts = payload.split(',')
                        
                        if len(parts) >= 11: # ID + 10 amplitudes
                            try:
                                amplitudes = [int(p) for p in parts[1:11]]
                                snapshot[node_id] = amplitudes
                                has_data = True
                            except ValueError:
                                pass
                except requests.exceptions.RequestException:
                    pass # Node offline or timeout
            
            # Only save the frame if we actually got data from at least one node
            if has_data:
                recorded_data.append(snapshot)
                frames_recorded += 1
                
                # Update UI periodically so it doesn't freeze (Tkinter safe thread call)
                if frames_recorded % 5 == 0:
                    app.after(0, app.update_status, f"🔴 Recording '{current_label}'... ({frames_recorded} frames)", "red")
                
        time.sleep(0.05) # Poll ~20 times a second

def save_data_to_csv(label, data):
    """Saves the recorded session to a CSV file"""
    if not data:
        return False, "No data recorded! Make sure ESP32s are online."
        
    filename = f"{DATA_DIR}/{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
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
        self.geometry("450x350")
        self.resizable(False, False)
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)

        # Title
        self.title_label = ctk.CTkLabel(self, text="CSI Data Collector", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Label Selection Area
        self.label_frame = ctk.CTkFrame(self)
        self.label_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.label_frame.grid_columnconfigure(1, weight=1)

        self.action_lbl = ctk.CTkLabel(self.label_frame, text="Action Label:")
        self.action_lbl.grid(row=0, column=0, padx=10, pady=10)

        # Pre-defined actions dropdown
        self.action_var = ctk.StringVar(value="falling")
        self.action_menu = ctk.CTkOptionMenu(
            self.label_frame, 
            variable=self.action_var,
            values=["falling", "walking", "sitting", "standing", "waving", "empty_room"]
        )
        self.action_menu.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Custom tag entry box
        self.custom_entry = ctk.CTkEntry(self.label_frame, placeholder_text="Or type custom label here...")
        self.custom_entry.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")

        # Start / Stop Buttons
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.btn_frame.grid_columnconfigure((0, 1), weight=1)

        self.start_btn = ctk.CTkButton(self.btn_frame, text="▶ START RECORDING", fg_color="green", hover_color="darkgreen", font=ctk.CTkFont(weight="bold"), command=self.start_recording)
        self.start_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.stop_btn = ctk.CTkButton(self.btn_frame, text="⏹ STOP RECORDING", fg_color="red", hover_color="darkred", font=ctk.CTkFont(weight="bold"), state="disabled", command=self.stop_recording)
        self.stop_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Live Status Monitor
        self.status_label = ctk.CTkLabel(self, text="Ready to record. Select a label and press Start.", font=ctk.CTkFont(size=14))
        self.status_label.grid(row=3, column=0, padx=20, pady=20)

    def start_recording(self):
        global is_recording, current_label, recorded_data, frames_recorded
        
        # Priority to custom entry if filled
        custom_val = self.custom_entry.get().strip()
        if custom_val:
            current_label = custom_val.replace(" ", "_").lower()
        else:
            current_label = self.action_var.get()

        recorded_data = [] # Clear buffer
        frames_recorded = 0
        is_recording = True

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.action_menu.configure(state="disabled")
        self.custom_entry.configure(state="disabled")
        
        self.update_status(f"🔴 Recording '{current_label}'... (0 frames)", "red")

    def stop_recording(self):
        global is_recording
        is_recording = False
        
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.action_menu.configure(state="normal")
        self.custom_entry.configure(state="normal")
        
        self.update_status("Saving data...", "white")
        
        # Save payload
        success, msg = save_data_to_csv(current_label, recorded_data)
        
        color = "#2ecc71" if success else "#e67e22" # Using nice hex colors
        self.update_status(msg, color)

    def update_status(self, text, color="white"):
        self.status_label.configure(text=text, text_color=color)

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    
    app = DataCollectorApp()
    
    print("Starting background ESP32 HTTP Poller thread...")
    threading.Thread(target=http_poller, args=(app,), daemon=True).start()
    
    print("Opening CustomTkinter UI...")
    app.mainloop()
