import streamlit as st
from pathlib import Path
import settings


def scan_for_data_files():
    """Scan for JSON files in the default data directory with sorting options"""
    base_dir = Path(__file__).parent
    data_dir = base_dir / settings.DEFAULT_DATA_DIR

    if not data_dir.exists():
        st.sidebar.warning(f"Default data directory not found: {data_dir}")
        return {}

    files = list(data_dir.glob(settings.FILE_PATTERN))

    if not files:
        st.sidebar.warning(f"No JSON files found in: {data_dir}")
        return {}

    # Sorting options
    if settings.SORT_FILES_BY == "name":
        key = lambda f: f.name
    elif settings.SORT_FILES_BY == "mtime":
        key = lambda f: f.stat().st_mtime
    elif settings.SORT_FILES_BY == "ctime":
        key = lambda f: f.stat().st_ctime
    else:
        key = lambda f: f.name

    reverse = settings.SORT_ORDER == "descending"
    sorted_files = sorted(files, key=key, reverse=reverse)

    return {f.name: f for f in sorted_files}


def format_file_name(name):
    """Format file name for better display"""
    # Remove extension
    name = Path(name).stem

    # Replace underscores and hyphens with spaces
    name = name.replace("_", " ").replace("-", " ")

    # Capitalize first letter of each word
    return " ".join(word.capitalize() for word in name.split())


def prepare_step_range(last_step, num_steps, max_step_index):
    """Prepare step range with validation"""
    start_step = max(0, last_step - num_steps)
    end_step = min(last_step, max_step_index)
    return (start_step, end_step, 1)
