import sys
import json
import os
import glob
import matplotlib.pyplot as plt

# Get the directory from command line arguments
if len(sys.argv) < 2:
    print("Usage: python plot_progress.py <directory>")
    sys.exit(1)

directory = sys.argv[1]

# Find the experiment_state JSON file in the given directory
file_pattern = os.path.join(directory, 'experiment_state*.json')
file_list = glob.glob(file_pattern)

if not file_list:
    print(f"No experiment_state JSON file found in directory: {directory}")
    sys.exit(1)

file_path = file_list[0]

# Read the JSON file
with open(file_path, 'r') as file:
    data = json.load(file)

# Extract trial data
trial_data = data.get('trial_data', [])

# Initialize lists to store progress data
wirelength_progress = []
performance_progress = []
wl_ecp_progress = []
iterations = []

# Iterate through trial data to extract required metrics
for i, trial in enumerate(trial_data):
    trial_info = json.loads(trial[0])
    trial_result = json.loads(trial[1])
    last_result = trial_result.get('last_result', {})
    wirelength = last_result.get('wirelength')
    performance = last_result.get('performance')
    wl_ecp = last_result.get('WL_ECP')
    iteration = last_result.get('training_iteration')

    if wl_ecp is not None and wl_ecp < 1e9:
        wirelength_progress.append(wirelength)
        performance_progress.append(performance)
        wl_ecp_progress.append(wl_ecp)
        iterations.append(i)

# Plot the progress
plt.figure(figsize=(12, 6))

plt.subplot(3, 1, 1)
plt.plot(iterations, wirelength_progress, marker='o')
plt.title('Wirelength Progress')
plt.xlabel('Iteration')
plt.ylabel('Wirelength')

plt.subplot(3, 1, 2)
plt.plot(iterations, performance_progress, marker='o')
plt.title('Performance Progress')
plt.xlabel('Iteration')
plt.ylabel('Performance')

plt.subplot(3, 1, 3)
plt.plot(iterations, wl_ecp_progress, marker='o')
plt.title('WL_ECP Progress')
plt.xlabel('Iteration')
plt.ylabel('WL_ECP')

plt.tight_layout()

# Save the plot to a file
output_file_path = f'{directory}/plot_progress.png'
plt.savefig(output_file_path)

# Optionally, close the plot to free up memory
plt.close()

