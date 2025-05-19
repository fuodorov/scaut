import numpy as np
import random
import time
from functools import wraps
from skopt import gp_minimize
from skopt.space import Real, Integer
from skopt.utils import use_named_args
from scipy.optimize import least_squares

from .utils import scan_logger, truncated_pinv
from ..core import config as cfg
from .exceptions import ScanValueError

def response_measurements(targets={}, max_attempts=10, num_singular_values=10, rcond=1e-15, inverse_mode=True, response_matrices=[]):
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
   
            previous_scan = baseline_result

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
            
            if not response_matrices:
                for initial_on_values in on_values_all:
                    current_on_values = initial_on_values.copy()
                    motors_matrix, measurements_matrix = [], []
                    scan_logger.info("Performing individual scans for each motor to build the response matrix.")
                    
                    for i, mn in enumerate(motor_names):
                        attempt = 0
                        success = False
                        
                        while attempt < max_attempts and not success:
                            try:
                                scan_logger.debug(f"Performing scan for motor {mn}, on_value={current_on_values[i]}")
                                
                                cal_motors = []
                                for j, other_mn in enumerate(motor_names):
                                    value = current_on_values[j] if j == i else off_values[j]
                                    cal_motors.append((other_mn, [value]))
                                
                                cal_result = scan_func(
                                    meters=meters,
                                    motors=cal_motors,
                                    previous_scan=previous_scan,
                                    save=False,
                                    **{k: v for k, v in kwargs.items() if k not in ["motors", "meters", "save"]}
                                )
                                
                                previous_scan.update(cal_result)
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
                                
                                success = True
                            except ScanValueError as e:
                                attempt += 1
                                scan_logger.warning(
                                    f"Attempt {attempt} for motor {mn}: Device value outside the allowed range! "
                                    "Reducing on_value for this motor and retrying..."
                                )
                                current_on_values[i] /= 2
                                if attempt >= max_attempts:
                                    scan_logger.error(f"Max attempts reached for motor {mn}. Unable to complete scan with valid on_value.")
                                    raise e
                                        
                    motors_matrix = np.array(motors_matrix)             # shape: (n_motors, n_motors)
                    measurements_matrix = np.array(measurements_matrix)   # shape: (n_motors, n_meters)
                    
                    scan_logger.debug(f"motors_matrix:\n{motors_matrix}")
                    scan_logger.debug(f"measurements_matrix:\n{measurements_matrix}")
                    scan_logger.info("Computing the response matrix.")
                    
                    pseudo_inverse = np.linalg.pinv(motors_matrix, rcond=rcond)
                    response_matrix = pseudo_inverse @ measurements_matrix
                    scan_logger.debug(f"response_matrix:\n{response_matrix}")
                    
                    response_matrices.append(response_matrix)

            avg_response_matrix = sum(response_matrices) / len(response_matrices)
            target_values, baseline_array = [], []
            
            scan_logger.info("Computing motor deltas to reach targets.")
            for meter_name in meter_names:
                target_values.append(targets.get(meter_name, 0.0))
                baseline_array.append(baseline_meter_values[meter_name])

            target_array = np.array(target_values)   # (n_meters,)
            baseline_arr = np.array(baseline_array)  # (n_meters,)
            delta_meter = target_array - baseline_arr

            R = avg_response_matrix
            max_singular_values = min(num_singular_values, min(R.shape))
            best_error, best_delta_motors, best_final_positions, best_candidate = np.inf, None, None, None

            for candidate in range(0, max_singular_values + 1):
                R_pinv_candidate = truncated_pinv(R, candidate, rcond=rcond)  # (n_meters, n_motors)
                delta_motors_candidate = delta_meter @ R_pinv_candidate         # (n_motors,)
                
                final_positions_candidate = [off_values[i] + delta_motors_candidate[i] for i in range(n_motors)]
                final_motors_candidate = list(zip(motor_names, [[pos] for pos in final_positions_candidate]))
                
                try:
                    final_result_candidate = scan_func(
                        meters=meters,
                        motors=final_motors_candidate,
                        previous_scan=previous_scan,
                        save=False,
                        **{k: v for k, v in kwargs.items() if k not in ["motors", "meters", "save"]}
                    )
                except ScanValueError as e:
                    scan_logger.warning(
                        f"Candidate {candidate}: Device value outside the allowed range! "
                        "Next candidate and retrying..."
                    )
                    continue
                    
                previous_scan.update(final_result_candidate)
                candidate_array = [final_result_candidate["steps"][-1]["meter_data"][name] for name in meter_names]
                candidate_error = np.linalg.norm(np.array(target_values) - np.array(candidate_array))
                
                scan_logger.debug(f"Candidate using {candidate} singular values: error = {candidate_error:.5f}")
                
                if candidate_error < best_error:
                    best_error = candidate_error
                    best_delta_motors = delta_motors_candidate
                    best_final_positions = final_positions_candidate
                    best_candidate = candidate
            
            previous_scan["response_measurements"] = {
                "targets": targets,
                "response_matrix": avg_response_matrix.tolist(),
                "best_error": candidate_error.tolist(),
                "best_delta_motors": best_delta_motors.tolist(),
                "best_final_positions": final_positions_candidate,
                "best_num_singular_values": best_candidate,
            }
            scan_logger.info(f"Selected candidate with {best_candidate} singular values (error {best_error:.5f}).")     
            scan_logger.debug(f"Calculated motor deltas: {best_delta_motors}")
            scan_logger.debug(f"Final motor positions: {best_final_positions}")
            
            final_motors = list(zip(motor_names, [[pos] for pos in best_final_positions]))
            
            final_result = scan_func(
                meters=meters,
                motors=final_motors,
                previous_scan=previous_scan,
                **{k: v for k, v in kwargs.items() if k not in ["motors", "meters"]}
            )
            
            scan_logger.info("Finished response_measurements wrapper.")
            return final_result
        return wrapper
    return decorator


