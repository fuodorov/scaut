import numpy as np
import random
import time
from functools import wraps
from skopt import gp_minimize
from skopt.space import Real, Integer
from skopt.utils import use_named_args

from .utils import scan_logger, truncated_pinv
from ..core import config as cfg
from .exceptions import ScanMeterValueError

def response_measurements(targets={}, max_attempts=10, num_singular_values=5, rcond=1e-15, inverse_mode=True):
    def decorator(scan_func):
        @wraps(scan_func)
        def wrapper(*args, **kwargs):
            scan_logger.info("Calling response_measurements wrapper")
            
            motors, meters = kwargs.get("motors", []), kwargs.get("meters", [])
            motor_names, meter_names = [m[0] for m in motors], [m[0] for m in meters]
            n_motors, n_meters = len(motor_names), len(meter_names)
            
            scan_logger.debug(f"Motors list: {motor_names}")
            scan_logger.debug(f"Meters list: {meter_names}")
            
            off_values = [m[1][0] for m in motors]
            on_values  = [m[1][1] for m in motors]

            scan_logger.info("off_values and on_values for each motor defined.")
            scan_logger.debug(f"off_values={off_values}, on_values={on_values}")

            scan_logger.info("Performing baseline scan...")
            
            baseline_result = scan_func(
                meters=meters,
                motors=[(motor_names[i], [off_values[i]]) for i in range(n_motors)],
                save=False,
                **{k: v for k, v in kwargs.items() if k not in ["motors","meters","save"]}
            )
   
            response_metadata = baseline_result["metadata"]

            baseline_meter_values = {}
            if motor_names:
                scan_logger.debug("Extracting baseline meter values from scan result.")
                first_motor, first_off = motor_names[0], off_values[0]
                base_data = baseline_result["data"].get(first_motor, {})
                if first_off in base_data:
                    for meter_name in meter_names:
                        baseline_meter_values[meter_name] = base_data[first_off].get(meter_name, 0.0)
                else:
                    for meter_name in meter_names:
                        baseline_meter_values[meter_name] = 0.0
                        
            scan_logger.debug(f"baseline_meter_values={baseline_meter_values}")
            
            on_values_all = (
                [np.array(off_values) + np.array(on_values), np.array(off_values) - np.array(on_values)]
                if inverse_mode
                else [np.array(off_values) + np.array(on_values)]
            )
            response_matrices = []
            
            for initial_on_values in on_values_all:
                current_on_values = initial_on_values.copy()
                attempt = 0
            
                while attempt < max_attempts:
                    motors_matrix, measurements_matrix = [], []
                    try:
                        scan_logger.info("Performing individual scans for each motor to build the response matrix.")
            
                        for i, mn in enumerate(motor_names):
                            scan_logger.debug(f"Performing scan for motor {mn}, on_value={current_on_values[i]}")
                            cal_motors = []
                            for j, other_mn in enumerate(motor_names):
                                value = current_on_values[j] if j == i else off_values[j]
                                cal_motors.append((other_mn, [value]))
                            
                            cal_result = scan_func(
                                meters=meters,
                                motors=cal_motors,
                                metadata=response_metadata,
                                save=False,
                                **{k: v for k, v in kwargs.items() if k not in ["motors", "meters", "save"]}
                            )
            
                            response_metadata.update(cal_result["metadata"])
                            this_data = cal_result["data"].get(mn, {}).get(current_on_values[i], {})
            
                            delta_motors_row = [0.0] * n_motors
                            delta_motors_row[i] = (current_on_values[i] - off_values[i])
                            delta_meters_row = []
                            for meter_name in meter_names:
                                meas_val = this_data.get(meter_name, 0.0)
                                base_val = baseline_meter_values.get(meter_name, 0.0)
                                delta_meters_row.append(meas_val - base_val)
            
                            motors_matrix.append(delta_motors_row)
                            measurements_matrix.append(delta_meters_row)
            
                        motors_matrix = np.array(motors_matrix)             # shape: (n_motors, n_motors)
                        measurements_matrix = np.array(measurements_matrix)   # shape: (n_motors, n_meters)
            
                        scan_logger.debug(f"motors_matrix:\n{motors_matrix}")
                        scan_logger.debug(f"measurements_matrix:\n{measurements_matrix}")
                        scan_logger.info("Computing the response matrix.")
            
                        pseudo_inverse = np.linalg.pinv(motors_matrix, rcond=rcond)
                        response_matrix = pseudo_inverse @ measurements_matrix
                        scan_logger.debug(f"response_matrix:\n{response_matrix}")
            
                        response_matrices.append(response_matrix)
                        break
            
                    except ScanMeterValueError as e:
                        attempt += 1
                        scan_logger.warning(
                            f"Attempt {attempt}: Device value outside the allowed range! "
                            "Reducing on_values in half and retrying..."
                        )
                        current_on_values = initial_on_values / (2 ** attempt)
                        if attempt >= max_attempts:
                            scan_logger.error("Max attempts reached, unable to complete scan with valid on_values.")
                            if response_matrices:
                                break
                            else:
                                raise e


            avg_response_matrix = sum(response_matrices) / len(response_matrices)
            
            response_metadata["response_matrix"] = avg_response_matrix.tolist()

            target_values = []
            baseline_array = []

            scan_logger.info("Computing motor deltas to reach targets.")
            for meter_name in meter_names:
                target_values.append(targets.get(meter_name, 0.0))
                baseline_array.append(baseline_meter_values[meter_name])

            target_array = np.array(target_values)   # (n_meters,)
            baseline_arr = np.array(baseline_array)  # (n_meters,)
            delta_meter = target_array - baseline_arr

            R = avg_response_matrix
            R_pinv = truncated_pinv(R, num_singular_values, rcond=rcond)      # (n_meters, n_motors)
            delta_motors = delta_meter @ R_pinv  # (n_motors,)

            final_positions = [off_values[i] + delta_motors[i] for i in range(n_motors)]
            scan_logger.debug(f"Calculated motor deltas: {delta_motors}")
            scan_logger.debug(f"Final motor positions: {final_positions}")
            
            final_motors = list(zip(motor_names, [[pos] for pos in final_positions]))
            
            final_result = scan_func(
                meters=meters,
                motors=final_motors,
                metadata=response_metadata,
                **{k: v for k, v in kwargs.items() if k not in ["motors","meters"]}
            )

            scan_logger.info("Finished response_measurements wrapper.")
            return final_result
        return wrapper
    return decorator


