import numpy as np
from functools import wraps

from .utils import scan_logger


def response_measurements(targets={}):
    def decorator(scan_func):
        @wraps(scan_func)
        def wrapper(*args, **kwargs):
            scan_logger.info("Calling response_measurements wrapper")
            
            motors, meters = kwargs.get("motors", []), kwargs.get("meters", [])
            motor_names = [m[0] for m in motors]
            n_motors, n_meters = len(motor_names), len(meters)
            
            scan_logger.debug(f"Motors list: {motor_names}")
            scan_logger.debug(f"Meters list: {meters}")
            
            off_values = [np.min(m[1]) for m in motors]
            on_values  = [np.max(m[1]) for m in motors]

            scan_logger.info("off_values and on_values for each motor defined.")
            scan_logger.debug(f"off_values={off_values}, on_values={on_values}")

            scan_logger.info("Performing baseline scan...")
            baseline_result = scan_func(
                meters=meters,
                motors=[(motor_names[i], [off_values[i]]) for i in range(n_motors)],
                **{k: v for k, v in kwargs.items() if k not in ["motors","meters"]}
            )
            response_metadata = baseline_result["metadata"]

            baseline_meter_values = {}
            if motor_names:
                scan_logger.debug("Extracting baseline meter values from scan result.")
                first_motor, first_off = motor_names[0], off_values[0]
                base_data = baseline_result["data"].get(first_motor, {})
                if first_off in base_data:
                    for meter_name in meters:
                        baseline_meter_values[meter_name] = base_data[first_off].get(meter_name, 0.0)
                else:
                    for meter_name in meters:
                        baseline_meter_values[meter_name] = 0.0
                        
            scan_logger.debug(f"baseline_meter_values={baseline_meter_values}")
            motors_matrix, measurements_matrix, measurements_matrix = [], [], []

            scan_logger.info("Performing individual scans for each motor to build the response matrix.")
            for i, mn in enumerate(motor_names):
                scan_logger.debug(f"Performing scan for motor {mn}, on_value={on_values[i]}")
                cal_motors = []
                for j, other_mn in enumerate(motor_names):
                    cal_motors.append((other_mn, [on_values[j] if j == i else off_values[j]]))

                cal_result = scan_func(
                    meters=meters,
                    motors=cal_motors,
                    metadata=response_metadata,
                    **{k: v for k, v in kwargs.items() if k not in ["motors","meters"]}
                )
                response_metadata.update(cal_result["metadata"])
                this_data = cal_result["data"].get(mn, {}).get(on_values[i], {})

                delta_motors_row = [0.0]*n_motors
                delta_motors_row[i] = (on_values[i] - off_values[i])

                delta_meters_row = []
                for meter_name in meters:
                    meas_val = this_data.get(meter_name, 0.0)
                    base_val = baseline_meter_values.get(meter_name, 0.0)
                    delta_meters_row.append(meas_val - base_val)

                motors_matrix.append(delta_motors_row)
                measurements_matrix.append(delta_meters_row)

            motors_matrix = np.array(motors_matrix)              # shape: (n_motors, n_motors)
            measurements_matrix = np.array(measurements_matrix)  # shape: (n_motors, n_meters)
            
            scan_logger.debug(f"motors_matrix:\n{motors_matrix}")
            scan_logger.debug(f"measurements_matrix:\n{measurements_matrix}")
            scan_logger.info("Computing the response matrix.")
            
            pseudo_inverse = np.linalg.pinv(motors_matrix)         # (n_motors, n_motors)
            response_matrix = pseudo_inverse @ measurements_matrix  # (n_motors, n_meters)
            scan_logger.debug(f"response_matrix:\n{response_matrix}")
            response_metadata["motors_matrix"] = motors_matrix.tolist()
            response_metadata["measurements_matrix"] = measurements_matrix.tolist()
            response_metadata["response_matrix"] = response_matrix.tolist()
            
            target_values = []
            baseline_array = []

            scan_logger.info("Computing motor deltas to reach targets.")
            for meter_name in meters:
                target_values.append(targets.get(meter_name, 0.0))
                baseline_array.append(baseline_meter_values[meter_name])

            target_array = np.array(target_values)   # (n_meters,)
            baseline_arr = np.array(baseline_array)  # (n_meters,)
            delta_meter = target_array - baseline_arr

            R = response_matrix
            R_pinv = np.linalg.pinv(R)      # (n_meters, n_motors)
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

