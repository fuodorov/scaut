import os
import uuid
import csv
import json
import time
import itertools
import logging
import numpy as np
from tqdm import tnrange, tqdm_notebook

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from IPython.display import clear_output as cell_clear_output
import math
import pandas as pd

from ..core import config as cfg

scan_logger = logging.getLogger('Scan')


def create_output_directory(dirname):
    dir_path = os.path.abspath(os.path.join(dirname if dirname else "", f"{uuid.uuid4()}"))
    os.makedirs(dir_path, exist_ok=True)
    scan_logger.info(f"Created directory: {dir_path}")
    return dir_path


def save_data(data_filename, data):
    with open(data_filename, "w", newline="", encoding="utf-8") as f_out:
        json.dump(data, f_out)
        scan_logger.info(f"Data saved to file: {data_filename}")


def set_motor_value(motor_name, motor_value, get_func, put_func, verify_motor, max_retries, delay, tolerance):
    if verify_motor:
        for attempt in range(max_retries):
            put_func(motor_name, motor_value)
            time.sleep(delay)
            current_pos = get_func(motor_name)
            scan_logger.debug(f"Attempting to set {motor_name} to {motor_value}. Current position: {current_pos}")
            if abs(current_pos - motor_value) <= tolerance:
                scan_logger.info(f"{motor_name} successfully set to {motor_value}.")
                return True
        raise RuntimeError(
            f"Failed to set {motor_name} to {motor_value} "
            f"after {max_retries} attempts."
        )
    else:
        put_func(motor_name, motor_value)
        scan_logger.info(f"{motor_name} set to {motor_value} without verification.")
        return True


def collect_meters_data(meters, get_func, sample_size):
    data = {}
    for meter in tqdm_notebook(meters, desc="Collect data"):
        values = []
        for val in tnrange(sample_size, desc="Fetch"):
            values.append(get_func(meter))
        data[meter] = sum(values) / sample_size
        scan_logger.debug(f"Data collected for {meter}: {val}")
    return data


def plot_scan_data(step_data, step_count=cfg.SCAN_SHOW_LAST_STEP_NUMBERS):
    data = step_data["data"]
    metadata = step_data["metadata"]

    motors = metadata.get("motors", [])
    meters = metadata.get("meters", [])
    steps = metadata.get("steps", [])[-step_count:]
    step_numbers = [step["step_index"] for step in steps]
    
    num_motors = len(motors)
    num_meters = len(meters)
    
    max_cols = max(num_motors, num_meters)
    total_rows = 2

    fig, axes = plt.subplots(total_rows, max_cols, figsize=(5 * max_cols, 8))  # Сетка графиков
    fig.suptitle("Scan Data Plot", fontsize=16)

    if total_rows == 1:
        axes = [axes]

    if max_cols == 1:
        axes = [[ax] for ax in axes]

    for i, motor in enumerate(motors):
        row, col = 0, i
        ax = axes[row][col]
        motor_values = [step["motor_values"].get(motor, 0) for step in steps]
        ax.plot(step_numbers, motor_values, marker="o", label=f"Motor: {motor}")
        ax.set_title(f"Motor: {motor} Values by Steps")
        ax.set_xlabel("Steps")
        ax.set_ylabel("Motor Values")
        ax.grid(True)

    for j, meter in enumerate(meters):
        row, col = 1, j
        ax = axes[row][col]
        meter_values = [step["meter_data"].get(meter, 0) for step in steps]
        ax.plot(step_numbers, meter_values, marker="o", label=f"Meter: {meter}")
        ax.set_title(f"Meter: {meter} Values by Steps")
        ax.set_xlabel("Steps")
        ax.set_ylabel("Meter Values")
        ax.grid(True)

    for row in range(total_rows):
        for col in range(max_cols):
            if (row == 0 and col >= num_motors) or (row == 1 and col >= num_meters):
                fig.delaxes(axes[row][col])

    plt.tight_layout(rect=[0, 0, 1, 1])


def print_table_scan_data(step_data, step_count=cfg.SCAN_SHOW_LAST_STEP_NUMBERS):
    metadata = step_data["metadata"]
    steps = metadata.get("steps", [])[-step_count:]
    
    table_data = []
    for step in steps[::-1]:
        row = {}
        row.update({"Step": step.get('step_index', {})})
        row.update(step.get("motor_values", {}))
        row.update(step.get("meter_data", {}))
        table_data.append(row)
    
    df = pd.DataFrame(table_data)
    print("=== Scan Data Table ===\n")
    print(df.to_string(index=False))


