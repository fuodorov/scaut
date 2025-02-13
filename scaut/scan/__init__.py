import os
import itertools
from datetime import datetime
from tqdm import tnrange, tqdm_notebook
from tqdm.contrib import tzip

from ..core import config as cfg
from .utils import (
    create_output_path,
    save_data,
    set_motors_values,
    get_meters_data,
    scan_logger,
)
from .decorators import response_measurements, bayesian_optimization, watch_measurements
from .exceptions import ScanMeterValueError


def scan(meters, motors, checks=[], *, get_func, put_func, verify_motor=True, 
         max_retries=cfg.SCAN_MAX_TRIES, delay=cfg.SCAN_DELAY, tolerance=cfg.SCAN_TOLERANCE, 
         previous_scan=None, save=False, path=cfg.DATA_DIR, name=None,
         callback=[], save_original_motor_values=True, sample_size=cfg.SCAN_SAMPLE_SIZE,
         parallel=cfg.SCAN_PARALLEL, repeat=cfg.SCAN_REPEAT, strict_check=False,
):
    data = previous_scan or {}
    original_motor_values = {}
    motor_names, motor_ranges = [motor[0] for motor in motors], [motor[1] for motor in motors]
    meter_names, meter_ranges = [meter[0] for meter in meters], [meter[1] for meter in meters]
    check_names, check_ranges = [check[0] for check in checks], [check[1] for check in checks]
    all_combinations = list(itertools.product(*motor_ranges))
    
    if save_original_motor_values:
        try:
            original_motor_values, _ = get_meters_data(motor_names, get_func, sample_size, delay, parallel)
        except Exception as e:
            scan_logger.error(f"Error getting initial value for motor '{motor_name}': {e}")
            raise RuntimeError(f"Failed to retrieve initial motor value for '{motor_name}'")
   
    data["data"] = {}        
    data["scan_start_time"] = data.get("scan_start_time", datetime.now().isoformat())
    data["motors"] = motor_names
    data["original_motor_values"] =  original_motor_values
    data["meters"] = meter_names
    data["meter_ranges"] = {meter_name: meter_range for meter_name, meter_range in zip(meter_names, meter_ranges)}
    data["checks"] = check_names
    data["check_ranges"] = {check_name: check_range for check_name, check_range in zip(check_names, check_ranges)}
    data["parameters"] = {
        "save": save, 
        "verify_motor": verify_motor, 
        "max_retries": max_retries, 
        "delay": delay, 
        "tolerance": tolerance, 
        "sample_size": sample_size
    }
    scan_logger.info("Starting scan process")
    scan_logger.info(f"Motors: {motor_names}")
    scan_logger.info(f"Motor value combinations: {all_combinations}")

    try:
        for step_index, combination in enumerate(all_combinations*repeat):
            scan_logger.info(f"Step {step_index + 1}/{len(all_combinations)}: Setting motor combination: {combination}")
            set_motors_values(motor_names, combination, get_func, put_func, verify_motor, max_retries, delay, tolerance, parallel)
            check_data, check_errors = get_meters_data(check_names, get_func, sample_size, delay, parallel, check_ranges, strict_check)
            scan_logger.info(f"Collected data from checks: {check_data}")
            meter_data, meter_errors = get_meters_data(meter_names, get_func, sample_size, delay, parallel, meter_ranges, strict_check)
            scan_logger.info(f"Collected data from meters: {meter_data}")

            for motor_name, motor_value in zip(motor_names, combination):
                if motor_name not in data["data"]:
                    data["data"][motor_name] = {}
                if motor_value not in data["data"][motor_name]:
                    data["data"][motor_name][motor_value] = {}
                data["data"][motor_name][motor_value].update(meter_data)

            if "steps" not in data:
                data["steps"] = []
            step_data = {
                "step_index": len(data["steps"]) + 1,
                "motor_values": dict(zip(motor_names, combination)),
                "meter_data": meter_data,
                "check_data": check_data,
                "meter_errors": meter_errors,
                "check_errors": check_errors,
                "timestamp": datetime.now().isoformat(),
            }
            data["steps"].append(step_data)

    except KeyboardInterrupt as e:
        scan_logger.error("Scan process stopped by user")
        raise e
        
    except Exception as e:
        scan_logger.exception(f"Error during scan process: {e}")
        raise e
        
    finally:
        
        for call in callback:
            if call is not None:
                scan_logger.info(f"Starting callback {call.__name__}")
                call(data)
                scan_logger.info(f"Callback {call.__name__} process completed")
                    
        if save_original_motor_values:
            scan_logger.info("Restoring motors to their original values")
            set_motors_values(original_motor_values.keys(), original_motor_values.values(), get_func, put_func, verify_motor, max_retries, delay, tolerance, parallel)
                
        data["scan_end_time"] = datetime.now().isoformat()
        data["total_steps"] = len(data.get("steps", []))
        
        if save:
            path = create_output_path(path, name)
            data["parameters"]["path"] = path
            save_data(path, data)
            scan_logger.info(f"Data saved to {path}")

        scan_logger.info("Scan process completed")
        
    return data


@response_measurements(targets={}, max_attempts=cfg.SCAN_RESPONSE_MEASUREMENTS_MAX_ATTEMPTS, num_singular_values=cfg.SCAN_RESPONSE_MEASUREMENTS_NUM_SINGULAR_VALUES, rcond=cfg.SCAN_RESPONSE_MEASUREMENTS_RCOND)
def reply(*args, **kwargs):
    return scan(*args, **kwargs)


@bayesian_optimization(targets={}, penalty=cfg.SCAN_BAYESIAN_OPTIMIZATION_PENALTY, n_calls=cfg.SCAN_BAYESIAN_OPTIMIZATION_N_CALLS, random_state=cfg.SCAN_RANDOM_STATE, minimize=cfg.SCAN_BAYESIAN_OPTIMIZATION_MINIMIZE)
def optimize(*args, **kwargs):
    return scan(*args, **kwargs)


@watch_measurements(observation_time=None)
def watch(*args, **kwargs):
    return scan(*args, **kwargs)
