import os
import uuid
import csv
import json
import time
import itertools
import logging
import numpy as np
from tqdm import tnrange, tqdm_notebook
import concurrent.futures

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from IPython.display import clear_output as cell_clear_output
import pandas as pd

from ..core import config as cfg
from .exceptions import ScanMeterValueError

scan_logger = logging.getLogger('Scan')


def create_output_path(prefix_path, name=None):
    if not name:
        name = f"{uuid.uuid4()}.json"
    if prefix_path:
        os.makedirs(prefix_path, exist_ok=True)
    path = os.path.abspath(os.path.join(prefix_path if prefix_path else "", name))
    scan_logger.info(f"Created path: {path}")
    return path


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


def set_motors_values(motor_names, combination, get_func, put_func, verify_motor,
                      max_retries, delay, tolerance, parallel=False):
    if parallel:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    set_motor_value,
                    motor_name,
                    motor_value,
                    get_func,
                    put_func,
                    verify_motor,
                    max_retries,
                    delay,
                    tolerance,
                ): motor_name
                for motor_name, motor_value in zip(motor_names, combination)
            }
            for future in tqdm_notebook(
                concurrent.futures.as_completed(futures),
                total=len(futures),
                desc="Set motor values",
                disable=cfg.TQDM_DISABLE,
            ):
                future.result()
    else:
        for motor_name, motor_value in tqdm_notebook(
            zip(motor_names, combination),
            total=len(motor_names),
            desc="Set motor values",
            disable=cfg.TQDM_DISABLE,
        ):
            set_motor_value(motor_name, motor_value, get_func, put_func,
                    verify_motor, max_retries, delay, tolerance)
            scan_logger.info(f"Motor '{motor_name}' set to value {motor_value}")
            

def get_meter_data(meter, get_func, sample_size, delay):
    values = []
    for _ in range(sample_size):
        values.append(get_func(meter))
        time.sleep(delay)
        
    avg = sum(values) / sample_size
    std = np.sqrt(sum((x - avg) ** 2 for x in values) / sample_size)
    scan_logger.debug(f"Data collected for {meter}: avg = {avg}, std = {std}")
    return meter, avg, std


def get_meters_data(meters, get_func, sample_size, delay=0, parallel=False, limits=None, strict_check=False):
    data, error_data = {}, {}
    if parallel:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(get_meter_data, meter, get_func, sample_size, delay): meter
                for meter in meters
            }
            for future in tqdm_notebook(concurrent.futures.as_completed(futures),
                               total=len(futures),
                               desc="Collect data",
                               disable=cfg.TQDM_DISABLE):
                meter, avg, sem = future.result()
                data[meter] = avg
                error_data[meter] = sem
    else:
        for meter in tqdm_notebook(meters, desc="Collect data", disable=cfg.TQDM_DISABLE):
            meter, avg, sem = get_meter_data(meter, get_func, sample_size, delay)
            data[meter] = avg
            error_data[meter] = sem
            
    if limits:
        for meter_name, meter_range in zip(meters, limits):
            measured_avg = data.get(meter_name, {})
            lower_limit, upper_limit = min(meter_range), max(meter_range)
            if measured_avg < lower_limit or measured_avg > upper_limit:
                msg = (f"Device '{meter_name}' measured value = {measured_avg} "
                       f"outside the allowed range ({lower_limit}, {upper_limit})")
                scan_logger.warning(msg)
                if strict_check:
                    raise ScanMeterValueError(msg)
                    
    return data, error_data


def plot_scan_data(scan_data, step_range=None):
    all_steps = scan_data.get("steps", [])
    motors = scan_data.get("motors", [])
    meters = scan_data.get("meters", [])
    if step_range is not None:
        min_index, max_index = step_range
        steps = [step for step in all_steps
                 if min_index <= step.get("step_index", 0) <= max_index]
    else:
        steps = all_steps[-cfg.SCAN_SHOW_LAST_STEP_NUMBERS:]
    
    if not steps:
        return
        
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


def print_table_scan_data(scan_data, step_range=None):
    all_steps = scan_data.get("steps", [])
    if step_range is not None:
        min_index, max_index = step_range
        steps = [step for step in all_steps
                 if min_index <= step.get("step_index", 0) <= max_index]
    else:
        steps = all_steps[-cfg.SCAN_SHOW_LAST_STEP_NUMBERS:]
    
    if not steps:
        return
    
    table_data = []
    for step in steps[::-1]:
        row = {}
        row.update({"Step": step.get('step_index', {})})
        row.update(step.get("motor_values", {}))
        row.update(step.get("meter_data", {}))
        row.update(step.get("meter_errors", {}))
        table_data.append(row)
    
    df = pd.DataFrame(table_data)
    print("=== Scan Data Table ===\n")
    print(df.to_string(index=False))


