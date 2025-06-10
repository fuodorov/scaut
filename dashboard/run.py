import streamlit as st
import json

from scaut.scan.utils import plot_generic_data


def main():
    st.set_page_config(
        page_title="SCAUT",
        page_icon="snowflake",
        layout="wide",
    )
    st.title("Dashboard")

    # File upload
    st.sidebar.header("Data Source")
    uploaded_file = st.sidebar.file_uploader("Choose a JSON file", type="json")

    if uploaded_file is None:
        st.warning("Please upload a JSON file")
        return

    try:
        scan_data = json.load(uploaded_file)
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return

    # Get available steps
    all_steps = scan_data.get("steps", [])
    if not all_steps:
        st.error("No steps found in the data")
        return

    max_step_index = len(all_steps) - 1

    # Sidebar controls
    st.sidebar.header("Plot Configuration")

    # Fixed key pairs for all three plots
    plot_configs = [
        {"name": "Meters", "items_key": "meters", "value_key": "meter_data",
         "limits_key": "meter_ranges", "errors_key": "meter_errors"},
        {"name": "Motors", "items_key": "motors", "value_key": "motor_values",
         "limits_key": "motor_ranges", "errors_key": "motor_errors"},
        {"name": "Checks", "items_key": "checks", "value_key": "check_data",
         "limits_key": "check_ranges", "errors_key": "check_errors"}
    ]

    # Filter for available data
    available_plots = [cfg for cfg in plot_configs
                       if cfg["items_key"] in scan_data and any(cfg["value_key"] in step for step in all_steps)]

    if not available_plots:
        st.error("No valid data found in the file")
        return

    # Step controls
    st.sidebar.header("Step Controls")
    num_steps = st.sidebar.slider("Number of Steps to Show", 1, 10, 7)
    last_step = st.sidebar.slider("Last Step Index", 1, max_step_index, max_step_index)
    step_range = (max(0, last_step - num_steps + 1), last_step, 1)

    # Figure settings
    st.sidebar.header("Figure Settings")
    fig_width = st.sidebar.slider("Figure Width", 5, 40, 16)
    fig_height = st.sidebar.slider("Figure Height per Plot", 3, 10, 4)

    # Create tabs for each plot
    tabs = st.tabs([cfg["name"] for cfg in available_plots])

    for i, tab in enumerate(tabs):
        with tab:
            cfg = available_plots[i]
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
                st.caption(f"Figure {i + 1}: {cfg['name']} data visualization showing {num_steps} steps. "
                           f"Black markers indicate the most recent step ({last_step}).")
            else:
                st.error(f"No {cfg['name']} data to display with current settings")

    # Show raw data if requested
    if st.sidebar.checkbox("Show Raw Data"):
        st.subheader("Raw Data")
        st.json(scan_data["steps"][last_step-1])


if __name__ == "__main__":
    main()
