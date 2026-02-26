import os
import glob
import pandas as pd
import numpy as np
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Only import TF when actually compiling to save startup time
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.callbacks import Callback

class TkinterCallback(Callback):
    def __init__(self, update_func, total_epochs):
        super().__init__()
        self.update_func = update_func
        self.total_epochs = total_epochs

    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        val_acc = logs.get('val_accuracy', 0.0)
        acc = logs.get('accuracy', 0.0)
        loss = logs.get('loss', 0.0)
        
        msg = f"Epoch {epoch+1}/{self.total_epochs} - loss: {loss:.4f} - acc: {acc:.4f} - val_acc: {val_acc:.4f}"
        progress = (epoch + 1) / self.total_epochs
        
        # Cross thread update
        self.update_func(msg, progress)

class TrainerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SentinAI - Edge ML Trainer")
        self.geometry("600x650")
        
        # Variables
        self.dataset_path = ctk.StringVar(value=os.path.join(os.path.dirname(__file__), "dataset"))
        self.epochs = ctk.IntVar(value=50)
        self.batch_size = ctk.IntVar(value=32)
        
        self.build_ui()
        
    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        
        title = ctk.CTkLabel(self, text="SentinAI Model Trainer", font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, pady=(20, 10))
        
        # --- Config Frame ---
        config_frame = ctk.CTkFrame(self)
        config_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        config_frame.grid_columnconfigure(1, weight=1)
        
        # Dataset
        lbl_ds = ctk.CTkLabel(config_frame, text="Dataset Folder:")
        lbl_ds.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        ent_ds = ctk.CTkEntry(config_frame, textvariable=self.dataset_path, state="disabled")
        ent_ds.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        btn_ds = ctk.CTkButton(config_frame, text="Browse", width=80, command=self.browse_folder)
        btn_ds.grid(row=0, column=2, padx=10, pady=10)
        
        # Epochs
        lbl_ep = ctk.CTkLabel(config_frame, text="Epochs:")
        lbl_ep.grid(row=1, column=0, padx=10, pady=(10, 0), sticky="w")
        
        ent_ep = ctk.CTkEntry(config_frame, textvariable=self.epochs)
        ent_ep.grid(row=1, column=1, padx=10, pady=(10, 0), sticky="ew", columnspan=2)
        
        desc_ep = ctk.CTkLabel(config_frame, text="How many times the AI loops over the data. 50-100 is good.", font=ctk.CTkFont(size=11), text_color="gray")
        desc_ep.grid(row=2, column=1, padx=10, pady=0, sticky="w")
        
        # Batch Size
        lbl_bs = ctk.CTkLabel(config_frame, text="Batch Size:")
        lbl_bs.grid(row=3, column=0, padx=10, pady=(10, 0), sticky="w")
        
        ent_bs = ctk.CTkEntry(config_frame, textvariable=self.batch_size)
        ent_bs.grid(row=3, column=1, padx=10, pady=(10, 0), sticky="ew", columnspan=2)
        
        desc_bs = ctk.CTkLabel(config_frame, text="How many samples to study at once. Try 8, 16, or 32.", font=ctk.CTkFont(size=11), text_color="gray")
        desc_bs.grid(row=4, column=1, padx=10, pady=0, sticky="w")
        
        # --- Actions Frame ---
        self.train_btn = ctk.CTkButton(self, text="▶ TRAIN MODEL", fg_color="green", hover_color="darkgreen", font=ctk.CTkFont(weight="bold", size=16), command=self.start_training_thread)
        self.train_btn.grid(row=2, column=0, pady=20, padx=20, sticky="ew")
        
        # --- Log Console ---
        self.log_textbox = ctk.CTkTextbox(self, height=200, state="disabled")
        self.log_textbox.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="nsew")
        
        # --- Progress Bar ---
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.progress_bar.set(0)

    def log(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
        
    def progress_update(self, msg, progress_val):
        self.log(msg)
        self.progress_bar.set(progress_val)

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.dataset_path.get())
        if folder:
            self.dataset_path.set(folder)
            
    def start_training_thread(self):
        self.train_btn.configure(state="disabled", text="TRAINING...")
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self.progress_bar.set(0)
        
        t = threading.Thread(target=self.run_training, daemon=True)
        t.start()
        
    def run_training(self):
        try:
            folder = self.dataset_path.get()
            epochs = self.epochs.get()
            batch_size = self.batch_size.get()
            
            self.log(f"Starting Training Run...")
            self.log(f"Dataset: {folder}")
            self.log(f"Epochs: {epochs} | Batch Size: {batch_size}")
            
            X, y = self.load_data(folder)
            
            if len(X) == 0:
                self.log("ERROR: No valid data found for training!")
                self.after(0, self.training_finished, False)
                return
                
            self.log(f"Extracted {len(X)} training samples.")
            
            # Shuffling
            indices = np.arange(len(X))
            np.random.shuffle(indices)
            X = X[indices]
            y = y[indices]
            
            # Simple TF Model Architecture (Matching analyzer.py expectations)
            # Input dimension is exactly 20 * (10 subcarriers * 4 nodes) = 800
            model = Sequential([
                tf.keras.Input(shape=(len(X[0]),)),
                Dense(128, activation='relu'),
                Dropout(0.3),
                Dense(64, activation='relu'),
                Dense(1, activation='sigmoid')
            ])
            
            model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
            
            # Re-compile the callback list properly since lambda fails scoping sometimes
            class InnerTkinterCallback(Callback):
                def on_epoch_end(inner_self, epoch, logs=None):
                    logs = logs or {}
                    val_acc = logs.get('val_accuracy', 0.0)
                    acc = logs.get('accuracy', 0.0)
                    loss = logs.get('loss', 0.0)
                    msg = f"Epoch {epoch+1}/{epochs} - loss: {loss:.4f} - acc: {acc:.4f} - val_acc: {val_acc:.4f}"
                    progress = (epoch + 1) / epochs
                    self.after(0, self.progress_update, msg, progress)
                    
            self.log("Beginning fitting...")
            
            # Since custom callbacks can crash with Tkinter threads sometimes if not careful, we catch
            try:
                model.fit(
                    X, y,
                    epochs=epochs,
                    batch_size=batch_size,
                    validation_split=0.2, # 20% validation
                    callbacks=[InnerTkinterCallback()],
                    verbose=0
                )
            except Exception as e:
                self.log(f"Callback Thread Error: {e}\nFitting without visual updates...")
                model.fit(X, y, epochs=epochs, batch_size=batch_size, validation_split=0.2, verbose=1)
            
            # Save the model relative to the execution context generally where backend expects it
            save_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "csi_fall_model.keras")
            model.save(save_path)
            self.log(f"\n✅ Training Complete! Model saved successfully to:")
            self.log(f"{save_path}")
            
            self.after(0, self.training_finished, True)
            
        except Exception as e:
            self.log(f"\n❌ ERROR DURING TRAINING:\n{str(e)}")
            self.after(0, self.training_finished, False)

    def load_data(self, dataset_folder):
        csv_files = glob.glob(os.path.join(dataset_folder, "**/*.csv"), recursive=True)
        if not csv_files:
            return np.array([]), np.array([])
            
        X_all = []
        Y_all = []
        
        self.log(f"Found {len(csv_files)} total CSV files. Processing...")
        
        for file in csv_files:
            try:
                df = pd.read_csv(file)
                if len(df) < 20: continue
                
                # Check actual available subcarrier columns per node
                node_cols_map = {}
                for node in ["ESP32_NODE_1", "ESP32_NODE_2", "ESP32_NODE_3", "ESP32_NODE_4"]:
                     node_cols_map[node] = [c for c in df.columns if node in c and "_sub_" in c]
                
                # Create rolling windows of length 20
                for i in range(len(df) - 20):
                    window = df.iloc[i:i+20]
                    
                    window_features = []
                    # We need shape (20, 40) where 20 is time steps, 40 is features (10 * 4 nodes)
                    # Let's flatten that into (800,)
                    for frame_idx in range(20):
                        frame_row = window.iloc[frame_idx]
                        frame_vals = []
                        for node in ["ESP32_NODE_1", "ESP32_NODE_2", "ESP32_NODE_3", "ESP32_NODE_4"]:
                            cols = node_cols_map[node]
                            if len(cols) > 0:
                                # Cast to float, fill NaN with 0
                                # Take up to 10 subcarriers
                                vals = pd.to_numeric(frame_row[cols[:10]], errors='coerce').fillna(0).values
                                # pad if less than 10
                                if len(vals) < 10:
                                     vals = np.pad(vals, (0, 10 - len(vals)))
                            else:
                                vals = np.zeros(10)
                            frame_vals.extend(vals)
                        window_features.extend(frame_vals)
                    
                    # Store as flattened array of 800 floats (20 frames * 40 features)
                    X_all.append(np.array(window_features, dtype=np.float32) / 255.0)
                    
                    # Labels: if string contains 'fall', it's 1, else 0.
                    label_str = str(df.iloc[i+10]['label']).lower()
                    if 'fall' in label_str:
                        Y_all.append(1)
                    else:
                        Y_all.append(0)
            except Exception as e:
                pass
                
        return np.array(X_all), np.array(Y_all)

    def training_finished(self, success):
        self.train_btn.configure(state="normal", text="▶ TRAIN MODEL")
        if success:
            messagebox.showinfo("Success", "Model trained and saved successfully!")
        else:
            self.progress_bar.set(0)
            messagebox.showerror("Error", "Training failed. See console log for details.")

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = TrainerApp()
    app.mainloop()
