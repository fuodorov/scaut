import os
import uuid
import csv
import json
import time
import itertools
import logging
from tqdm import tqdm

import matplotlib.pyplot as plt
from IPython.display import clear_output
import math
import pandas as pd

from ...core import config as cfg

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


def collect_meters_data(meters, get_func):
    data = {}
    for meter in meters:
        val = get_func(meter)
        data[meter] = val
        scan_logger.debug(f"Data collected for {meter}: {val}")
    return data


def plot_scan_data(step_data, step_count=cfg.SCAN_SHOW_LAST_STEP_NUMBERS):
    data = step_data["data"]
    metadata = step_data["metadata"]

    motors = list(data.keys())
    meters = set()

    for motor_data in data.values():
        for motor_value_data in motor_data.values():
            meters.update(motor_value_data.keys())

    meters = sorted(meters)

    steps = metadata.get("steps", [])[-step_count:]
    step_numbers = [step["step_index"] for step in steps]
    clear_output(wait=True)
    
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
    plt.pause(0.1)


def print_table_scan_data(step_data, step_count=cfg.SCAN_SHOW_LAST_STEP_NUMBERS):
    metadata = step_data["metadata"]
    steps = metadata.get("steps", [])[-step_count:]
    clear_output(wait=True)
    
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
    clear_output(wait=True)
    
    print("=== Scan Data ===")
    for step in steps[::-1]:
        print(f"Step {step.get("step_index", None)}:")
        print(f"  Motor Values: {step.get("motor_values", {})}")
        print(f"  Meter Data: {step.get("meter_data", {})}")
        print("-" * 40)
