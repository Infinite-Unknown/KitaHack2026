import os
import glob
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Conv1D, MaxPooling1D, Flatten, BatchNormalization
from sklearn.model_selection import train_test_split

DATASET_DIR = "../train/dataset"
MODEL_SAVE_PATH = "csi_fall_model.keras"

# Window size in snapshots
WINDOW_SIZE = 20
NUM_FEATURES = 30  # 10 subcarriers * 3 nodes
STRIDE = 2  # Smaller stride = more overlapping windows = more training data

NODE_SUB_COLS = []
for node in ["ESP32_NODE_1", "ESP32_NODE_2", "ESP32_NODE_3"]:
    for i in range(10):
        NODE_SUB_COLS.append(f"{node}_sub_{i}")

def extract_all_windows(file_path):
    """
    Extract ALL overlapping sliding windows from a CSV file.
    This massively multiplies our training data from each recording.
    """
    df = pd.read_csv(file_path)
    if len(df) < WINDOW_SIZE:
        print(f"  Skipping {file_path} (Too short: {len(df)} rows)")
        return []

    # Pad missing columns with zeros
    for col in NODE_SUB_COLS:
        if col not in df.columns:
            df[col] = 0

    # Extract the numeric matrix
    data_matrix = df[NODE_SUB_COLS].apply(pd.to_numeric, errors='coerce').fillna(0).values

    windows = []
    for start in range(0, len(data_matrix) - WINDOW_SIZE + 1, STRIDE):
        window = data_matrix[start:start + WINDOW_SIZE]
        if window.shape == (WINDOW_SIZE, NUM_FEATURES):
            windows.append(window)

    return windows

def load_data():
    X = []
    y = []

    files = glob.glob(os.path.join(DATASET_DIR, "*.csv"))
    print(f"Found {len(files)} CSV files.\n")

    fall_count = 0
    normal_count = 0

    for f in files:
        filename = os.path.basename(f).lower()
        label = 1 if 'fall' in filename else 0

        windows = extract_all_windows(f)
        for w in windows:
            X.append(w)
            y.append(label)

        if label == 1:
            fall_count += len(windows)
        else:
            normal_count += len(windows)

        print(f"  {filename} -> {len(windows)} windows | Label: {'FALL' if label == 1 else 'NORMAL'}")

    print(f"\nTotal windows: FALL={fall_count}, NORMAL={normal_count}")

    # Balance classes by oversampling the minority class
    X = np.array(X)
    y = np.array(y)

    fall_idx = np.where(y == 1)[0]
    normal_idx = np.where(y == 0)[0]

    if len(fall_idx) > 0 and len(normal_idx) > 0:
        max_class_size = max(len(fall_idx), len(normal_idx))

        # Oversample minority class
        if len(fall_idx) < max_class_size:
            extra = np.random.choice(fall_idx, max_class_size - len(fall_idx), replace=True)
            fall_idx = np.concatenate([fall_idx, extra])
        elif len(normal_idx) < max_class_size:
            extra = np.random.choice(normal_idx, max_class_size - len(normal_idx), replace=True)
            normal_idx = np.concatenate([normal_idx, extra])

        balanced_idx = np.concatenate([fall_idx, normal_idx])
        np.random.shuffle(balanced_idx)
        X = X[balanced_idx]
        y = y[balanced_idx]
        print(f"After balancing: {len(X)} total samples (FALL={np.sum(y==1)}, NORMAL={np.sum(y==0)})")

    return X, y

def build_model(input_shape):
    """
    Simpler CNN model (no LSTM) — works much better with small datasets.
    """
    model = Sequential([
        Conv1D(filters=32, kernel_size=3, activation='relu', input_shape=input_shape),
        BatchNormalization(),
        MaxPooling1D(pool_size=2),

        Conv1D(filters=64, kernel_size=3, activation='relu'),
        BatchNormalization(),
        MaxPooling1D(pool_size=2),
        Dropout(0.3),

        Flatten(),
        Dense(32, activation='relu'),
        Dropout(0.3),
        Dense(1, activation='sigmoid')
    ])

    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def main():
    print("=" * 50)
    print("SentinAI TensorFlow Model Trainer v2")
    print("=" * 50)

    print("\nLoading datasets...")
    X, y = load_data()

    if len(X) == 0:
        print("No valid data found! Please add CSVs to the dataset folder.")
        return

    print(f"\nFinal data shape: X={X.shape}, y={y.shape}")

    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # Normalize
    X_train = X_train / 255.0
    X_test = X_test / 255.0

    print("\nBuilding Model...")
    model = build_model((WINDOW_SIZE, NUM_FEATURES))
    model.summary()

    print("\nTraining Model...")
    lr_scheduler = tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=10, min_lr=1e-6, verbose=1)
    model.fit(
        X_train, y_train,
        epochs=100,
        batch_size=8,
        validation_data=(X_test, y_test),
        callbacks=[lr_scheduler],
        verbose=1
    )

    # Evaluate
    print("\n" + "=" * 50)
    print("Final Evaluation:")
    loss, acc = model.evaluate(X_test, y_test, verbose=0)
    print(f"  Test Loss: {loss:.4f}")
    print(f"  Test Accuracy: {acc*100:.1f}%")

    # Show predictions on test set
    preds = model.predict(X_test, verbose=0)
    print(f"\n  Prediction range: {preds.min()*100:.1f}% - {preds.max()*100:.1f}%")
    print(f"  Mean prediction for FALL samples: {preds[y_test==1].mean()*100:.1f}%")
    print(f"  Mean prediction for NORMAL samples: {preds[y_test==0].mean()*100:.1f}%")
    print("=" * 50)

    print(f"\nSaving Keras model to {MODEL_SAVE_PATH}...")
    model.save(MODEL_SAVE_PATH)

    print("\nSUCCESS! Model is ready for backend inference.")

if __name__ == "__main__":
    main()
