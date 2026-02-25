import os
import glob
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Conv1D, MaxPooling1D, Flatten, LSTM
from sklearn.model_selection import train_test_split

DATASET_DIR = "../train/dataset"
MODEL_SAVE_PATH = "csi_fall_model.keras"
TFLITE_SAVE_PATH = "csi_fall_model.tflite"

# Window size in snapshots (10 snapshots/sec * 2 seconds = 20 frames)
WINDOW_SIZE = 20
NUM_FEATURES = 30 # 10 subcarriers * 3 nodes

def parse_csv_to_windows(file_path):
    """
    Parses a CSI CSV file and extracts sliding 20-frame windows.
    Since one CSV is a single event, we extract the window with the highest variance.
    """
    df = pd.read_csv(file_path)
    if len(df) < WINDOW_SIZE:
        print(f"Skipping {file_path} (Too short: {len(df)} rows)")
        return None
        
    node_sub_cols = []
    for node in ["ESP32_NODE_1", "ESP32_NODE_2", "ESP32_NODE_3"]:
        for i in range(10):
            node_sub_cols.append(f"{node}_sub_{i}")
            
    # Quick fix for missing columns or mismatched data
    available_cols = [c for c in node_sub_cols if c in df.columns]
    if len(available_cols) != 30:
        print(f"Warning: {file_path} does not have exactly 30 subcarrier columns. Padding missing.")
        for missing in set(node_sub_cols) - set(available_cols):
            df[missing] = 0
            
    # Calculate best window (max variance)
    max_var = -1
    best_start = 0
    node_1_cols = [c for c in df.columns if "ESP32_NODE_1_sub_0" in c]
    
    for i in range(len(df) - WINDOW_SIZE):
        try:
            window_var = sum(np.var(pd.to_numeric(df[col].iloc[i:i+WINDOW_SIZE], errors='coerce').fillna(0)) for col in node_1_cols)
            if window_var > max_var:
                max_var = window_var
                best_start = i
        except Exception:
            pass
            
    # (Removed hardcoded window selection to generalize across new datasets)
            
    chunk = df.iloc[best_start:best_start+WINDOW_SIZE]
    
    # Parse strictly into integers
    window_data = []
    for i in range(len(chunk)):
        row_vals = chunk[node_sub_cols].iloc[i].values
        frame = []
        for v in row_vals:
            try:
                frame.append(float(v))
            except (ValueError, TypeError):
                frame.append(0.0)
        window_data.append(frame)
        
    return np.array(window_data)

def load_data():
    X = []
    y = []
    
    files = glob.glob(os.path.join(DATASET_DIR, "*.csv"))
    print(f"Found {len(files)} CSV files.")
    
    for f in files:
        filename = os.path.basename(f).lower()
        # Labeling rules: 1 for FALL, 0 for NORMAL
        label = 1 if 'fall' in filename else 0
        
        window = parse_csv_to_windows(f)
        if window is not None and window.shape == (WINDOW_SIZE, NUM_FEATURES):
            X.append(window)
            y.append(label)
            print(f"Loaded {filename} | Label: {label}")
        else:
            print(f"Failed to load valid window from {filename}")
            
    return np.array(X), np.array(y)

def build_model(input_shape):
    model = Sequential([
        # 1D Convolution to find temporal patterns in the subcarriers
        Conv1D(filters=32, kernel_size=3, activation='relu', input_shape=input_shape),
        MaxPooling1D(pool_size=2),
        Dropout(0.2),
        
        # LSTM to track the time-series sequence changes
        LSTM(32, return_sequences=False),
        Dropout(0.2),
        
        Dense(16, activation='relu'),
        # Output layer: 1 node with Sigmoid (Probability of FALL)
        Dense(1, activation='sigmoid')
    ])
    
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def main():
    print("Loading datasets...")
    X, y = load_data()
    
    if len(X) == 0:
        print("No valid data found! Please add CSVs to the dataset folder.")
        return
        
    print(f"Data shape: X={X.shape}, y={y.shape}")
    
    # Normally we split train/test, but if dataset is very small, we might skip it
    if len(X) > 5:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    else:
        print("Dataset too small for train/test split. Training on all data.")
        X_train, y_train = X, y
        X_test, y_test = X, y

    # Normalize data (CSI values are usually 0-255)
    X_train = X_train / 255.0
    X_test  = X_test / 255.0

    print("Building Model...")
    model = build_model((WINDOW_SIZE, NUM_FEATURES))
    model.summary()
    
    print("Training Model...")
    model.fit(X_train, y_train, epochs=30, batch_size=4, validation_data=(X_test, y_test))
    
    print(f"Saving Keras model to {MODEL_SAVE_PATH}...")
    model.save(MODEL_SAVE_PATH)
    
    print("Converting to TensorFlow Lite (for edge deployment)...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    # Enable optimizations for size/latency
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    
    # Enable Select TF ops for LSTM support
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS, 
        tf.lite.OpsSet.SELECT_TF_OPS
    ]
    converter._experimental_lower_tensor_list_ops = False
    
    tflite_model = converter.convert()

    with open(TFLITE_SAVE_PATH, 'wb') as f:
        f.write(tflite_model)
    print(f"TF Lite model saved to {TFLITE_SAVE_PATH}")
    
    print("\nSUCCESS! Models are ready for the backend inference.")

if __name__ == "__main__":
    main()