def print_scan_data(step_data, step_count=cfg.SCAN_SHOW_LAST_STEP_NUMBERS):
    metadata = step_data["metadata"]
    steps = metadata.get("steps", [])[-step_count:]
    
    print("=== Scan Data ===")
    for step in steps[::-1]:
        print(f"Step {step.get("step_index", None)}:")
        print(f"  Motor Values: {step.get("motor_values", {})}")
        print(f"  Meter Data: {step.get("meter_data", {})}")
        print("-" * 40)


def plot_meters_data(step_data, step_count=cfg.SCAN_SHOW_LAST_STEP_NUMBERS):
    data = step_data["data"]
    metadata = step_data["metadata"]

    steps = metadata.get("steps", [])[-step_count:]
    step_numbers = [step["step_index"] for step in steps]
    last_step_index = steps[-1]["step_index"]
    
    meters = metadata.get("meters", [])
    meter_indices = range(len(meters))

    cmap = cm.binary
    norm = mcolors.Normalize(vmin=min(step_numbers)-1, vmax=max(step_numbers))
    scalar_map = cm.ScalarMappable(norm=norm, cmap=cmap)
    scalar_map.set_array([])

    fig, ax = plt.subplots(figsize=(12, 6))

    for step in steps:
        step_index = step["step_index"]
        meter_data = step.get("meter_data", {})
        y_values = [meter_data.get(meter, 0) for meter in meters]
        x_values = list(meter_indices)
        color = scalar_map.to_rgba(step_index)        
        marker = "." if step_index != last_step_index else "o"
        linestyle = "--" if step_index != last_step_index else "-"
        ax.plot(x_values, y_values, marker=marker, linestyle=linestyle, color=color)

    ax.set_xticks(meter_indices)
    ax.set_xticklabels(meters, rotation=45, ha='right')

    ax.set_title("Meters Data Plot", fontsize=16)
    ax.set_xlabel("Meters")
    ax.set_ylabel("Meter Values")

    cbar = fig.colorbar(scalar_map, ax=ax)
    cbar.set_label('Step Index')

    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_motors_data(step_data, step_count=cfg.SCAN_SHOW_LAST_STEP_NUMBERS):
    data = step_data["data"]
    metadata = step_data["metadata"]

    steps = metadata.get("steps", [])[-step_count:]
    step_numbers = [step["step_index"] for step in steps]
    last_step_index = steps[-1]["step_index"]
    
    motors = metadata.get("motors", [])
    motor_indices = range(len(motors))

    cmap = cm.binary
    norm = mcolors.Normalize(vmin=min(step_numbers)-1, vmax=max(step_numbers))
    scalar_map = cm.ScalarMappable(norm=norm, cmap=cmap)
    scalar_map.set_array([])

    fig, ax = plt.subplots(figsize=(12, 6))

    for step in steps:
        step_index = step["step_index"]
        motor_data = step.get("motor_values", {})
        y_values = [motor_data.get(motor, 0) for motor in motors]
        x_values = list(motor_indices)
        color = scalar_map.to_rgba(step_index)
        marker = "." if step_index != last_step_index else "o"
        linestyle = "--" if step_index != last_step_index else "-"
        ax.plot(x_values, y_values, marker=marker, linestyle=linestyle, color=color)

    ax.set_xticks(motor_indices)
    ax.set_xticklabels(motors, rotation=45, ha='right')

    ax.set_title("Motors Data Plot", fontsize=16)
    ax.set_xlabel("Motors")
    ax.set_ylabel("Motor Values")

    cbar = fig.colorbar(scalar_map, ax=ax)
    cbar.set_label('Step Index')

    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_response_matrix(step_data):
    metadata = step_data.get("metadata", {})
    
    if "response_matrix" not in metadata:
        return
        
    motors = metadata.get("motors", [])
    meters = metadata.get("meters", [])
    response_matrix = np.array(metadata["response_matrix"])

    fig, ax = plt.subplots(figsize=(10, 8))
    
    im = ax.imshow(response_matrix, aspect='auto', cmap='viridis')
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label('Response Value')

    ax.set_title("Response Matrix Heatmap", fontsize=16)
    ax.set_xlabel("Response Columns")
    ax.set_ylabel("Response Rows")

    num_rows, num_cols = response_matrix.shape
    ax.set_xticks(range(num_cols))
    ax.set_yticks(range(num_rows))
    
    ax.set_xticklabels(meters, rotation=45, ha='right')
    ax.set_yticklabels(motors)

    for i in range(num_rows):
        for j in range(num_cols):
            text = ax.text(j, i, f"{response_matrix[i, j]:.2f}", ha="center", va="center", color="w", fontsize=8)

    ax.grid(False)
    plt.tight_layout()
    plt.show()


def clear_output(*args):
    cell_clear_output(wait=True)
    