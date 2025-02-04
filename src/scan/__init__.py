import os
import itertools
from datetime import datetime
from tqdm import tnrange, tqdm_notebook
from tqdm.contrib import tzip

from ..core import config as cfg
from .utils import (
    create_output_directory,
    save_data,
    set_motors_values,
    get_meters_data,
    scan_logger,
)
from .decorators import response_measurements, bayesian_optimization


def scan(meters, motors, *, get_func, put_func, verify_motor=True, 
         max_retries=cfg.SCAN_MAX_TRIES, delay=cfg.SCAN_DELAY, tolerance=cfg.SCAN_TOLERANCE, 
         data=None, metadata=None, save=False, dirname=cfg.DATA_DIR,
         callback=None, save_original_motor_values=True, sample_size=cfg.SCAN_SAMPLE_SIZE,
         parallel=cfg.SCAN_PARALLEL, repeat=cfg.SCAN_REPEAT,
):
    data = data or {}
    metadata = metadata or {}
    original_motor_values = {}
    motor_names, motor_ranges = [motor[0] for motor in motors], [motor[1] for motor in motors]
    meter_names, meter_ranges = [meter[0] for meter in meters], [meter[1] for meter in meters]
    all_combinations = list(itertools.product(*motor_ranges))
    
    if save_original_motor_values:
        try:
            original_motor_values = get_meters_data(motor_names, get_func, sample_size, delay, parallel)
        except Exception as e:
            scan_logger.error(f"Error getting initial value for motor '{motor_name}': {e}")
            raise RuntimeError(f"Failed to retrieve initial motor value for '{motor_name}'")
            
    metadata["scan_start_time"] = datetime.now().isoformat()
    metadata["motors"] = motor_names
    metadata["original_motor_values"] =  original_motor_values
    metadata["meters"] = meter_names
    metadata["parameters"] = {
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
            meter_data = get_meters_data(meter_names, get_func, sample_size, delay, parallel)
            for meter_name, meter_range in zip(meter_names, meter_ranges):
                measured_value = meter_data.get(meter_name)
                lower_limit, upper_limit = min(meter_range), max(meter_range)
                if measured_value < lower_limit or measured_value > upper_limit:
                    raise ValueError(
                        f"Device value '{meter_name}' = {measured_value} "
                        f"outside the allowed range ({lower_limit}, {upper_limit})"
                    )
                    
            scan_logger.info(f"Collected data from meters: {meter_data}")

            for motor_name, motor_value in zip(motor_names, combination):
                if motor_name not in data:
                    data[motor_name] = {}
                if motor_value not in data[motor_name]:
                    data[motor_name][motor_value] = {}
                data[motor_name][motor_value].update(meter_data)

            if "steps" not in metadata:
                metadata["steps"] = []
            step_metadata = {
                "step_index": len(metadata["steps"]) + 1,
                "motor_values": dict(zip(motor_names, combination)),
                "meter_data": meter_data,
                "timestamp": datetime.now().isoformat(),
            }
            metadata["steps"].append(step_metadata)

            for call in callback:
                if call is not None:
                    scan_logger.info(f"Starting callback {call.__name__}")
                    call({"data": data, "metadata": metadata})
                    scan_logger.info(f"Callback {call.__name__} process completed")

    except KeyboardInterrupt as e:
        scan_logger.error("Scan process stopped by user")
        raise e
        
    except Exception as e:
        scan_logger.exception(f"Error during scan process: {e}")
        raise e
        
    finally:
        if save_original_motor_values:
            scan_logger.info("Restoring motors to their original values")
            set_motors_values(original_motor_values.keys(), original_motor_values.values(), get_func, put_func, verify_motor, max_retries, delay, tolerance, parallel)
                
        metadata["scan_end_time"] = datetime.now().isoformat()
        metadata["total_steps"] = len(metadata.get("steps", []))
        
        if save:
            dirname = create_output_directory(dirname)
            metadata["parameters"]["dirname"] = dirname
            save_data(os.path.join(dirname, "data.json"), data)
            save_data(os.path.join(dirname, "metadata.json"), metadata)
            scan_logger.info(f"Data saved to directory {dirname}")

        scan_logger.info("Scan process completed")
        
    return {"data": data, "metadata": metadata}


@response_measurements(targets={})
def scan_response_measurements(*args, **kwargs):
    return scan(*args, **kwargs)


@bayesian_optimization(targets={}, n_calls=cfg.SCAN_BAYESIAN_OPTIMIZATION_N_CALLS, random_state=cfg.SCAN_RANDOM_STATE)
def scan_bayesian_optimization(*args, **kwargs):
    return scan(*args, **kwargs)

    
