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
from robotaste.views.sample_sequence_builder import render_timeline
from robotaste.config.protocols import validate_protocol
from robotaste.config.protocol_schema import VALIDATION_RULES

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
    """Displays a screen for selecting an existing protocol."""
    st.header("Protocol Selection")
    st.write("Choose a protocol to apply to the current session, or manage the protocol library.")

    protocols = list_protocols()
    
    if not protocols:
        st.warning("No protocols found. Go to 'Manage Protocols' to create one.")
        if st.button("Manage Protocols"):
            go_to('list_viewer')
        return

    protocol_names = {p['protocol_id']: p['name'] for p in protocols}
    
    selected_id = st.selectbox(
        "Select a Protocol",
        options=list(protocol_names.keys()),
        format_func=lambda x: protocol_names[x],
        key="protocol_selector"
    )

    if selected_id:
        st.session_state.selected_protocol_id = selected_id
        st.info(f"You have selected **{protocol_names[selected_id]}**.")

    col1, col2 = st.columns(2)
    with col1:
        st.button("Use Selected Protocol", type="primary", help="This will apply the protocol to the session (Not Implemented).")
    with col2:
        if st.button("Manage Protocols"):
            go_to('list_viewer')

def protocol_list_viewer():
    """Displays a list of all saved protocols with options to edit, delete, etc."""
    st.header("Protocol Library")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Here you can view, edit, or create new experiment protocols.")
    with col2:
        if st.button("＋ Create New Protocol", type="primary"):
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
                if p['is_archived']: name += " (Archived)"
                st.markdown(f"**{name}**")
                st.caption(f"ID: `{p['protocol_id']}` | Last updated: {p['updated_at']}")
            
            with p_col2:
                b_col1, b_col2, b_col3, b_col4 = st.columns(4)
                if b_col1.button("✏️", key=f"edit_{p['protocol_id']}", help="Edit Protocol"):
                    go_to('editor', edit_protocol_id=p['protocol_id'])
                if b_col2.button("👁️", key=f"preview_{p['protocol_id']}", help="Preview Protocol"):
                    go_to('preview', preview_protocol_id=p['protocol_id'])
                archive_verb = "Unarchive" if p['is_archived'] else "Archive"
                if b_col3.button("🗄️", key=f"archive_{p['protocol_id']}", help=f"{archive_verb} Protocol"):
                    archive_protocol(p['protocol_id'], archived=not p['is_archived'])
                    st.rerun()
                if b_col4.button("🗑️", key=f"delete_{p['protocol_id']}", help="Delete Protocol"):
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
    # Using st.data_editor with pandas DataFrame for better column config
    ingredients_df = pd.DataFrame(form_data.get('ingredients', []))
    
    edited_ingredients = st.data_editor(
        ingredients_df,
        num_rows="dynamic",
        key="ingredients_editor",
        use_container_width=True,
        column_config={
            "name": st.column_config.TextColumn("Ingredient Name", required=True),
            "min_concentration": st.column_config.NumberColumn("Min Concentration", format="%.4f", required=True),
            "max_concentration": st.column_config.NumberColumn("Max Concentration", format="%.4f", required=True),
        }
    )
    # The output of data_editor is a DataFrame, keep it that way for now.
    # We will convert back to records list before saving.
    form_data['ingredients'] = edited_ingredients

    # --- Schedule Editor ---
    st.subheader("Sample Selection Schedule")
    render_timeline(form_data.get('sample_selection_schedule', []))

    # UI to edit the schedule
    schedule = form_data.get('sample_selection_schedule', [])
    for i, block in enumerate(schedule):
        with st.expander(f"Edit Block {i+1}: Cycles {block['cycle_range']['start']}-{block['cycle_range']['end']}"):
            # In a real app, you'd have UI here to change ranges, modes, and samples.
            # This is a complex UI and for now we will just show the JSON.
            new_block_json = st.text_area(f"Block {i+1} JSON", value=json.dumps(block, indent=2), height=250, key=f"block_{i}")
            try:
                schedule[i] = json.loads(new_block_json)
            except json.JSONDecodeError:
                st.error(f"Invalid JSON in block {i+1}")

    if st.button("Add Schedule Block"):
        schedule.append({
            "cycle_range": {"start": 1, "end": 1},
            "mode": "user_selected"
        })
        st.rerun()

    # --- Save/Cancel Buttons ---
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Protocol", type="primary"):
            # Make a copy to modify for saving, preserving the original form state
            final_protocol = st.session_state.protocol_form_data.copy()

            # Convert ingredients DataFrame back to list of dicts for validation/saving
            if isinstance(final_protocol.get('ingredients'), pd.DataFrame):
                final_protocol['ingredients'] = final_protocol['ingredients'].to_dict('records')
            
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
                    go_to('list_viewer')
                else:
                    st.error("Failed to save protocol to the database.")

    with col2:
        if st.button("Cancel"):
            if 'protocol_form_data' in st.session_state:
                del st.session_state['protocol_form_data']
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

