"""
Protocol Manager Interface

This view allows moderators to create, edit, view, and select 
pre-defined experiment protocols.

Author: Developer B
Version: 1.2 (Full CRUD Integration)
"""

import streamlit as st
import pandas as pd
import uuid
import json
from datetime import datetime

# Backend and component imports
from robotaste.data.protocol_repo import (
    list_protocols,
    get_protocol_by_id,
    create_protocol_in_db,
    update_protocol,
    delete_protocol,
    archive_protocol
)
from robotaste.views.sample_sequence_builder import render_timeline, sample_sequence_editor
from robotaste.config.protocols import validate_protocol
from robotaste.config.protocol_schema import VALIDATION_RULES
from robotaste.config.defaults import DEFAULT_INGREDIENT_CONFIG

# --- State Management Helpers ---

def go_to(view_name: str, **kwargs):
    """Helper function to switch views and pass arguments."""
    st.session_state.protocol_view = view_name
    # Clear old state to prevent conflicts
    for key in ['edit_protocol_id', 'preview_protocol_id']:
        if key not in kwargs and key in st.session_state:
            del st.session_state[key]
    # Set new state
    for key, value in kwargs.items():
        st.session_state[key] = value
    st.rerun()

# --- UI Views ---

def protocol_selection_screen():
    """
    Streamlined protocol selection with clean, scientific aesthetic.
    Matches mashaniv.wixsite.com/niv-taste-lab design.
    """
    st.markdown(
        """
        <h2 style='font-weight: 300; color: #2C3E50;
        letter-spacing: 0.05em; margin-bottom: 2rem;'>
        Protocol Selection
        </h2>
        """,
        unsafe_allow_html=True
    )

    protocols = list_protocols()

    if not protocols:
        st.info("📋 No protocols found in the library.")
        if st.button("Create First Protocol", type="primary"):
            go_to('editor')
        return

    # === SECTION 1: Protocol Selection (Primary Focus) ===
    st.markdown("### Choose Protocol")

    protocol_options = {p['protocol_id']: p for p in protocols}

    selected_id = st.selectbox(
        "Select a protocol for this experiment session:",
        options=list(protocol_options.keys()),
        format_func=lambda x: f"{protocol_options[x]['name']} (v{protocol_options[x].get('version', '1.0')})",
        key="protocol_selector",
        help="Choose from your saved experiment protocols",
        label_visibility="collapsed"
    )

    # === SECTION 2: Protocol Details (When Selected) ===
    if selected_id:
        selected_protocol = protocol_options[selected_id]
        st.session_state.selected_protocol_id = selected_id

        # Clean protocol card with key information
        st.markdown(
            f"""
            <div style='background: #F8F9FA; padding: 1.5rem;
            border-radius: 8px; border-left: 4px solid #521924;
            margin: 1.5rem 0;'>
                <h3 style='margin: 0 0 0.5rem 0; font-weight: 400;
                color: #2C3E50;'>{selected_protocol['name']}</h3>
                <p style='margin: 0; color: #7F8C8D;
                font-size: 0.95rem; line-height: 1.6;'>
                {selected_protocol.get('description', 'No description provided.')}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Key metrics in columns
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            cycles = selected_protocol.get('stopping_criteria', {}).get('max_cycles', 'N/A')
            st.metric("Cycles", cycles)

        with col2:
            num_ingredients = len(selected_protocol.get('ingredients', []))
            st.metric("Ingredients", num_ingredients)

        with col3:
            q_type = selected_protocol.get('questionnaire_type', 'N/A')
            display_type = q_type.replace('_', ' ').title() if q_type != 'N/A' else 'N/A'
            st.metric("Questionnaire", display_type)

        with col4:
            if st.button("👁️ Preview", key="preview_btn", use_container_width=True):
                go_to('preview', preview_protocol_id=selected_id)

    # === SECTION 3: Action Buttons ===
    st.markdown("---")

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        use_disabled = not selected_id
        if st.button(
            "Use This Protocol",
            type="primary",
            disabled=use_disabled,
            use_container_width=True
        ):
            if selected_id:
                st.success(f"✓ Protocol '{protocol_options[selected_id]['name']}' applied")

    with col2:
        if st.button("Protocol Library", use_container_width=True):
            go_to('list_viewer')

    with col3:
        if st.button("+ New", use_container_width=True):
            go_to('editor')

def protocol_list_viewer():
    """Clean protocol library with card-based layout."""
    st.markdown(
        """
        <h2 style='font-weight: 300; color: #2C3E50;
        letter-spacing: 0.05em;'>Protocol Library</h2>
        """,
        unsafe_allow_html=True
    )

    col1, col2 = st.columns([4, 1])
    with col1:
        st.caption("Manage your experiment protocols")
    with col2:
        if st.button("+ Create New", type="primary", use_container_width=True):
            go_to('editor')

    st.markdown("---")
    protocols = list_protocols(include_archived=True)

    if not protocols:
        st.info("No protocols in the library. Create one to get started!")
        return

    for p in protocols:
        with st.container(border=True):
            p_col1, p_col2 = st.columns([3, 1])
            with p_col1:
                name = p['name']
                if p['is_archived']:
                    name += " (Archived)"
                st.markdown(f"**{name}**")
                desc = p.get('description', 'No description')
                if len(desc) > 100:
                    desc = desc[:100] + "..."
                st.caption(desc)
                st.caption(f"Last updated: {p['updated_at'][:10] if p['updated_at'] else 'Unknown'}")

            with p_col2:
                b_col1, b_col2, b_col3, b_col4 = st.columns(4)
                if b_col1.button("✏️", key=f"edit_{p['protocol_id']}", help="Edit"):
                    go_to('editor', edit_protocol_id=p['protocol_id'])
                if b_col2.button("👁️", key=f"preview_{p['protocol_id']}", help="Preview"):
                    go_to('preview', preview_protocol_id=p['protocol_id'])
                archive_icon = "📦" if p['is_archived'] else "🗄️"
                archive_verb = "Unarchive" if p['is_archived'] else "Archive"
                if b_col3.button(archive_icon, key=f"archive_{p['protocol_id']}", help=archive_verb):
                    archive_protocol(p['protocol_id'], archived=not p['is_archived'])
                    st.rerun()
                if b_col4.button("🗑️", key=f"delete_{p['protocol_id']}", help="Delete"):
                    delete_protocol(p['protocol_id'])
                    st.rerun()

    st.markdown("---")
    if st.button("← Back to Session Setup"):
        go_to('selection')

def protocol_editor():
    """Provides a UI for creating or editing a protocol."""
    protocol_id = st.session_state.get('edit_protocol_id')
    is_editing = protocol_id is not None

    header = "Edit Protocol" if is_editing else "Create New Protocol"
    st.header(header)

    # Load existing protocol data if in edit mode
    if is_editing and 'protocol_form_data' not in st.session_state:
        protocol_data = get_protocol_by_id(protocol_id)
        if protocol_data:
            st.session_state.protocol_form_data = protocol_data
        else:
            st.error("Could not load protocol data.")
            return
    elif not is_editing and 'protocol_form_data' not in st.session_state:
        # Default structure for a new protocol, including all required fields
        st.session_state.protocol_form_data = {
            "name": "New Protocol",
            "description": "",
            "tags": [],
            "version": "1.0",
            "questionnaire_type": VALIDATION_RULES['valid_questionnaire_types'][0], # Get a valid default
            "ingredients": [],
            "sample_selection_schedule": []
        }

    form_data = st.session_state.protocol_form_data

    # --- UI for Protocol Editing ---
    all_protocols = list_protocols()
    all_tags = sorted(list(set(tag for p in all_protocols for tag in p.get('tags', []))))

    form_data['name'] = st.text_input("Protocol Name", value=form_data.get('name', ''))
    form_data['description'] = st.text_area("Description", value=form_data.get('description', ''))
    form_data['tags'] = st.multiselect("Tags", options=all_tags, default=form_data.get('tags', []))
    form_data['questionnaire_type'] = st.selectbox(
        "Questionnaire Type",
        options=VALIDATION_RULES['valid_questionnaire_types'],
        index=VALIDATION_RULES['valid_questionnaire_types'].index(form_data.get('questionnaire_type'))
        if form_data.get('questionnaire_type') in VALIDATION_RULES['valid_questionnaire_types']
        else 0,
        help="Identifier for the questionnaire to be used."
    )

    # --- Ingredient Editor ---
    st.subheader("Ingredients")
    st.caption("Add ingredients used in your experiment with their concentration ranges.")

    # Get current ingredients list (ensure it's a list, not DataFrame)
    current_ingredients = form_data.get('ingredients', [])
    if isinstance(current_ingredients, pd.DataFrame):
        current_ingredients = current_ingredients.to_dict('records')

    # Initialize ingredients in session state if not exists
    if 'protocol_ingredients' not in st.session_state:
        st.session_state.protocol_ingredients = current_ingredients.copy() if current_ingredients else []

    ingredients = st.session_state.protocol_ingredients

    # Display current ingredients
    if ingredients:
        st.write("**Current Ingredients:**")
        for idx, ing in enumerate(ingredients):
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

                with col1:
                    st.write(f"**{ing['name']}**")

                with col2:
                    st.caption(f"Min: {ing['min_concentration']:.4f} mM")

                with col3:
                    st.caption(f"Max: {ing['max_concentration']:.4f} mM")

                with col4:
                    if st.button("🗑️", key=f"delete_ing_{idx}", help="Delete ingredient"):
                        ingredients.pop(idx)
                        st.rerun()
    else:
        st.info("No ingredients added yet. Use the form below to add ingredients.")

    # Add new ingredient form
    with st.expander("➕ Add Ingredient", expanded=len(ingredients) == 0):
        with st.form("add_ingredient_form", clear_on_submit=True):
            # Get list of ingredient names from defaults
            available_ingredient_names = [ing["name"] for ing in DEFAULT_INGREDIENT_CONFIG]

            # Create dict for quick lookup of default values
            ingredient_defaults = {ing["name"]: ing for ing in DEFAULT_INGREDIENT_CONFIG}

            # Selectbox for ingredient name
            selected_name = st.selectbox(
                "Select Ingredient",
                options=available_ingredient_names,
                help="Choose from available ingredients"
            )

            # Get default values for selected ingredient
            default_ing = ingredient_defaults.get(selected_name, {})
            default_min = default_ing.get("min_concentration", 0.0)
            default_max = default_ing.get("max_concentration", 100.0)

            st.caption(f"Default range for {selected_name}: {default_min:.4f} - {default_max:.4f} mM")

            col1, col2 = st.columns(2)
            with col1:
                min_conc = st.number_input(
                    "Min Concentration (mM)",
                    min_value=0.0,
                    value=default_min,
                    step=0.01,
                    format="%.4f",
                    help="Minimum concentration for this ingredient"
                )
            with col2:
                max_conc = st.number_input(
                    "Max Concentration (mM)",
                    min_value=0.0,
                    value=default_max,
                    step=0.01,
                    format="%.4f",
                    help="Maximum concentration for this ingredient"
                )

            if st.form_submit_button("Add Ingredient", type="primary"):
                # Check if ingredient already added
                if any(ing["name"] == selected_name for ing in ingredients):
                    st.error(f"{selected_name} is already in the ingredient list")
                elif min_conc >= max_conc:
                    st.error("Min concentration must be less than max concentration")
                else:
                    ingredients.append({
                        "name": selected_name,
                        "min_concentration": min_conc,
                        "max_concentration": max_conc
                    })
                    st.success(f"Added ingredient: {selected_name}")
                    st.rerun()

    # Update form_data with current ingredients
    form_data['ingredients'] = ingredients

    # --- Schedule Editor ---
    st.subheader("Sample Selection Schedule")
    st.caption("Define how samples are selected for each cycle of your experiment.")

    # Initialize schedule if empty
    if 'sample_selection_schedule' not in form_data or not form_data['sample_selection_schedule']:
        form_data['sample_selection_schedule'] = [
            {
                "cycle_range": {"start": 1, "end": 5},
                "mode": "user_selected"
            }
        ]

    # Callback to update form_data when schedule changes
    def update_schedule(new_schedule):
        form_data['sample_selection_schedule'] = new_schedule
        st.session_state.protocol_form_data['sample_selection_schedule'] = new_schedule

    # When the editor view is loaded, we should ensure any old editor state is cleared
    # so it re-initializes with the current protocol's data. This prevents stale data
    # from a previous edit session appearing.
    current_protocol_id = st.session_state.get('edit_protocol_id')
    if 'editor_protocol_id' not in st.session_state or st.session_state.editor_protocol_id != current_protocol_id:
        if 'editor_schedule' in st.session_state:
            del st.session_state.editor_schedule
        st.session_state.editor_protocol_id = current_protocol_id

    # Render the integrated editor (includes timeline + edit UI)
    sample_sequence_editor(
        schedule=form_data.get('sample_selection_schedule', []),
        ingredients=form_data.get('ingredients', []),
        on_change=update_schedule
    )
    # Get the potentially updated schedule for the save button logic later.
    schedule = form_data.get('sample_selection_schedule', [])

    # --- Phase Sequence Editor (NEW for Week 5) ---
    st.subheader("Phase Sequence")
    st.caption("Define the order and type of phases in your experiment. Leave empty to use default phases.")

    phase_sequence = form_data.get('phase_sequence', {})
    phases = phase_sequence.get('phases', [])

    # Show current phases
    if phases:
        st.write("**Current Phase Sequence:**")
        for idx, phase in enumerate(phases):
            phase_id = phase.get('phase_id', 'unknown')
            phase_type = phase.get('phase_type', 'unknown')
            required = phase.get('required', True)
            auto_advance = phase.get('auto_advance', False)

            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"{idx+1}. **{phase_id}** ({phase_type})")
                if not required:
                    st.caption("↳ Optional phase")
                if auto_advance:
                    duration = phase.get('duration_ms', 0) / 1000
                    st.caption(f"↳ Auto-advances after {duration}s")
            with col2:
                if idx > 0 and st.button("⬆️", key=f"phase_up_{idx}", help="Move up"):
                    phases[idx], phases[idx-1] = phases[idx-1], phases[idx]
                    st.rerun()
            with col3:
                if st.button("🗑️", key=f"phase_delete_{idx}", help="Delete"):
                    phases.pop(idx)
                    st.rerun()
    else:
        st.info("No custom phases defined. The experiment will use the default phase sequence.")

    # Add new phase
    with st.expander("➕ Add Phase"):
        new_phase_type = st.selectbox(
            "Phase Type",
            ["builtin", "custom", "loop"],
            key="new_phase_type",
            help="Builtin: Standard phases (waiting, registration, etc.). Custom: Your own phase with custom content. Loop: Experiment cycle."
        )

        if new_phase_type == "builtin":
            new_phase_id = st.selectbox(
                "Phase ID",
                ["waiting", "registration", "instructions", "loading", "questionnaire", "selection", "completion"],
                key="new_phase_id"
            )
        elif new_phase_type == "loop":
            new_phase_id = st.text_input("Phase ID", value="experiment_loop", key="new_phase_id")
        else:
            new_phase_id = st.text_input("Custom Phase ID", placeholder="e.g., tutorial_video", key="new_phase_id")

        col1, col2 = st.columns(2)
        with col1:
            new_required = st.checkbox("Required", value=True, key="new_required")
        with col2:
            new_auto_advance = st.checkbox("Auto-advance", value=False, key="new_auto_advance")

        new_duration_ms = None
        if new_auto_advance:
            new_duration_ms = st.number_input(
                "Duration (seconds)",
                min_value=1,
                value=5,
                key="new_duration_sec"
            ) * 1000  # Convert to ms

        # Custom phase content editor (simplified)
        new_content = None
        if new_phase_type == "custom":
            st.write("**Custom Phase Content:**")
            content_type = st.selectbox(
                "Content Type",
                ["text", "media", "break", "survey"],
                key="new_content_type"
            )

            if content_type == "text":
                new_content = {
                    "type": "text",
                    "title": st.text_input("Title", key="content_title"),
                    "body": st.text_area("Body Text", key="content_body"),
                }
            elif content_type == "media":
                new_content = {
                    "type": "media",
                    "media_type": st.selectbox("Media Type", ["image", "video"], key="content_media_type"),
                    "media_url": st.text_input("Media URL", key="content_url"),
                    "caption": st.text_input("Caption (optional)", key="content_caption"),
                }
            elif content_type == "break":
                break_duration = st.number_input("Break Duration (seconds)", min_value=1, value=30, key="content_break_dur")
                new_content = {
                    "type": "break",
                    "duration_seconds": break_duration,
                    "message": st.text_input("Message", value=f"Please wait {break_duration} seconds...", key="content_message"),
                }
            elif content_type == "survey":
                st.info("Survey content editor coming soon. For now, you can add the phase and edit the JSON manually after saving.")
                new_content = {
                    "type": "survey",
                    "questions": []
                }

        if st.button("Add This Phase", type="primary"):
            new_phase = {
                "phase_id": new_phase_id,
                "phase_type": new_phase_type,
                "required": new_required,
            }

            if new_auto_advance and new_duration_ms:
                new_phase["auto_advance"] = True
                new_phase["duration_ms"] = int(new_duration_ms)

            if new_content:
                new_phase["content"] = new_content

            phases.append(new_phase)
            form_data['phase_sequence'] = {"phases": phases}
            st.success(f"Added phase: {new_phase_id}")
            st.rerun()

    # --- Save/Cancel Buttons ---
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Protocol", type="primary"):
            # Make a copy to modify for saving, preserving the original form state
            final_protocol = st.session_state.protocol_form_data.copy()

            # Re-assign schedule from local variable
            final_protocol['sample_selection_schedule'] = schedule

            # Validate before saving
            is_valid, errors = validate_protocol(final_protocol)
            if not is_valid:
                error_message = f"Protocol is invalid: {errors}"
                if isinstance(errors, list):
                    error_message = "Protocol is invalid:\n" + "\n".join([f"- {e}" for e in errors])
                st.error(error_message)
            else:
                if is_editing:
                    # For existing protocols, we only update, not create new IDs/dates
                    final_protocol['updated_at'] = datetime.utcnow().isoformat()
                    success = update_protocol(final_protocol)
                else:
                    # For new protocols, assign all required metadata
                    final_protocol['protocol_id'] = str(uuid.uuid4())
                    final_protocol['created_at'] = datetime.utcnow().isoformat()
                    final_protocol['updated_at'] = final_protocol['created_at']
                    final_protocol['is_archived'] = False # New protocols start as active
                    success = create_protocol_in_db(final_protocol)

                if success:
                    st.toast("Protocol saved successfully!")
                    # Clean up session state before navigating away
                    if 'protocol_form_data' in st.session_state:
                        del st.session_state['protocol_form_data']
                    if 'protocol_ingredients' in st.session_state:
                        del st.session_state['protocol_ingredients']
                    if 'editor_schedule' in st.session_state:
                        del st.session_state.editor_schedule
                    if 'editor_protocol_id' in st.session_state:
                        del st.session_state.editor_protocol_id
                    go_to('list_viewer')
                else:
                    st.error("Failed to save protocol to the database.")

    with col2:
        if st.button("Cancel"):
            if 'protocol_form_data' in st.session_state:
                del st.session_state['protocol_form_data']
            if 'protocol_ingredients' in st.session_state:
                del st.session_state['protocol_ingredients']
            if 'editor_schedule' in st.session_state:
                del st.session_state.editor_schedule
            if 'editor_protocol_id' in st.session_state:
                del st.session_state.editor_protocol_id
            go_to('list_viewer')

def protocol_preview():
    """Displays a read-only summary of a protocol."""
    st.header("Protocol Preview")
    protocol_id = st.session_state.get('preview_protocol_id')
    if not protocol_id:
        st.error("No protocol selected for preview.")
        if st.button("← Back to List"): go_to('list_viewer')
        return

    protocol = get_protocol_by_id(protocol_id)
    if not protocol:
        st.error(f"Could not find protocol with ID: {protocol_id}")
        if st.button("← Back to List"): go_to('list_viewer')
        return

    st.write(f"**Name:** {protocol.get('name', 'N/A')}")
    st.write(f"**Description:** {protocol.get('description', 'N/A')}")

    render_timeline(protocol.get("sample_selection_schedule", []))
    
    st.subheader("Full Protocol JSON")
    st.json(protocol)

    st.markdown("---")
    if st.button("← Back to List"):
        go_to('list_viewer')

def protocol_manager_view():
    """Main function to orchestrate the protocol manager views."""
    if 'protocol_view' not in st.session_state:
        st.session_state.protocol_view = 'selection'

    view = st.session_state.protocol_view
    
    with st.sidebar:
        st.header("Protocol Manager")
        if st.button("Selection Screen"): go_to('selection')
        if st.button("Protocol Library"): go_to('list_viewer')

    if view == 'selection':
        protocol_selection_screen()
    elif view == 'list_viewer':
        protocol_list_viewer()
    elif view == 'editor':
        protocol_editor()
    elif view == 'preview':
        protocol_preview()
    else:
        st.session_state.protocol_view = 'selection'
        st.rerun()

# To run this view standalone for testing:
if __name__ == "__main__":
    st.set_page_config(layout="wide")
    # This requires the database to be initialized.
    # You may need to run main_app.py once to create the db.
    try:
        protocol_manager_view()
    except Exception as e:
        st.error(f"An error occurred. Ensure the database is initialized. Error: {e}")

