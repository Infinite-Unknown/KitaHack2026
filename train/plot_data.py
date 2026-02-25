import pandas as pd
import matplotlib.pyplot as plt
import glob
import os

DATA_DIR = "dataset"
output_dir = "plots"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))

if not csv_files:
    print(f"No CSV files found in {DATA_DIR}/")
    exit()

print(f"Found {len(csv_files)} recorded sessions. Generating plots...")

for file in csv_files:
    # Extract the label from the filename (e.g., "falling_2026.csv" -> "falling")
    basename = os.path.basename(file)
    label = basename.split('_')[0]
    
    df = pd.read_csv(file)
    
    # We only plot the first node's data for visual simplicity
    # The columns are named like ESP32_NODE_1_sub_0, ESP32_NODE_1_sub_1, etc.
    node1_cols = [c for c in df.columns if "NODE_1" in c]
    
    if not node1_cols:
        print(f"Skipping {basename} - no NODE_1 data found.")
        continue
        
    plt.figure(figsize=(12, 6))
    
    # Plot the first 5 subcarriers for readability
    for col in node1_cols[:5]:
        plt.plot(df['timestamp'] - df['timestamp'].iloc[0], df[col], label=col.split('_')[-1], alpha=0.7)
        
    plt.title(f"CSI Amplitude Signature: {label.upper()}")
    plt.xlabel("Time (seconds)")
    plt.ylabel("CSI Amplitude")
    plt.grid(True, alpha=0.3)
    plt.legend(title="Subcarrier", loc='upper right')
    
    plot_path = os.path.join(output_dir, f"{label}_plot.png")
    plt.savefig(plot_path)
    plt.close()
    print(f"Saved plot: {plot_path}")

print("Done! Check the 'plots' folder.")