def bayesian_optimization(targets={}, n_calls=10, random_state=42, penalty=10):
    def decorator(scan_func):
        @wraps(scan_func)
        def wrapper(*args, **kwargs):
            scan_logger.info("Launching the Bayesian optimization decorator.")
            
            motors, meters = kwargs.get("motors", []), kwargs.get("meters", [])
            motor_names, meter_names = [m[0] for m in motors], [m[0] for m in meters]
            motor_bounds = {}
            
            scan_logger.debug(f"List motors: {motor_names}")
            scan_logger.debug(f"List meters: {meter_names}")
            
            for motor in motors:
                name, values = motor
                motor_bounds[name] = (values[0], values[1])
            
            space = []
            motor_order = []
            off_values = []
            for name in motor_names:
                lb, ub = motor_bounds[name]
                space.append(Real(lb - ub, lb + ub, name=name))
                off_values.append(lb)
                motor_order.append(name)
            
            scan_logger.info("Performing a basic scan with the initial values of the motors.")
            baseline_result = scan_func(
                meters=meters,
                motors=[(name, [val]) for name, val in zip(motor_names, off_values)],
                *args,
                **{k: v for k, v in kwargs.items() if k not in ["motors", "meters"]}
            )
            response_metadata = baseline_result.get("metadata", {})
            
            baseline_meter_values = {}
            if motor_names:
                scan_logger.debug("Extracting basic metric values from the result of a basic scan.")
                first_motor = motor_names[0]
                first_off = off_values[0]
                base_data = baseline_result["data"].get(first_motor, {})
                if first_off in base_data:
                    for meter_name in meter_names:
                        baseline_meter_values[meter_name] = base_data[first_off].get(meter_name, 0.0)
                else:
                    for meter_name in meter_names:
                        baseline_meter_values[meter_name] = 0.0
                            
            scan_logger.debug(f"Base list meter values: {baseline_meter_values}")
            
            @use_named_args(space)
            def objective(**motor_settings):
                scan_logger.debug(f"Current motor settings: {motor_settings}")
                calibrated_motors = [(name, [val]) for name, val in motor_settings.items()]
                
                try:
                    scan_result = scan_func(
                        meters=meters,
                        motors=calibrated_motors,
                        metadata=response_metadata,
                        save=False,
                        *args,
                        **{k: v for k, v in kwargs.items() if k not in ["motors", "meters", "save"]}
                    )
                except ScanMeterValueError as e:
                    scan_logger.warning(f"Device value outside the allowed range! Add penalty {penalty}")
                    return penalty
                
                measured_value = {}
                for motor, values in scan_result["data"].items():
                    for val, meter_data in values.items():
                        for meter in meter_names:
                            measured_value[meter] = meter_data.get(meter, 0.0)
                
                delta = {}
                for meter in meter_names:
                    delta[meter] = np.abs(measured_value.get(meter, 0.0))
                
                scan_logger.debug(f"Measuring the delta of metrics: {delta}")
                
                target_delta = sum(np.abs(measured_value.get(meter, 0.0) - targets.get(meter, 0.0)) for meter in meter_names)
                scan_logger.debug(f"Target delta ({targets}): {target_delta}")
                
                return target_delta
            
            scan_logger.info("The beginning of Bayesian optimization.")
            res = gp_minimize(
                func=objective,
                dimensions=space,
                n_calls=n_calls,
                random_state=random_state,
                x0=off_values,
            )
            
            scan_logger.info("Bayesian optimization is complete.")
            scan_logger.info(f"Best result: {res.x}")
            scan_logger.info(f"Best function result: {res.fun}")
            
            optimized_settings = {dim.name: val for dim, val in zip(space, res.x)}
            response_metadata["bayesian_optimization"] = {
                "best_settings": optimized_settings,
                "best_value": res.fun,
            }
            final_scan = scan_func(
                meters=meters,
                motors=[(name, [val]) for name, val in optimized_settings.items()],
                metadata=response_metadata,
                *args,
                **{k: v for k, v in kwargs.items() if k not in ["motors", "meters"]}
            )

            return final_scan
        return wrapper
    return decorator
    

