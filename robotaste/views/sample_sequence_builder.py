"""
Sample Sequence Builder Component

This view provides a UI for visualizing and editing a protocol's 
sample selection schedule.

Author: Developer B
Version: 2.0 (Editor functionality added)
"""

import streamlit as st
import pandas as pd
import uuid

# Define colors for different modes for the timeline
MODE_COLORS = {
    "predetermined": "#3B82F6",  # Blue
    "user_selected": "#10B981",  # Green
    "bo_selected": "#8B5CF6",    # Purple
    "default": "#D1D5DB"        # Gray
}
MODE_NAMES = {
    "predetermined": "Predetermined",
    "user_selected": "User Selected",
    "bo_selected": "BO Selected"
}


def render_timeline(schedule: list):
    """
    Renders a visual timeline of the sample selection schedule.
    
    Args:
        schedule: The sample_selection_schedule list from a protocol.
    """
    st.markdown("#### Schedule Timeline")

    if not schedule:
        st.info("The schedule is empty. Add a block to get started.")
        return

    try:
        max_cycle = 0
        for block in schedule:
            if block["cycle_range"]["end"] > max_cycle:
                max_cycle = block["cycle_range"]["end"]
        
        if max_cycle == 0:
            st.info("The schedule has no cycles defined.")
            return

    except (KeyError, TypeError) as e:
        st.error(f"Invalid schedule structure. Could not determine cycle range: {e}")
        return

    cycle_modes = ["default"] * max_cycle
    for block in schedule:
        start = block["cycle_range"]["start"]
        end = block["cycle_range"]["end"]
        for i in range(start - 1, end):
            if i < len(cycle_modes):
                cycle_modes[i] = block["mode"]

    timeline_html = '<div style="display: flex; width: 100%; height: 40px; border-radius: 8px; overflow: hidden; border: 1px solid #E5E7EB;">'
    for i, mode in enumerate(cycle_modes):
        color = MODE_COLORS.get(mode, MODE_COLORS["default"])
        title = f"Cycle {i+1}: {MODE_NAMES.get(mode, 'N/A')}"
        timeline_html += f'<div style="flex-grow: 1; background-color: {color};" title="{title}"></div>'
    timeline_html += '</div>'

    labels_html = '<div style="display: flex; width: 100%; justify-content: space-between; margin-top: 5px; font-size: 0.8em;">'
    step = 1
    if max_cycle > 20:
        step = 5
    for i in range(1, max_cycle + 1):
        if (i - 1) % step == 0:
            labels_html += f'<span>{i}</span>'
        else:
            labels_html += '<span></span>'
    if max_cycle > 1 and (max_cycle -1) % step != 0:
        labels_html += f'<span>{max_cycle}</span>'

    labels_html += '</div>'

    st.markdown(timeline_html, unsafe_allow_html=True)
    st.markdown(labels_html, unsafe_allow_html=True)

    # Legend
    st.markdown("##### Legend")
    legend_html = '<div style="display: flex; gap: 20px; margin-top: 10px;">'
    for mode, name in MODE_NAMES.items():
        color = MODE_COLORS[mode]
        legend_html += f'<div><span style="display: inline-block; width: 15px; height: 15px; background-color: {color}; border-radius: 3px; margin-right: 5px; vertical-align: middle;"></span>{name}</div>'
    legend_html += '</div>'
    st.markdown(legend_html, unsafe_allow_html=True)


