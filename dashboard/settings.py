import os
from pathlib import Path

# Plot configurations
PLOT_CONFIGS = [
    {"name": "Meters", "items_key": "meters", "value_key": "meter_data",
     "limits_key": "meter_ranges", "errors_key": "meter_errors"},
    {"name": "Motors", "items_key": "motors", "value_key": "motor_values",
     "limits_key": "motor_ranges", "errors_key": "motor_errors"},
    {"name": "Checks", "items_key": "checks", "value_key": "check_data",
     "limits_key": "check_ranges", "errors_key": "check_errors"}
]

# Default values
DEFAULT_NUM_STEPS = 7
DEFAULT_FIG_WIDTH = 16
DEFAULT_FIG_HEIGHT_PER_PLOT = 4
CACHE_TTL = 3600  # 1 hour cache

# Default data settings
DEFAULT_DATA_DIR = "../data"
FILE_PATTERN = "prod/*.json"  # Pattern to match JSON files
SORT_FILES_BY = "mtime"  # Options: 'name', 'mtime' (modification time), 'ctime' (creation time)
SORT_ORDER = "ascending"  # Options: 'ascending', 'descending'
