import os
import itertools
from datetime import datetime

from ...core import config as cfg
from .utils import (
    create_output_directory,
    save_data,
    set_motor_value,
    collect_meters_data,
    scan_logger,
)
from .decorators import response_measurements


def scan(meters, motors, *, get_func, put_func, verify_motor=True, 
         max_retries=3, delay=0.1, tolerance=1e-6, 
         data={}, metadata={}, save=False, dirname=cfg.DATA_DIR,
         callbacks=[], save_original_motor_values=True,
):
    data = data or {}
    metadata = metadata or {}
    original_motor_values = {}

    if save_original_motor_values:
        for motor_name, _ in motors:
            try:
                original_motor_values[motor_name] = get_func(motor_name)
            except Exception as e:
                scan_logger.error(f"Error getting initial value for motor '{motor_name}': {e}")
                raise RuntimeError(f"Failed to retrieve initial motor value for '{motor_name}'")
            
    metadata["scan_start_time"] = datetime.now().isoformat()
    metadata["motors"] = [motor[0] for motor in motors]
    metadata["original_motor_values"] =  original_motor_values
    metadata["meters"] = meters
    metadata["parameters"] = {
        "save": save,
        "verify_motor": verify_motor,
        "max_retries": max_retries,
        "delay": delay,
        "tolerance": tolerance,
    }

    motor_names, motor_values = [motor[0] for motor in motors], [motor[1] for motor in motors]
    all_combinations = list(itertools.product(*motor_values))

    scan_logger.info("Starting scan process")
    scan_logger.info(f"Motors: {motor_names}")
    scan_logger.info(f"Motor value combinations: {all_combinations}")

    try:
        for step_index, combination in enumerate(all_combinations):
            scan_logger.info(f"Step {step_index + 1}/{len(all_combinations)}: Setting motor combination: {combination}")
            
            for motor_name, motor_value in zip(motor_names, combination):
                set_motor_value(
                    motor_name, motor_value,
                    get_func=get_func,
                    put_func=put_func,
                    verify_motor=verify_motor,
                    max_retries=max_retries,
                    delay=delay,
                    tolerance=tolerance
                )
                scan_logger.info(f"Motor '{motor_name}' set to value {motor_value}")

            meter_data = collect_meters_data(meters, get_func)
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

            for callback in callbacks:
                if callback is not None:
                    scan_logger.info(f"Starting callback {callback.__name__}")
                    callback({
                        "data": data,
                        "metadata": metadata
                    })
                    scan_logger.info(f"Callback {callback.__name__} process completed")

    except KeyboardInterrupt as e:
        scan_logger.error("Scan process stopped by user")
        
    except Exception as e:
        scan_logger.exception(f"Error during scan process: {e}")
    
    finally:
        if save_original_motor_values:
            scan_logger.info("Restoring motors to their original values")
            for motor_name, original_value in original_motor_values.items():
                try:
                    set_motor_value(
                        motor_name, original_value,
                        get_func=get_func,
                        put_func=put_func,
                        verify_motor=verify_motor,
                        max_retries=max_retries,
                        delay=delay,
                        tolerance=tolerance
                    )
                    scan_logger.info(f"Motor '{motor_name}' restored to its original value {original_value}")
                except Exception as e:
                    scan_logger.error(f"Failed to restore motor '{motor_name}' to its original value: {e}")
                
        metadata["scan_end_time"] = datetime.now().isoformat()
        metadata["total_steps"] = len(metadata["steps"])
        
        if save:
            dirname = create_output_directory(dirname)
            metadata["parameters"]["dirname"] = dirname
            save_data(os.path.join(dirname, "data.json"), data)
            save_data(os.path.join(dirname, "metadata.json"), metadata)
            scan_logger.info(f"Data saved to directory {dirname}")

        scan_logger.info("Scan process completed")
        
    return {"data": data, "metadata": metadata}


@response_measurements()
def scan_response_matrix(*args, **kwargs):
    return scan(*args, **kwargs)
    