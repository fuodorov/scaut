import streamlit as st
import json
from pathlib import Path
from scaut.scan.utils import plot_generic_data, plot_response_matrix  # Добавляем импорт новой функции
import settings
from app_utils import scan_for_data_files, format_file_name, prepare_step_range


# Cache expensive computations
@st.cache_data(ttl=settings.CACHE_TTL, show_spinner="Loading data...")
def load_json_file(file_path):
    """Load and parse JSON file with caching"""
    with open(file_path, 'r') as f:
        return json.load(f)

@st.cache_data(ttl=settings.CACHE_TTL, show_spinner="Loading data...")
def load_uploaded_data(uploaded_file):
    """Load uploaded JSON data"""
    return json.load(uploaded_file)

@st.cache_data(ttl=settings.CACHE_TTL)
def get_available_plots(scan_data):
    """Get available plots with caching"""
    all_steps = scan_data.get("steps", [])
    return [
        cfg for cfg in settings.PLOT_CONFIGS
        if cfg["items_key"] in scan_data and any(cfg["value_key"] in step for step in all_steps)
    ]

def main():
    st.set_page_config(
        page_title="SCAUT Dashboard",
        page_icon="snowflake",
        layout="wide",
    )
    st.title("SCAUT Data Visualization Dashboard")

    # Scan for available data files
    default_files = scan_for_data_files()

    # Data source selection
    st.sidebar.header("Data Source")
    source_type = st.sidebar.radio("Select data source:",
                                   ["Default Dataset", "Upload Custom File"])

    scan_data = None

    if source_type == "Default Dataset":
        if not default_files:
            st.error("No default files found. Please upload a custom file.")
            return

        # Create user-friendly display names
        file_options = {format_file_name(name, size): path for name, [path, size] in default_files.items()}

        selected_display = st.sidebar.selectbox(
            "Select default dataset",
            list(file_options.keys())
        )

        file_path = file_options[selected_display]

        try:
            scan_data = load_json_file(file_path)
            st.sidebar.success(f"Loaded: {selected_display}")
            st.sidebar.caption(f"File: {file_path.name}")
        except Exception as e:
            st.error(f"Error loading default file: {e}")
            return

    else:  # Upload Custom File
        uploaded_file = st.sidebar.file_uploader(
            "Choose a JSON file",
            type="json"
        )

        if uploaded_file is None:
            # Show first available default if exists
            if default_files:
                first_file, size = next(iter(default_files.values()))
                display_name = format_file_name(first_file.name, size)
                st.info(f"Using default dataset: {display_name}")
                try:
                    scan_data = load_json_file(first_file)
                except Exception as e:
                    st.error(f"Error loading default file: {e}")
                    return
            else:
                st.warning("Please upload a JSON file or add default files")
                return
        else:
            try:
                scan_data = load_uploaded_data(uploaded_file)
                st.sidebar.success("File uploaded successfully!")
                st.sidebar.caption(f"File: {uploaded_file.name}")
            except Exception as e:
                st.error(f"Error loading file: {e}")
                return

    # Check if response matrix is available
    has_response_matrix = "response_measurements" in scan_data

    # Get available steps
    all_steps = scan_data.get("steps", [])
    has_steps = bool(all_steps)

    if not has_steps and not has_response_matrix:
        st.error("No steps found in the data and no response matrix available")
        return

    # Step controls (only show if steps are available)
    if has_steps:
        max_step_index = len(all_steps) - 1

        st.sidebar.header("Step Controls")
        num_steps = st.sidebar.slider(
            "Number of Steps to Show",
            1,
            10,
            settings.DEFAULT_NUM_STEPS
        )
        last_step = st.sidebar.slider(
            "Last Step Index",
            0,  # Start from 0 for index-based operations
            max_step_index,
            max_step_index
        )
        step_range = prepare_step_range(last_step, num_steps, max_step_index)
        scan_data["steps"] = scan_data["steps"][step_range[0]:step_range[1]:step_range[2]]

    # Sidebar controls
    st.sidebar.header("Plot Configuration")
    available_plots = get_available_plots(scan_data) if has_steps else []

    # Prepare tab names
    tab_names = [cfg["name"] for cfg in available_plots]
    if has_response_matrix:
        tab_names.append("Response Matrix")

    if not available_plots and not has_response_matrix:
        st.error("No valid data found in the file")
        return

    # Figure settings
    st.sidebar.header("Figure Settings")
    fig_width = st.sidebar.slider(
        "Figure Width",
        5,
        40,
        settings.DEFAULT_FIG_WIDTH
    )
    fig_height = st.sidebar.slider(
        "Figure Height per Plot",
        3,
        10,
        settings.DEFAULT_FIG_HEIGHT_PER_PLOT
    )

    # Create tabs
    tabs = st.tabs(tab_names)

    # Plot regular data tabs
    for i, cfg in enumerate(available_plots):
        with tabs[i]:
            fig = plot_generic_data(
                scan_data=scan_data,
                items_key=cfg["items_key"],
                step_value_key=cfg["value_key"],
                title=f"{cfg['name']} Data",
                xlabel="Devices",
                ylabel="Values",
                step_range=step_range,
                limits_key=cfg["limits_key"],
                errors_key=cfg["errors_key"],
                fig_size_x=fig_width,
                fig_size_y=fig_height
            )

            if fig:
                st.pyplot(fig)
                last_step_display = last_step + 1  # Convert to 1-based for display
                st.caption(f"Figure {i + 1}: {cfg['name']} data visualization showing {num_steps} steps. "
                           f"Black markers indicate the most recent step ({last_step_display}).")
            else:
                st.error(f"No {cfg['name']} data to display with current settings")

    # Plot response matrix if available
    if has_response_matrix:
        response_tab_index = len(available_plots)
        with tabs[response_tab_index]:
            st.subheader("Response Matrix")
            try:
                fig = plot_response_matrix(scan_data)
                if fig:
                    st.pyplot(fig)
                    st.caption("Response matrix visualization showing the relationship between inputs and outputs.")
                else:
                    st.warning("Response matrix data is present but could not be visualized.")
            except Exception as e:
                st.error(f"Error plotting response matrix: {e}")
                st.exception(e)

    # Show raw data if requested
    if st.sidebar.checkbox("Show Raw Data"):
        st.subheader("Raw Data")
        if has_steps:
            st.json(scan_data["steps"])
        if has_response_matrix:
            st.subheader("Response Matrix Data")
            st.json(scan_data["response_measurements"])


if __name__ == "__main__":
    main()