def watch_measurements(observation_time=None):
    def decorator(scan_func):
        @wraps(scan_func)
        def wrapper(*args, **kwargs):
            scan_logger.info("Calling watch_measurements wrapper")
            start = time.time()
            end = start + observation_time if observation_time is not None else None
            response_metadata = {}
            final_scan = {}
            
            while True:
                if end is not None and time.time() >= end:
                    break
                    
                try:
                    motors, meters = kwargs.get("motors", []), kwargs.get("meters", [])
                    get_func, put_func = kwargs.get("get_func", []), kwargs.get("put_func", [])
                    motor_names, meter_names = [m[0] for m in motors], [m[0] for m in meters]
                    n_motors, n_meters = len(motor_names), len(meter_names)
                    
                    scan_logger.debug(f"Motors list: {motor_names}")
                    scan_logger.debug(f"Meters list: {meter_names}")
                    
                    on_values  = [get_func(name) for name in motor_names]
        
                    scan_logger.debug(f"on_values={on_values}")
        
                    scan_logger.info("Performing scan...")
                    final_scan = scan_func(
                        meters=meters,
                        motors=[(motor_names[i], [on_values[i]]) for i in range(n_motors)],
                        metadata=response_metadata,
                        save=False,
                        **{k: v for k, v in kwargs.items() if k not in ["motors","meters","save"]}
                    )
                    response_metadata = final_scan.get("metadata", {})
                    
                except KeyboardInterrupt as e:
                    scan_logger.error("Scan process stopped by user")
                    break
                finally:
                    final_scan = scan_func(
                        meters=meters,
                        motors=[(motor_names[i], [on_values[i]]) for i in range(n_motors)],
                        metadata=response_metadata,
                        **{k: v for k, v in kwargs.items() if k not in ["motors","meters"]}
                    )
            return final_scan
        return wrapper
    return decorator


def add_noise(noise_level):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            noisy_args = []
            for arg in args:
                noisy_args.append(random.gauss(arg, abs(arg) * noise_level) if isinstance(arg, (int, float)) else arg)
            
            noisy_kwargs = {}
            for key, value in kwargs.items():
                noisy_kwargs[key] = random.gauss(value, value * noise_level) if isinstance(value, (int, float)) else value
            
            result = func(*noisy_args, **noisy_kwargs)
            return random.gauss(result, abs(result) * noise_level) if isinstance(result, (int, float)) else result
        return wrapper
    return decorator
    