def sample_sequence_editor(schedule: list, on_change):
    """
    Main function to render the sample sequence editor UI.
    
    Args:
        schedule: The sample_selection_schedule list from a protocol.
        on_change: A callback function to be called when the schedule changes.
    """
    if 'editor_schedule' not in st.session_state:
        st.session_state.editor_schedule = [dict(s, id=str(uuid.uuid4())) for s in schedule]

    render_timeline(st.session_state.editor_schedule)
    st.markdown("---")
    st.markdown("#### Edit Schedule")

    for i, block in enumerate(st.session_state.editor_schedule):
        with st.container():
            st.markdown(f"**Block {i+1}**")
            col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
            
            with col1:
                start = st.number_input("Start Cycle", min_value=1, value=block["cycle_range"]["start"], key=f"start_{block['id']}")
            with col2:
                end = st.number_input("End Cycle", min_value=start, value=block["cycle_range"]["end"], key=f"end_{block['id']}")
            
            with col3:
                mode = st.selectbox("Mode", options=list(MODE_NAMES.keys()), format_func=lambda x: MODE_NAMES[x], index=list(MODE_NAMES.keys()).index(block["mode"]), key=f"mode_{block['id']}")

            with col4:
                st.write("") # for alignment
                if st.button("Delete", key=f"delete_{block['id']}"):
                    st.session_state.editor_schedule.pop(i)
                    on_change([s for s in st.session_state.editor_schedule])
                    st.rerun()

            st.session_state.editor_schedule[i]["cycle_range"]["start"] = start
            st.session_state.editor_schedule[i]["cycle_range"]["end"] = end
            st.session_state.editor_schedule[i]["mode"] = mode

            if mode == "predetermined":
                st.markdown("##### Predetermined Samples")
                if "predetermined_samples" not in st.session_state.editor_schedule[i]:
                    st.session_state.editor_schedule[i]["predetermined_samples"] = []

                # Use data editor for samples
                samples_df = pd.DataFrame(st.session_state.editor_schedule[i]["predetermined_samples"])
                edited_df = st.data_editor(samples_df, num_rows="dynamic", key=f"samples_{block['id']}")

                if isinstance(edited_df, pd.DataFrame):
                    st.session_state.editor_schedule[i]["predetermined_samples"] = edited_df.to_dict('records')

            elif mode == "bo_selected":
                st.markdown("##### Bayesian Optimization Config")
                if "bo_config" not in st.session_state.editor_schedule[i]:
                    st.session_state.editor_schedule[i]["bo_config"] = {}
                
                acq_func = st.text_input("Acquisition Function", value=st.session_state.editor_schedule[i]["bo_config"].get("acquisition_function", "ucb"), key=f"acq_func_{block['id']}")
                st.session_state.editor_schedule[i]["bo_config"]["acquisition_function"] = acq_func

            st.markdown("---")


    if st.button("Add Block"):
        new_start = 1
        if st.session_state.editor_schedule:
            new_start = st.session_state.editor_schedule[-1]["cycle_range"]["end"] + 1
        
        st.session_state.editor_schedule.append({
            "cycle_range": {"start": new_start, "end": new_start},
            "mode": "user_selected",
            "id": str(uuid.uuid4()) # unique id for block
        })
        on_change([s for s in st.session_state.editor_schedule])
        st.rerun()

    if st.button("Apply Changes"):
        # Basic validation for overlapping ranges
        sorted_schedule = sorted(st.session_state.editor_schedule, key=lambda x: x['cycle_range']['start'])
        is_overlapping = False
        for j in range(len(sorted_schedule) - 1):
            if sorted_schedule[j]['cycle_range']['end'] >= sorted_schedule[j+1]['cycle_range']['start']:
                is_overlapping = True
                st.error(f"Error: Cycle ranges are overlapping between block starting at {sorted_schedule[j]['cycle_range']['start']} and {sorted_schedule[j+1]['cycle_range']['start']}.")
                break
        
        if not is_overlapping:
            # remove id from schedule
            clean_schedule = [{k: v for k, v in s.items() if k != 'id'} for s in st.session_state.editor_schedule]
            on_change(clean_schedule)
            st.success("Schedule updated!")
            del st.session_state.editor_schedule


# To run this view standalone for testing:
if __name__ == "__main__":
    st.set_page_config(layout="wide")
    st.title("Sample Sequence Builder")
    st.info("This component allows editing the sample selection schedule of a protocol.")

    if 'test_schedule' not in st.session_state:
        st.session_state.test_schedule = [
            {
              "cycle_range": {"start": 1, "end": 2},
              "mode": "predetermined",
              "predetermined_samples": [
                {"cycle": 1, "concentrations": '{"Sugar": 10.0, "Salt": 2.0}'},
                {"cycle": 2, "concentrations": '{"Sugar": 20.0, "Salt": 4.0}'}
              ]
            },
            {
              "cycle_range": {"start": 3, "end": 5},
              "mode": "user_selected"
            },
            {
              "cycle_range": {"start": 6, "end": 10},
              "mode": "bo_selected",
              "bo_config": {"acquisition_function": "ucb"}
            }
        ]

    def on_schedule_change(new_schedule):
        st.session_state.test_schedule = new_schedule
        st.toast("Schedule updated in parent component's state.")

    sample_sequence_editor(st.session_state.test_schedule, on_schedule_change)

    st.markdown("### Current Schedule State")
    st.json(st.session_state.test_schedule)