def bayesian_optimization(targets={}, n_calls=10, random_state=42, penalty=10, minimize=True):
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
            previous_scan = baseline_result
            
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
                        previous_scan=previous_scan,
                        save=False,
                        *args,
                        **{k: v for k, v in kwargs.items() if k not in ["motors", "meters", "save"]}
                    )
                except ScanValueError as e:
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
                
                return target_delta if minimize else target_delta
            
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
            previous_scan["bayesian_optimization"] = {
                "targets": targets,
                "best_settings": optimized_settings,
                "best_value": res.fun,
            }
            final_scan = scan_func(
                meters=meters,
                motors=[(name, [val]) for name, val in optimized_settings.items()],
                previous_scan=previous_scan,
                *args,
                **{k: v for k, v in kwargs.items() if k not in ["motors", "meters"]}
            )

            return final_scan
        return wrapper
    return decorator


def least_squares_fitting(targets={}, penalty=10, method="lm", max_nfev=3, max_steps=3):
    def decorator(scan_func):
        @wraps(scan_func)
        def wrapper(*args, **kwargs):
            scan_logger.info("Launching the least_squares fitting decorator.")

            motors, meters, checks = kwargs.get("motors", []), kwargs.get("meters", []), kwargs.get("checks", [])
            motor_names, meter_names, check_names = [m[0] for m in motors], [m[0] for m in meters], [m[0] for m in checks]
            check_bounds = {m[0]: (m[1][0], m[1][1]) for m in checks}
            motor_bounds = {m[0]: check_bounds.get(m[0], (-np.inf, np.inf)) for m in motors}
            motor_initial_guess = {m[0]: m[1][0] for m in motors}

            baseline_scan = targets or kwargs.get("previous_scan", {}).copy()
            if not baseline_scan:
                baseline_scan = {
                    "steps": max_steps * [
                        {
                            'step_index': 0,
                            'motor_values': {},
                            'meter_data': {},
                            'check_data': {},
                            'meter_errors': {},
                            'check_errors': {},
                            'timestamp': ''
                        }
                    ]
                }
            
            baseline_steps = baseline_scan.get("steps", []).copy()
                
            if len(baseline_steps) > max_steps:
                scan_logger.info(f"Using {max_steps} steps out of {len(baseline_steps)} for optimization")
                baseline_steps = random.sample(baseline_steps, max_steps)
                
            scan_logger.debug(f"List motors: {motor_names}")
            scan_logger.debug(f"List meters: {meter_names}")

            def objective(motor_settings):
                residuals = []
                for step in baseline_steps:
                    scan_logger.debug(f"Current motor settings: {motor_settings} for step {step['step_index']}")
                    calibrated_motors = [(name, [motor_settings[i]]) for i, name in enumerate(motor_names)]
                    calibrated_meters = []
                    
                    for meter_name, meter_limits in meters:
                        if meter_name in step["meter_data"]:
                            target = step["meter_data"].get(meter_name, 0.0)
                            new_limits = [target + meter_limits[0], target + meter_limits[1]]
                            calibrated_meters.append((meter_name, new_limits))
                        else:
                            calibrated_meters.append((meter_name, meter_limits))
                    
                    for motor_name in step["motor_values"]:
                        if motor_name not in motor_names:
                            calibrated_motors.append((motor_name, [step["motor_values"][motor_name]]))

                    try:
                        scan_result = scan_func(
                            meters=calibrated_meters,
                            motors=calibrated_motors,
                            previous_scan=baseline_scan,
                            save=False,
                            **{k: v for k, v in kwargs.items() if k not in ["motors", "meters", "save", "previous_scan"]}
                        )                        
                    except ScanValueError as e:
                        scan_logger.warning(f"Device value outside the allowed range! Returning large penalty.")
                        residuals.extend([penalty] * len(meter_names))
                        continue

                    measured_value = {}
                    for motor, values in scan_result["data"].items():
                        for val, meter_data in values.items():
                            for meter in meter_names:
                                measured_value[meter] = meter_data.get(meter, 0.0)

                    for meter in meter_names:
                        residuals.append(measured_value.get(meter, 0.0) - step["meter_data"].get(meter, 0.0))

                return residuals

            initial_guess = [motor_initial_guess[name] for name in motor_names]
            bounds = ([motor_bounds[name][0] for name in motor_names], [motor_bounds[name][1] for name in motor_names])
            rel_diff_steps = [motor[1][1] for motor in motors]
            
            result = least_squares(
                objective,
                x0=initial_guess,
                bounds=bounds if not method=="lm" else [-np.inf, np.inf],
                method=method,
                max_nfev=max_nfev,
                diff_step=rel_diff_steps if not method=="lm" else None,
            )

            scan_logger.info(f"Optimization result: {result}")

            optimized_settings = result.x
            final_motors = [(name, [optimized_settings[i]]) for i, name in enumerate(motor_names)]

            baseline_scan["least_squares_fitting"] = {
                "targets": baseline_steps,
                "best_settings": {name: optimized_settings[i] for i, name in enumerate(motor_names)},
                "best_value": result.cost,
                "method": method,
            }
            
            last_step = baseline_scan.get("steps", [])[-1]
            for motor_name in last_step["motor_values"]:
                if motor_name not in motor_names:
                    final_motors.append((motor_name, [last_step["motor_values"][motor_name]]))

            final_scan = scan_func(
                meters=meters,
                motors=final_motors,
                previous_scan=baseline_scan,
                **{k: v for k, v in kwargs.items() if k not in ["motors", "meters", "previous_scan"]}
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
            previous_scan = {}
            final_scan = {}
            strict_check = kwargs.get("strict_check", False)
            
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
                        previous_scan=previous_scan,
                        save=False,
                        **{k: v for k, v in kwargs.items() if k not in ["motors","meters","save"]}
                    )
                    previous_scan = final_scan
                except ScanValueError as e:
                    if strict_check:
                        scan_logger.error(e)
                        raise e
                        
                    scan_logger.warning(e)
                    continue
                except KeyboardInterrupt as e:
                    scan_logger.error("Scan process stopped by user")
                    break
                    
            final_scan = scan_func(
                meters=meters,
                motors=[(motor_names[i], [on_values[i]]) for i in range(n_motors)],
                previous_scan=previous_scan,
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
    

def add_plot_params(items_key, step_value_key, title="Data Plot", xlabel="Devices", ylabel="Device Values", 
                    limits_key=None, errors_key=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            defaults = {
                "items_key": items_key,
                "step_value_key": step_value_key,
                "title": title,
                "xlabel": xlabel,
                "ylabel": ylabel,
                "limits_key": limits_key,
                "errors_key": errors_key
            }
            for key, value in defaults.items():
                kwargs.setdefault(key, value)
            return func(*args, **kwargs)
        return wrapper
    return decorator
    