def print_scan_data(scan_data, step_range=None):
    scan_data = scan_data["scan_data"]
    if step_range is not None:
        min_index, max_index = step_range
        steps = [step for step in all_steps
                 if min_index <= step.get("step_index", 0) <= max_index]
    else:
        steps = all_steps[-cfg.SCAN_SHOW_LAST_STEP_NUMBERS:]
    
    if not steps:
        return
    
    print("=== Scan Data ===")
    for step in steps[::-1]:
        print(f"Step {step.get('step_index', None)}:")
        print(f"  Motor Values: {step.get('motor_values', {})}")
        print(f"  Meter Data: {step.get('meter_data', {})}")
        print(f"  Meter Errors: {step.get('meter_errors', {})}")
        print("-" * 40)


def plot_generic_data(scan_data, items_key, step_value_key, title, xlabel, ylabel,
                      step_range=None, limits_key=None, errors_key=None):
    items = scan_data.get(items_key, [])
    all_steps = scan_data.get("steps", [])
    if step_range is not None:
        min_index, max_index = step_range
        steps = [step for step in all_steps
                 if min_index <= step.get("step_index", 0) <= max_index]
    else:
        steps = all_steps[-cfg.SCAN_SHOW_LAST_STEP_NUMBERS:]
    
    if not steps:
        return
        
    step_numbers = [step.get("step_index") for step in steps]
    last_step_index = steps[-1].get("step_index")
    item_indices = range(len(items))

    cmap = cm.binary
    norm = mcolors.Normalize(vmin=min(step_numbers) - 1, vmax=max(step_numbers))
    scalar_map = cm.ScalarMappable(norm=norm, cmap=cmap)
    scalar_map.set_array([])

    fig, ax = plt.subplots(figsize=(12, 6))

    for step in steps:
        step_index = step.get("step_index")
        values_dict = step.get(step_value_key, {})
        y_values = [values_dict.get(item, 0) for item in items]
        x_values = list(item_indices)
        color = scalar_map.to_rgba(step_index)
        marker = "." if step_index != last_step_index else "o"
        linestyle = "--" if step_index != last_step_index else "-"
        if errors_key and step_index == last_step_index:
            errors_dict = step.get(errors_key, {})
            y_errors = [errors_dict.get(item, 0) for item in items]
            ax.errorbar(x_values, y_values, yerr=y_errors, fmt=marker,
                        linestyle=linestyle, color=color, capsize=3)
        else:
            ax.plot(x_values, y_values, marker=marker, linestyle=linestyle, color=color)

    if limits_key:
        limits_dict = scan_data.get(limits_key, {})
        for i, item in enumerate(items):
            limits = limits_dict.get(item)
            if limits is not None and isinstance(limits, (list, tuple)) and len(limits) == 2:
                dx = 0.1
                ax.hlines(y=limits[0], xmin=i - dx, xmax=i + dx,
                          colors='red', linestyles='dashed', linewidth=2,
                          label=f"{item} limits" if i == 0 else None)
                ax.hlines(y=limits[1], xmin=i - dx, xmax=i + dx,
                          colors='red', linestyles='dashed', linewidth=2)

    ax.set_xticks(list(item_indices))
    ax.set_xticklabels(items, rotation=45, ha='right')
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    cbar = fig.colorbar(scalar_map, ax=ax)
    cbar.set_label('Step Index')

    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_meters_data(scan_data):
    plot_generic_data(
        scan_data,
        items_key="meters",
        step_value_key="meter_data",
        title="Data Plot",
        xlabel="Devices",
        ylabel="Device Values",
        limits_key="meter_ranges",
        errors_key="meter_errors"
    )


def plot_checks_data(scan_data):
    plot_generic_data(
        scan_data,
        items_key="checks",
        step_value_key="check_data",
        title="Data Plot",
        xlabel="Devices",
        ylabel="Device Values",
        limits_key="check_ranges",
        errors_key="check_errors"
    )


def plot_motors_data(scan_data):
    plot_generic_data(
        scan_data,
        items_key="motors",
        step_value_key="motor_values",
        title="Data Plot",
        xlabel="Devices",
        ylabel="Device Values",
    )


def plot_response_matrix(scan_data):  
    if "response_matrix" not in scan_data:
        return
        
    motors = scan_data.get("motors", [])
    meters = scan_data.get("meters", [])
    response_matrix = np.array(scan_data["response_matrix"])

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


def truncated_pinv(A, num_singular_values=None, rcond=1e-15):
    U, s, Vh = np.linalg.svd(A, full_matrices=False)
    
    if num_singular_values is not None:
        k = min(num_singular_values, s.shape[0])
        U = U[:, :k]
        s = s[:k]
        Vh = Vh[:k, :]
    
    s_inv = np.array([1/x if x > rcond else 0 for x in s])
    
    A_pinv = np.dot(Vh.T, np.dot(np.diag(s_inv), U.T))
    return A_pinv