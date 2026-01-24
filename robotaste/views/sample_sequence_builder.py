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
    "predetermined_absolute": "#3B82F6",  # Blue
    "predetermined_randomized": "#F59E0B",  # Amber/Orange
    "user_selected": "#10B981",  # Green
    "bo_selected": "#fda50f",    # Saffron
    "predetermined": "#3B82F6",  # Legacy - maps to predetermined_absolute
    "default": "#D1D5DB"        # Gray
}
MODE_NAMES = {
    "predetermined_absolute": "Predetermined (Absolute)",
    "predetermined_randomized": "Predetermined (Randomized)",
    "user_selected": "User Selected",
    "bo_selected": "BO Selected",
    "predetermined": "Predetermined (Absolute)"  # Legacy - maps to predetermined_absolute
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


def sample_sequence_editor(schedule: list, ingredients: list, on_change):


    """


    Main function to render the sample sequence editor UI.


    


    Args:


        schedule: The sample_selection_schedule list from a protocol.


        ingredients: The list of ingredients from the protocol.


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





            if mode in ["predetermined", "predetermined_absolute"]:


                st.markdown("##### Predetermined Samples")





                ingredient_names = [ing['name'] for ing in ingredients]


                if not ingredient_names:


                    st.warning("Please add ingredients to the protocol to define predetermined samples.")


                else:


                    # --- FLATTEN DATA for data_editor ---


                    flat_samples = []


                    for sample in block.get("predetermined_samples", []):


                        record = {'cycle': sample.get('cycle')}


                        concentrations = sample.get('concentrations', {})


                        for name in ingredient_names:


                            record[name] = concentrations.get(name, 0.0)


                        flat_samples.append(record)


                    


                    all_columns = ['cycle'] + ingredient_names


                    samples_df = pd.DataFrame(flat_samples, columns=all_columns)





                    column_config = {


                        name: st.column_config.NumberColumn(f"{name} (mM)", format="%.4f", default=0.0) 


                        for name in ingredient_names


                    }


                    column_config['cycle'] = st.column_config.NumberColumn("Cycle #", format="%d", required=True, min_value=1)





                    edited_df = st.data_editor(


                        samples_df,


                        num_rows="dynamic",


                        key=f"samples_{block['id']}",


                        column_config=column_config,


                        use_container_width=True


                    )





                    # --- RE-PIVOT DATA from data_editor ---


                    if isinstance(edited_df, pd.DataFrame):


                        new_samples = []


                        edited_df.dropna(subset=['cycle'], inplace=True)


                        edited_df.dropna(subset=ingredient_names, how='all', inplace=True)





                        for _, row in edited_df.iterrows():


                            cycle = int(row['cycle'])


                            concentrations = {name: float(row[name]) if pd.notna(row[name]) else 0.0 for name in ingredient_names}


                            


                            new_samples.append({


                                "cycle": cycle,


                                "concentrations": concentrations


                            })


                        


                        new_samples.sort(key=lambda x: x['cycle'])


                        st.session_state.editor_schedule[i]["predetermined_samples"] = new_samples

            elif mode == "predetermined_randomized":
                st.markdown("##### Sample Bank Configuration")

                ingredient_names = [ing['name'] for ing in ingredients]

                if not ingredient_names:
                    st.warning("Please add ingredients to the protocol to define sample bank.")
                else:
                    # Initialize sample_bank if not exists
                    if "sample_bank" not in st.session_state.editor_schedule[i]:
                        st.session_state.editor_schedule[i]["sample_bank"] = {
                            "samples": [],
                            "design_type": "randomized",
                            "constraints": {
                                "prevent_consecutive_repeats": True,
                                "ensure_all_used_before_repeat": True
                            }
                        }

                    # Design type selector
                    design_type = st.selectbox(
                        "Design Type",
                        options=["randomized", "latin_square"],
                        index=0 if st.session_state.editor_schedule[i]["sample_bank"].get("design_type") == "randomized" else 1,
                        key=f"design_type_{block['id']}",
                        help="Randomized: Random order each session. Latin Square: Counterbalanced order across sessions."
                    )
                    st.session_state.editor_schedule[i]["sample_bank"]["design_type"] = design_type

                    # Constraints
                    st.markdown("**Constraints:**")
                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        prevent_repeats = st.checkbox(
                            "Prevent consecutive repeats",
                            value=st.session_state.editor_schedule[i]["sample_bank"]["constraints"].get("prevent_consecutive_repeats", True),
                            key=f"prevent_repeats_{block['id']}"
                        )
                        st.session_state.editor_schedule[i]["sample_bank"]["constraints"]["prevent_consecutive_repeats"] = prevent_repeats
                    with col_c2:
                        ensure_all = st.checkbox(
                            "Use all before repeating",
                            value=st.session_state.editor_schedule[i]["sample_bank"]["constraints"].get("ensure_all_used_before_repeat", True),
                            key=f"ensure_all_{block['id']}"
                        )
                        st.session_state.editor_schedule[i]["sample_bank"]["constraints"]["ensure_all_used_before_repeat"] = ensure_all

                    # Sample bank data editor
                    st.markdown("**Sample Bank:**")

                    # Flatten samples for data_editor
                    flat_samples = []
                    for sample in st.session_state.editor_schedule[i]["sample_bank"].get("samples", []):
                        record = {
                            'ID': sample.get('id', ''),
                            'Label': sample.get('label', '')
                        }
                        concentrations = sample.get('concentrations', {})
                        for name in ingredient_names:
                            record[name] = concentrations.get(name, 0.0)
                        flat_samples.append(record)

                    all_columns = ['ID', 'Label'] + ingredient_names
                    samples_df = pd.DataFrame(flat_samples, columns=all_columns)

                    # Column configuration
                    column_config = {
                        'ID': st.column_config.TextColumn("Sample ID", required=True, help="Unique identifier (e.g., A, B, C)"),
                        'Label': st.column_config.TextColumn("Label", help="Optional description (e.g., Low, Medium, High)")
                    }
                    for name in ingredient_names:
                        column_config[name] = st.column_config.NumberColumn(f"{name} (mM)", format="%.4f", default=0.0)

                    edited_df = st.data_editor(
                        samples_df,
                        num_rows="dynamic",
                        key=f"bank_samples_{block['id']}",
                        column_config=column_config,
                        use_container_width=True
                    )

                    # Re-pivot data from data_editor
                    if isinstance(edited_df, pd.DataFrame):
                        new_samples = []
                        edited_df.dropna(subset=['ID'], inplace=True)
                        edited_df.dropna(subset=ingredient_names, how='all', inplace=True)

                        for _, row in edited_df.iterrows():
                            sample_id = str(row['ID']).strip()
                            if not sample_id:
                                continue
                            label = str(row['Label']).strip() if pd.notna(row['Label']) else ""
                            concentrations = {name: float(row[name]) if pd.notna(row[name]) else 0.0 for name in ingredient_names}

                            new_samples.append({
                                "id": sample_id,
                                "label": label,
                                "concentrations": concentrations
                            })

                        st.session_state.editor_schedule[i]["sample_bank"]["samples"] = new_samples

                        # Validation: check bank size vs cycle count
                        cycle_count = end - start + 1
                        bank_size = len(new_samples)
                        if bank_size > 0 and bank_size != cycle_count:
                            st.warning(f"⚠️ Bank size ({bank_size}) doesn't match cycle count ({cycle_count}). Consider adjusting to match.")

                        # Preview for Latin Square
                        if design_type == "latin_square" and bank_size > 0:
                            st.markdown("**Latin Square Preview (first 4 sessions):**")
                            sample_ids = [s['id'] for s in new_samples]
                            preview_text = ""
                            for session_num in range(1, min(5, bank_size + 1)):
                                rotation = (session_num - 1) % bank_size
                                sequence = sample_ids[rotation:] + sample_ids[:rotation]
                                preview_text += f"Session {session_num}: {' → '.join(sequence)}\n"
                            st.code(preview_text)

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


            if 'editor_schedule' in st.session_state:


                del st.session_state.editor_schedule








# To run this view standalone for testing:


if __name__ == "__main__":


    st.set_page_config(layout="wide")


    st.title("Sample Sequence Builder")


    st.info("This component allows editing the sample selection schedule of a protocol.")





    # Add dummy ingredients for testing


    if 'test_ingredients' not in st.session_state:


        st.session_state.test_ingredients = [


            {'name': 'Sugar'},


            {'name': 'Salt'}


        ]





    if 'test_schedule' not in st.session_state:


        st.session_state.test_schedule = [


            {


              "cycle_range": {"start": 1, "end": 2},


              "mode": "predetermined",


              "predetermined_samples": [


                {"cycle": 1, "concentrations": {"Sugar": 10.0, "Salt": 2.0}},


                {"cycle": 2, "concentrations": {"Sugar": 20.0, "Salt": 4.0}}


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





    sample_sequence_editor(


        st.session_state.test_schedule,


        st.session_state.test_ingredients,


        on_schedule_change


    )





    st.markdown("### Current Schedule State")


    st.json(st.session_state.test_schedule)

