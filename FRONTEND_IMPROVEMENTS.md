# Frontend Developer Instructions: GUI Improvements (Final Refined Version)

## Overview
You are tasked with improving 6 critical issues in the **RoboTaste** sensory experiment application. The application is built with **Streamlit** and uses a database-centric multi-device architecture.

**Target Devices:**
- **Moderator**: 13" laptop (1366x768 or 1440x900)
- **Subject**: 11" tablet (1024x768 or similar)

**Design Reference:** Match the aesthetic of https://mashaniv.wixsite.com/niv-taste-lab
- Clean, scientific aesthetic
- Professional typography
- Ample white space
- Subtle use of color accents
- Modern, minimalist approach

**Key Architecture Notes:**
- Main app: `main_app.py` (Streamlit)
- Styling: `robotaste/components/styles.py` (centralized CSS)
- Canvas: `robotaste/components/canvas.py` (2D grid interface)
- Views: `robotaste/views/` (subject, moderator, landing, protocol_manager)
- Theme config: `.streamlit/config.toml`
- Loading config: Already exists in protocol JSON under `loading_screen` key

---

## **Issue 1: Improve Loading Screen**

### Current Problem
The loading screen (ROBOT_PREPARING and LOADING phases) lacks visual appeal and doesn't provide adequate feedback during wait times.

### Current Implementation
- Located in: `robotaste/views/subject.py` (ROBOT_PREPARING and LOADING phase handlers)
- Helper function exists: `robotaste/utils/ui_helpers.py` → `render_loading_screen()` and `render_loading_spinner()`
- Configuration: Already stored in protocol JSON under `loading_screen` key with configurable duration

### Requirements

1. **Enhance the existing `render_loading_screen()` function** in `robotaste/utils/ui_helpers.py`:

   ```python
   def render_loading_screen(
       cycle_number: int,
       total_cycles: int = None,
       duration_seconds: int = 5,
       message: str = "Please rinse your mouth with water while the robot prepares the next sugar sample.",
       show_cycle_info: bool = True,
       show_progress_bar: bool = True,
       message_size: str = "large",
       **kwargs
   ):
       """
       Enhanced loading screen with clean, scientific aesthetic.
       Matches the style of mashaniv.wixsite.com/niv-taste-lab
       """
       
       # Clear any previous content
       st.empty()
       
       # Cycle header with clean, professional styling (matching reference site)
       if show_cycle_info:
           if total_cycles:
               st.markdown(
                   f"""
                   <div style='text-align: center; font-size: 3rem; 
                   font-weight: 300; color: #2C3E50; margin: 4rem 0 2rem 0;
                   letter-spacing: 0.05em;'>
                   Cycle <span style='font-weight: 600;'>{cycle_number}</span> of {total_cycles}
                   </div>
                   """,
                   unsafe_allow_html=True
               )
           else:
               st.markdown(
                   f"""
                   <div style='text-align: center; font-size: 3rem; 
                   font-weight: 300; color: #2C3E50; margin: 4rem 0 2rem 0;
                   letter-spacing: 0.05em;'>
                   Cycle <span style='font-weight: 600;'>{cycle_number}</span>
                   </div>
                   """,
                   unsafe_allow_html=True
               )
       
       # Message with clean, readable styling
       size_map = {"normal": "1.5rem", "large": "2rem", "extra_large": "2.5rem"}
       font_size = size_map.get(message_size, "2rem")
       
       st.markdown(
           f"""
           <div style='text-align: center; font-size: {font_size}; 
           font-weight: 400; color: #34495E; margin: 3rem auto; 
           max-width: 700px; line-height: 1.8; padding: 2rem;
           background: #F8F9FA; border-radius: 8px;
           border-left: 4px solid #6D28D9;'>
           {message}
           </div>
           """,
           unsafe_allow_html=True
       )
       
       # Animated progress bar with clean styling
       if show_progress_bar:
           # Add spacing
           st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
           
           progress_container = st.empty()
           time_container = st.empty()
           
           for i in range(duration_seconds + 1):
               progress = i / duration_seconds
               
               # Update progress bar
               progress_container.progress(progress)
               
               # Update time remaining with clean styling
               remaining = duration_seconds - i
               if remaining > 0:
                   time_container.markdown(
                       f"""
                       <div style='text-align: center; font-size: 1.25rem; 
                       color: #7F8C8D; margin-top: 1rem; font-weight: 300;'>
                       {remaining} seconds remaining
                       </div>
                       """,
                       unsafe_allow_html=True
                   )
               else:
                   time_container.markdown(
                       f"""
                       <div style='text-align: center; font-size: 1.25rem; 
                       color: #27AE60; margin-top: 1rem; font-weight: 400;'>
                       ✓ Ready
                       </div>
                       """,
                       unsafe_allow_html=True
                   )
               
               time.sleep(1)
   ```

2. **Update CSS in `robotaste/components/styles.py`** to match reference site aesthetic:

   ```python
   # Add to the get_style_css() function:
   
   /* === LOADING SCREEN STYLING (Clean, Scientific) === */
   .stSpinner {
       text-align: center !important;
       margin: 3rem 0 !important;
   }
   
   .stSpinner > div {
       font-size: 1.5rem !important;
       font-weight: 300 !important;
       color: #2C3E50 !important;
       letter-spacing: 0.05em !important;
   }
   
   .stSpinner svg {
       width: 120px !important;
       height: 120px !important;
       display: block !important;
       margin: 2rem auto !important;
   }
   
   /* Progress bar - clean, minimal styling */
   .stProgress > div > div {
       background: linear-gradient(90deg, #6D28D9 0%, #8B5CF6 100%) !important;
       height: 8px !important;
       border-radius: 4px !important;
       transition: width 0.3s ease !important;
   }
   
   .stProgress > div {
       background-color: #E8E8E8 !important;
       border-radius: 4px !important;
       height: 8px !important;
   }
   ```

3. **Verify existing loading configuration usage** in `subject.py`:
   - The code already calls `get_loading_screen_config(protocol)` from `ui_helpers.py`
   - Duration is already configurable via protocol JSON
   - No changes needed to the configuration logic

---

## **Issue 2: Fix Container Visibility During Transitions**

### Current Problem
Semi-transparent containers from the questionnaire remain visible when transitioning to the loading screen, creating visual clutter.

### Root Cause
Streamlit's state management can cause overlapping UI elements during phase transitions.

### Requirements

1. **Refactor phase rendering in `subject.py`** to ensure complete isolation:

   ```python
   def subject_interface():
       """Main subject interface with proper phase isolation."""
       init_session_state()
       
       # Get current phase
       current_phase_str = st.session_state.get("phase")
       if not current_phase_str:
           st.warning("Waiting for session to start...")
           sync_session_state(st.session_state.session_id, "subject")
           time.sleep(2)
           st.rerun()
           return
       
       # === CRITICAL: Use exclusive if/elif/else chain ===
       # This prevents multiple phases from rendering simultaneously
       
       if current_phase_str == ExperimentPhase.WAITING.value:
           _render_waiting_phase()
           
       elif current_phase_str == ExperimentPhase.CONSENT.value:
           render_consent_screen()
           
       elif current_phase_str == ExperimentPhase.REGISTRATION.value:
           render_registration_screen()
           
       elif current_phase_str == ExperimentPhase.INSTRUCTIONS.value:
           render_instructions_screen()
           
       elif current_phase_str == ExperimentPhase.ROBOT_PREPARING.value:
           _render_robot_preparing_phase()
           
       elif current_phase_str == ExperimentPhase.LOADING.value:
           _render_loading_phase()
           
       elif current_phase_str == ExperimentPhase.QUESTIONNAIRE.value:
           _render_questionnaire_phase()
           
       elif current_phase_str == ExperimentPhase.SELECTION.value:
           _render_selection_phase()
           
       elif current_phase_str == ExperimentPhase.COMPLETE.value:
           from robotaste.views.completion import show_subject_completion_screen
           show_subject_completion_screen()
           
       else:
           st.error(f"Unknown phase: {current_phase_str}")
           # Return immediately - don't render anything else
           return
   
   
   def _render_waiting_phase():
       """Isolated waiting phase renderer."""
       st.info("Waiting for moderator to start the experiment...")
       st.write("The experiment will begin shortly. Please be patient.")
       sync_session_state(st.session_state.session_id, "subject")
       time.sleep(2)
       st.rerun()
   
   
   def _render_robot_preparing_phase():
       """Isolated robot preparation phase renderer."""
       # Existing ROBOT_PREPARING logic here
       # ... (keep existing code)
   
   
   def _render_loading_phase():
       """Isolated loading phase renderer."""
       # Get current cycle and protocol
       cycle_num = get_current_cycle(st.session_state.session_id)
       protocol = get_session_protocol(st.session_state.session_id)
       
       # Get configuration
       from robotaste.utils.ui_helpers import get_loading_screen_config, render_loading_screen
       loading_config = get_loading_screen_config(protocol)
       
       # Calculate total cycles
       total_cycles = None
       if protocol:
           stopping_criteria = protocol.get("stopping_criteria", {})
           total_cycles = stopping_criteria.get("max_cycles")
       
       # Render loading screen (this function handles everything)
       render_loading_screen(
           cycle_number=cycle_num,
           total_cycles=total_cycles,
           **loading_config
       )
       
       # Transition to next phase
       transition_to_next_phase(
           current_phase_str=ExperimentPhase.LOADING.value,
           default_next_phase=ExperimentPhase.QUESTIONNAIRE,
           session_id=st.session_state.session_id,
           current_cycle=cycle_num,
       )
       st.rerun()
   
   
   def _render_questionnaire_phase():
       """Isolated questionnaire phase renderer."""
       # Existing QUESTIONNAIRE logic here
       # ... (keep existing code)
   
   
   def _render_selection_phase():
       """Isolated selection phase renderer."""
       cycle_info = prepare_cycle_sample(
           st.session_state.session_id, 
           get_current_cycle(st.session_state.session_id)
       )
       st.session_state.cycle_data = cycle_info
       
       # ... (rest of existing selection logic)
   ```

2. **Add transition CSS** to `styles.py`:

   ```python
   /* === CLEAN PHASE TRANSITIONS === */
   .main .block-container {
       animation: fadeIn 0.3s ease-in !important;
   }
   
   @keyframes fadeIn {
       from { opacity: 0; }
       to { opacity: 1; }
   }
   
   /* Ensure clean slate between phases */
   .element-container {
       animation: slideIn 0.3s ease-out !important;
   }
   
   @keyframes slideIn {
       from { 
           opacity: 0; 
           transform: translateY(10px); 
       }
       to { 
           opacity: 1; 
           transform: translateY(0); 
       }
   }
   ```

3. **Clean up session state during transitions** in `phase_utils.py`:

   ```python
   def transition_to_next_phase(current_phase_str, default_next_phase, session_id, current_cycle=None):
       """Clean transition with proper state cleanup."""
       
       # Clear phase-specific session state to prevent leakage
       phase_specific_keys = [
           'questionnaire_responses',
           'canvas_result',
           'last_saved_position',
           'phase_complete',
           'cycle_data',
           'override_bo'
       ]
       
       for key in phase_specific_keys:
           if key in st.session_state:
               del st.session_state[key]
       
       # Proceed with normal transition logic
       # ... (existing transition code)
   ```

4. **Ensure questionnaire forms use unique keys**:

   ```python
   # In robotaste/views/questionnaire.py, ensure forms have unique keys per cycle:
   
   def render_questionnaire(questionnaire_type: str, participant_id: str):
       """Render questionnaire with unique keys per cycle."""
       
       # Get current cycle for unique key
       cycle_num = get_current_cycle(st.session_state.session_id)
       
       with st.form(key=f"questionnaire_form_{questionnaire_type}_{cycle_num}"):
           # ... (existing questionnaire code)
   ```

---

## **Issue 3: Make QR Code and Subject URL Easily Accessible**

### Current Problem
Session code appears in a small green box. No QR code is displayed, and there's no easy way for moderators to share the session URL with subjects.

### Current Implementation
- Session creation: `robotaste/views/landing.py` → `landing_page()` function
- URL construction: Logic exists in code (uses `st.query_params.get("_host", "localhost:8501")`)
- Display: Minimal green box with session code

### Requirements

1. **Create new component file** `robotaste/components/session_info.py`:

   ```python
   """
   Session Info Panel Component
   
   Displays session code, QR code, and shareable URL for subject access.
   Matches the clean, scientific aesthetic of the reference site.
   """
   
   import streamlit as st
   import qrcode
   from io import BytesIO
   import logging
   
   logger = logging.getLogger(__name__)
   
   
   def generate_qr_code(url: str, size: int = 250) -> BytesIO:
       """
       Generate QR code for session URL.
       
       Args:
           url: URL to encode in QR code
           size: Size of QR code in pixels (box_size will be calculated)
           
       Returns:
           BytesIO object containing PNG image
       """
       qr = qrcode.QRCode(
           version=1,
           error_correction=qrcode.constants.ERROR_CORRECT_L,
           box_size=10,
           border=4,
       )
       qr.add_data(url)
       qr.make(fit=True)
       
       # Use clean purple color matching site aesthetic
       img = qr.make_image(fill_color="#6D28D9", back_color="white")
       
       # Convert to bytes
       buffer = BytesIO()
       img.save(buffer, format="PNG")
       buffer.seek(0)
       return buffer
   
   
   def get_subject_url(session_code: str) -> str:
       """
       Construct subject URL based on current host.
       Uses existing logic from the codebase.
       
       Args:
           session_code: 6-character session code
           
       Returns:
           Full URL for subject to join session
       """
       # Get base URL (same logic as in existing code)
       try:
           # Try to get from query params
           base_url = st.query_params.get("_host", "")
           if not base_url:
               # Fallback to localhost
               base_url = "localhost:8501"
           
           # Ensure http:// prefix
           if not base_url.startswith("http"):
               base_url = f"http://{base_url}"
           
       except Exception:
           base_url = "http://localhost:8501"
       
       return f"{base_url}/?role=subject&session={session_code}"
   
   
   def render_session_info_panel(session_code: str, expanded: bool = True):
       """
       Render session info panel with clean, scientific design.
       Matches aesthetic of mashaniv.wixsite.com/niv-taste-lab
       
       Args:
           session_code: 6-character session code
           expanded: Whether to show expanded by default
       """
       subject_url = get_subject_url(session_code)
       
       with st.expander("📱 Session Information", expanded=expanded):
           # Clean header section with session code
           st.markdown(
               f"""
               <div style='text-align: center; padding: 2.5rem; 
               background: #F8F9FA; border-radius: 8px; 
               border-left: 4px solid #6D28D9; margin-bottom: 2rem;'>
                   <div style='font-size: 1rem; color: #7F8C8D; 
                   font-weight: 400; margin-bottom: 0.5rem; 
                   letter-spacing: 0.1em; text-transform: uppercase;'>
                   Session Code
                   </div>
                   <div style='font-size: 3rem; color: #2C3E50; 
                   font-weight: 600; letter-spacing: 0.5rem; 
                   font-family: "Monaco", "Courier New", monospace;'>
                   {session_code}
                   </div>
               </div>
               """,
               unsafe_allow_html=True
           )
           
           # Two columns: QR code and URL
           col1, col2 = st.columns([1, 2])
           
           with col1:
               st.markdown("**Scan to Join**")
               # Generate and display QR code
               try:
                   qr_buffer = generate_qr_code(subject_url, size=250)
                   st.image(qr_buffer, use_container_width=True)
               except Exception as e:
                   logger.error(f"Failed to generate QR code: {e}")
                   st.error("QR code generation failed")
           
           with col2:
               st.markdown("**Share This Link**")
               st.code(subject_url, language=None)
               
               # Copy button
               if st.button("📋 Copy Link", key="copy_url_button", use_container_width=True):
                   # Use clipboard API via JavaScript
                   st.components.v1.html(
                       f"""
                       <script>
                       navigator.clipboard.writeText('{subject_url}').then(function() {{
                           console.log('Copied to clipboard');
                       }});
                       </script>
                       """,
                       height=0
                   )
                   st.success("✓ Link copied to clipboard")
               
               st.markdown("---")
               st.caption("**Instructions:** Subjects can scan the QR code or click the link to join the experiment.")
   ```

2. **Add QR code dependency** to `requirements.txt`:
   ```
   qrcode[pil]>=7.4.2
   ```

3. **Integrate into moderator view** - Update `robotaste/views/moderator.py`:

   ```python
   from robotaste.components.session_info import render_session_info_panel
   
   def moderator_dashboard():
       """Main moderator dashboard."""
       
       # ... existing imports and setup ...
       
       # Display session info at the top (always expanded for easy access)
       if st.session_state.get("session_code"):
           render_session_info_panel(
               st.session_state.session_code, 
               expanded=True
           )
           st.markdown("---")  # Visual separator
       
       # Rest of dashboard...
       # ... (existing code continues)
   ```

4. **Update landing page** - Enhance `robotaste/views/landing.py`:

   ```python
   # In the "New Session" tab, after session creation:
   
   if st.button("Create New Session", ...):
       if moderator_name:
           # ... existing session creation code ...
           
           # Show success with better formatting
           st.success(f"✓ Session created successfully!")
           
           # Import and show session info immediately
           from robotaste.components.session_info import render_session_info_panel
           render_session_info_panel(new_session_code, expanded=True)
           
           st.info("Configure your experiment settings on the next screen.")
           time.sleep(2)
           st.rerun()
   ```

---

## **Issue 4: Declutter Protocol Selection**

### Current Problem
The protocol selection area in `robotaste/views/protocol_manager.py` has too many competing elements without clear visual hierarchy.

### Current Implementation
- File: `robotaste/views/protocol_manager.py`
- Function: `protocol_selection_screen()`
- Issues: Dropdown, JSON viewer, import/export, documentation all competing for attention

### Requirements

1. **Completely refactor `protocol_selection_screen()`** in `protocol_manager.py`:

   ```python
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
           with st.container():
               st.markdown(
                   f"""
                   <div style='background: #F8F9FA; padding: 1.5rem; 
                   border-radius: 8px; border-left: 4px solid #6D28D9; 
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
                   st.metric("Questionnaire", q_type.replace('_', ' ').title())
               
               with col4:
                   # Preview button
                   if st.button("👁️ Preview Details", key="preview_btn", use_container_width=True):
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
               st.success(f"✓ Protocol '{protocol_options[selected_id]['name']}' applied")
               # TODO: Actual protocol application logic
       
       with col2:
           if st.button("Protocol Library", use_container_width=True):
               go_to('list_viewer')
       
       with col3:
           if st.button("+ New", use_container_width=True):
               go_to('editor')
       
       # === SECTION 4: Advanced Options (Collapsed) ===
       with st.expander("⚙️ Advanced Options", expanded=False):
           st.markdown("### Import Protocol")
           
           uploaded_file = st.file_uploader(
               "Upload protocol JSON file",
               type=['json'],
               help="Import a protocol from a JSON file",
               key="protocol_upload",
               label_visibility="collapsed"
           )
           
           if uploaded_file:
               try:
                   import json
                   protocol_data = json.load(uploaded_file)
                   st.success("✓ Protocol file loaded")
                   st.json(protocol_data)
                   # TODO: Import logic
               except Exception as e:
                   st.error(f"Failed to load protocol: {e}")
           
           st.markdown("---")
           st.markdown("### Documentation")
           st.markdown("📄 [Protocol Schema Reference](https://docs.robotaste.com/schema)")
           st.markdown("📖 [User Guide](https://docs.robotaste.com/guide)")
   ```

2. **Add selectbox styling** to `styles.py`:

   ```python
   /* === ENHANCED SELECTBOX STYLING === */
   .stSelectbox [data-baseweb="select"] {
       min-height: 3.5rem !important;
       border: 2px solid #D1D5DB !important;
       border-radius: 8px !important;
       background-color: white !important;
       transition: all 0.2s ease !important;
   }
   
   .stSelectbox [data-baseweb="select"]:hover {
       border-color: #9CA3AF !important;
   }
   
   .stSelectbox [data-baseweb="select"]:focus-within {
       border-color: #6D28D9 !important;
       box-shadow: 0 0 0 3px rgba(109, 40, 217, 0.1) !important;
   }
   
   /* Selectbox text visibility fix */
   .stSelectbox [data-baseweb="select"] div,
   .stSelectbox [data-baseweb="select"] span {
       font-size: 1.1rem !important;
       color: #2C3E50 !important;
       font-weight: 400 !important;
   }
   
   /* Dropdown options styling */
   [data-baseweb="popover"] [role="listbox"] {
       background-color: white !important;
       border: 1px solid #E5E7EB !important;
       border-radius: 8px !important;
       box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
   }
   
   [data-baseweb="popover"] li {
       font-size: 1rem !important;
       color: #2C3E50 !important;
       padding: 12px 16px !important;
       border-bottom: 1px solid #F3F4F6 !important;
   }
   
   [data-baseweb="popover"] li:hover {
       background-color: #F8F9FA !important;
   }
   ```

3. **Simplify protocol library view** in `protocol_list_viewer()`:

   ```python
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
       
       # Display protocols as clean cards
       for p in protocols:
           with st.container():
               # Card with clean styling
               status = " (Archived)" if p['is_archived'] else ""
               
               col1, col2 = st.columns([4, 1])
               
               with col1:
                   st.markdown(f"**{p['name']}{status}**")
                   st.caption(p.get('description', 'No description'))
                   st.caption(f"Last updated: {p['updated_at'][:10]}")
               
               with col2:
                   # Action buttons in a clean row
                   btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                   
                   with btn_col1:
                       if st.button("✏️", key=f"edit_{p['protocol_id']}", help="Edit"):
                           go_to('editor', edit_protocol_id=p['protocol_id'])
                   
                   with btn_col2:
                       if st.button("👁️", key=f"view_{p['protocol_id']}", help="View"):
                           go_to('preview', preview_protocol_id=p['protocol_id'])
                   
                   with btn_col3:
                       icon = "📦" if p['is_archived'] else "🗄️"
                       if st.button(icon, key=f"archive_{p['protocol_id']}", help="Archive/Unarchive"):
                           archive_protocol(p['protocol_id'], archived=not p['is_archived'])
                           st.rerun()
                   
                   with btn_col4:
                       if st.button("🗑️", key=f"delete_{p['protocol_id']}", help="Delete"):
                           if st.session_state.get(f"confirm_delete_{p['protocol_id']}", False):
                               delete_protocol(p['protocol_id'])
                               st.rerun()
                           else:
                               st.session_state[f"confirm_delete_{p['protocol_id']}"] = True
                               st.warning("Click again to confirm deletion")
               
               st.markdown("---")
   ```

---

## **Issue 5: Screen Size Compatibility**

### Current Problem
Layouts don't adapt well to different screen sizes. Content gets cut off or requires excessive scrolling.

### Target Devices
- **Moderator**: 13" laptop (1366x768 or 1440x900)
- **Subject**: 11" tablet (1024x768)

### Current Implementation
- Canvas sizing: `robotaste/components/canvas.py` → `get_canvas_size()`
- Viewport detection: `robotaste/utils/viewport.py` (exists but limited)
- CSS: `robotaste/components/styles.py`

### Requirements

1. **Optimize canvas sizing for target devices** in `canvas.py`:

   ```python
   def get_canvas_size() -> int:
       """
       Get responsive canvas size optimized for target devices.
       
       Target devices:
       - Moderator: 13" laptop (1366x768)
       - Subject: 11" tablet (1024x768)
       
       Returns:
           Canvas size in pixels (square)
       """
       try:
           # Try to get viewport data
           viewport = st.session_state.get('viewport_data', {'width': 1024, 'height': 768})
           viewport_width = viewport.get('width', 1024)
           viewport_height = viewport.get('height', 768)
           
           # Calculate based on device type
           # Tablets (subject): More screen space for canvas
           if viewport_width <= 1024:
               # 11" tablet - use larger portion of screen
               canvas_size = min(int(viewport_width * 0.65), 500)
           
           # Small laptops (moderator)
           elif viewport_width <= 1440:
               # 13" laptop - moderate canvas size
               canvas_size = min(int(viewport_width * 0.45), 500)
           
           # Larger screens
           else:
               canvas_size = 600
           
           # Ensure minimum size for usability
           canvas_size = max(400, canvas_size)
           
           return canvas_size
           
       except Exception:
           # Safe fallback for tablets
           return 450
   ```

2. **Update responsive CSS** in `styles.py` for target devices:

   ```python
   def get_style_css() -> str:
       """Generate CSS optimized for 13" laptop and 11" tablet."""
       
       # Get viewport data
       viewport = st.session_state.get('viewport_data', {'width': 1366, 'height': 768})
       font_scale = get_responsive_font_scale()
       
       return f"""
   <style>
       /* === DEVICE-OPTIMIZED RESPONSIVE DESIGN === */
       :root {{
           --viewport-width: {viewport.get('width', 1366)}px;
           --viewport-height: {viewport.get('height', 768)}px;
           --font-scale: {font_scale};
           
           /* Scientific color palette (matching reference site) */
           --primary: #6D28D9;
           --primary-light: #8B5CF6;
           --text-primary: #2C3E50;
           --text-secondary: #7F8C8D;
           --bg-primary: #FFFFFF;
           --bg-secondary: #F8F9FA;
           --border: #E5E7EB;
           
           /* Responsive spacing */
           --spacing-xs: 0.5rem;
           --spacing-sm: 1rem;
           --spacing-md: 1.5rem;
           --spacing-lg: 2rem;
           --spacing-xl: 3rem;
       }}
       
       /* === MAIN CONTAINER (Optimized for laptop/tablet) === */
       .main .block-container {{
           max-width: 100% !important;
           padding: var(--spacing-md) var(--spacing-lg) !important;
           max-height: calc(var(--viewport-height) - 3rem) !important;
           overflow-y: auto !important;
       }}
       
       /* === TYPOGRAPHY (Clean, Scientific) === */
       body {{
           font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", 
                        "Roboto", "Helvetica Neue", Arial, sans-serif !important;
           color: var(--text-primary) !important;
           line-height: 1.6 !important;
       }}
       
       h1 {{
           font-size: clamp(2rem, 3vw, 2.5rem) !important;
           font-weight: 300 !important;
           color: var(--text-primary) !important;
           letter-spacing: 0.05em !important;
           margin: var(--spacing-lg) 0 var(--spacing-md) 0 !important;
       }}
       
       h2 {{
           font-size: clamp(1.75rem, 2.5vw, 2rem) !important;
           font-weight: 400 !important;
           color: var(--text-primary) !important;
           margin: var(--spacing-md) 0 var(--spacing-sm) 0 !important;
       }}
       
       h3 {{
           font-size: clamp(1.5rem, 2vw, 1.75rem) !important;
           font-weight: 400 !important;
           color: var(--text-primary) !important;
           margin: var(--spacing-md) 0 var(--spacing-sm) 0 !important;
       }}
       
       p, div, span, label {{
           font-size: clamp(1rem, 1.5vw, 1.125rem) !important;
           line-height: 1.7 !important;
           color: var(--text-primary) !important;
       }}
       
       .stCaption {{
           font-size: 0.9rem !important;
           color: var(--text-secondary) !important;
       }}
       
       /* === BUTTONS (Clean Design) === */
       .stButton > button {{
           border-radius: 6px !important;
           padding: 0.75rem 1.5rem !important;
           font-size: clamp(0.95rem, 1.5vw, 1.1rem) !important;
           font-weight: 500 !important;
           border: 2px solid transparent !important;
           transition: all 0.2s ease !important;
           min-height: 44px !important; /* Touch-friendly for tablets */
       }}
       
       .stButton > button[kind="primary"] {{
           background: var(--primary) !important;
           color: white !important;
       }}
       
       .stButton > button[kind="primary"]:hover {{
           background: var(--primary-light) !important;
           transform: translateY(-1px) !important;
       }}
       
       .stButton > button[kind="secondary"] {{
           background: white !important;
           color: var(--primary) !important;
           border-color: var(--primary) !important;
       }}
       
       /* === FORMS & INPUTS === */
       .stTextInput input, .stNumberInput input {{
           border: 2px solid var(--border) !important;
           border-radius: 6px !important;
           padding: 0.75rem !important;
           font-size: clamp(1rem, 1.5vw, 1.125rem) !important;
           min-height: 44px !important;
           transition: border-color 0.2s ease !important;
       }}
       
       .stTextInput input:focus, .stNumberInput input:focus {{
           border-color: var(--primary) !important;
           box-shadow: 0 0 0 3px rgba(109, 40, 217, 0.1) !important;
           outline: none !important;
       }}
       
       /* === SLIDER (Enhanced for touch) === */
       .stSlider > div > div > div > div {{
           height: 8px !important;
           background: linear-gradient(90deg, #E5E7EB 0%, var(--primary) 100%) !important;
           border-radius: 4px !important;
       }}
       
       .stSlider > div > div > div > div > div {{
           width: 32px !important; /* Larger for touch on tablet */
           height: 32px !important;
           background: white !important;
           border: 3px solid var(--primary) !important;
           box-shadow: 0 2px 4px rgba(0,0,0,0.15) !important;
       }}
       
       /* === CANVAS CONTAINER === */
       .canvas-container {{
           display: flex !important;
           justify-content: center !important;
           align-items: center !important;
           margin: var(--spacing-lg) 0 !important;
       }}
       
       /* === METRICS (Clean Cards) === */
       [data-testid="stMetric"] {{
           background: var(--bg-secondary) !important;
           border: 1px solid var(--border) !important;
           border-radius: 8px !important;
           padding: 1rem !important;
       }}
       
       [data-testid="stMetric"] label {{
           font-size: 0.875rem !important;
           font-weight: 500 !important;
           color: var(--text-secondary) !important;
           text-transform: uppercase !important;
           letter-spacing: 0.05em !important;
       }}
       
       [data-testid="stMetric"] [data-testid="stMetricValue"] {{
           font-size: 2rem !important;
           font-weight: 600 !important;
           color: var(--primary) !important;
       }}
       
       /* === DEVICE-SPECIFIC ADJUSTMENTS === */
       
       /* 11" Tablet (Subject Interface) */
       @media (max-width: 1024px) {{
           .main .block-container {{
               padding: var(--spacing-sm) var(--spacing-md) !important;
           }}
           
           /* Larger touch targets */
           .stButton > button {{
               min-height: 48px !important;
               padding: 1rem 2rem !important;
           }}
           
           /* Optimize canvas for tablet */
           .canvas-container {{
               max-width: 95vw !important;
           }}
       }}
       
       /* 13" Laptop (Moderator Interface) */
       @media (max-width: 1440px) and (min-width: 1025px) {{
           .main .block-container {{
               max-width: 1300px !important;
               margin: 0 auto !important;
           }}
           
           /* Optimize sidebar width */
           section[data-testid="stSidebar"] {{
               width: 250px !important;
               min-width: 250px !important;
           }}
       }}
       
       /* Short screens (optimize vertical space) */
       @media (max-height: 800px) {{
           h1 {{
               margin-top: var(--spacing-sm) !important;
               margin-bottom: var(--spacing-xs) !important;
           }}
           
           .main .block-container {{
               padding-top: var(--spacing-sm) !important;
           }}
           
           [data-testid="stMetric"] {{
               padding: 0.75rem !important;
           }}
       }}
       
       /* === TABLES (Clean, Scientific) === */
       .stDataFrame {{
           border: 1px solid var(--border) !important;
           border-radius: 8px !important;
       }}
       
       /* === EXPANDERS === */
       .streamlit-expanderHeader {{
           background: var(--bg-secondary) !important;
           border-radius: 6px !important;
           font-weight: 500 !important;
       }}
       
       /* === CONTAINERS === */
       [data-testid="stContainer"] {{
           border: 1px solid var(--border) !important;
           border-radius: 8px !important;
           padding: var(--spacing-md) !important;
           margin: var(--spacing-sm) 0 !important;
       }}
       
       /* === ANIMATION === */
       .element-container {{
           animation: fadeIn 0.3s ease-in !important;
       }}
       
       @keyframes fadeIn {{
           from {{ opacity: 0; transform: translateY(5px); }}
           to {{ opacity: 1; transform: translateY(0); }}
       }}
   </style>
   """
   ```

3. **Test on target resolutions**:
   ```python
   # Add to testing checklist:
   # - 1366x768 (13" laptop - moderator primary)
   # - 1440x900 (13" laptop - moderator alternative)
   # - 1024x768 (11" tablet - subject primary)
   # - 1280x800 (11" tablet - subject alternative)
   ```

---

## **Issue 6: Overall Aesthetics - Match Reference Site**

### Current Problem
The interface needs to match the clean, scientific aesthetic of https://mashaniv.wixsite.com/niv-taste-lab

### Design Analysis of Reference Site
- Clean, minimalist design
- Ample white space
- Professional typography (light weight headers, readable body text)
- Subtle use of purple accent color
- Scientific, professional tone
- Card-based layouts with subtle borders
- Minimal shadows
- Clean, flat design

### Requirements

1. **Update color system** in `styles.py` to match reference site:

   ```python
   :root {{
       /* Color Palette (inspired by reference site) */
       --primary: #6D28D9;           /* Purple accent */
       --primary-light: #8B5CF6;     /* Light purple */
       --primary-dark: #5B21B6;      /* Dark purple */
       
       /* Neutrals (clean, scientific) */
       --text-primary: #2C3E50;      /* Dark blue-gray for text */
       --text-secondary: #7F8C8D;    /* Medium gray for secondary */
       --text-light: #95A5A6;        /* Light gray for captions */
       
       --bg-primary: #FFFFFF;        /* Pure white background */
       --bg-secondary: #F8F9FA;      /* Very light gray */
       --bg-tertiary: #F3F4F6;       /* Light gray for cards */
       
       --border-light: #E5E7EB;      /* Light border */
       --border-medium: #D1D5DB;     /* Medium border */
       
       /* Semantic colors (muted, professional) */
       --success: #27AE60;           /* Green */
       --success-light: #E8F5E9;
       --warning: #F39C12;           /* Orange */
       --warning-light: #FFF8E1;
       --error: #E74C3C;             /* Red */
       --error-light: #FFEBEE;
       --info: #3498DB;              /* Blue */
       --info-light: #E3F2FD;
       
       /* Minimal shadows (flat design) */
       --shadow-minimal: 0 1px 2px rgba(0,0,0,0.05);
       --shadow-subtle: 0 1px 3px rgba(0,0,0,0.08);
       
       /* Transitions */
       --transition: 0.2s ease;
   }}
   ```

2. **Typography matching reference site**:

   ```python
   /* === TYPOGRAPHY (Matching Reference Site) === */
   body {{
       font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", 
                    "Roboto", "Oxygen", "Ubuntu", "Helvetica Neue", 
                    Arial, sans-serif !important;
       color: var(--text-primary) !important;
       line-height: 1.7 !important;
       font-weight: 400 !important;
   }}
   
   /* Light-weight headers (matching reference site) */
   h1 {{
       font-size: clamp(2rem, 3vw, 2.5rem) !important;
       font-weight: 300 !important;  /* Light weight */
       color: var(--text-primary) !important;
       letter-spacing: 0.05em !important;
       margin: 2rem 0 1rem 0 !important;
       line-height: 1.3 !important;
   }}
   
   h2 {{
       font-size: clamp(1.75rem, 2.5vw, 2rem) !important;
       font-weight: 300 !important;  /* Light weight */
       color: var(--text-primary) !important;
       letter-spacing: 0.03em !important;
       margin: 1.5rem 0 1rem 0 !important;
   }}
   
   h3 {{
       font-size: clamp(1.5rem, 2vw, 1.75rem) !important;
       font-weight: 400 !important;
       color: var(--text-primary) !important;
       margin: 1.5rem 0 0.75rem 0 !important;
   }}
   
   /* Readable body text */
   p, div, span {{
       font-size: clamp(1rem, 1.5vw, 1.125rem) !important;
       line-height: 1.7 !important;
       color: var(--text-primary) !important;
       font-weight: 400 !important;
   }}
   
   /* Light captions */
   .stCaption {{
       font-size: 0.9rem !important;
       color: var(--text-secondary) !important;
       font-weight: 400 !important;
   }}
   ```

3. **Clean button design**:

   ```python
   /* === BUTTONS (Clean, Flat Design) === */
   .stButton > button {{
       background: var(--primary) !important;
       color: white !important;
       border: none !important;
       border-radius: 6px !important;
       padding: 0.75rem 1.75rem !important;
       font-size: 1rem !important;
       font-weight: 500 !important;
       letter-spacing: 0.02em !important;
       transition: all var(--transition) !important;
       box-shadow: none !important;  /* Flat design */
       cursor: pointer !important;
   }}
   
   .stButton > button:hover {{
       background: var(--primary-light) !important;
       transform: translateY(-1px) !important;
       box-shadow: var(--shadow-subtle) !important;
   }}
   
   .stButton > button:active {{
       transform: translateY(0) !important;
   }}
   
   .stButton > button[kind="secondary"] {{
       background: transparent !important;
       color: var(--primary) !important;
       border: 2px solid var(--primary) !important;
   }}
   
   .stButton > button[kind="secondary"]:hover {{
       background: var(--bg-secondary) !important;
   }}
   ```

4. **Clean card design**:

   ```python
   /* === CARDS & CONTAINERS (Minimal, Scientific) === */
   [data-testid="stContainer"] {{
       background: white !important;
       border: 1px solid var(--border-light) !important;
       border-radius: 8px !important;
       padding: 1.5rem !important;
       margin: 1rem 0 !important;
       box-shadow: none !important;  /* No shadows */
   }}
   
   /* Highlighted cards (with left border) */
   .highlight-card {{
       border-left: 4px solid var(--primary) !important;
       background: var(--bg-secondary) !important;
   }}
   ```

5. **Clean forms and inputs**:

   ```python
   /* === FORMS & INPUTS (Clean, Professional) === */
   .stTextInput input, .stNumberInput input, .stTextArea textarea {{
       border: 2px solid var(--border-medium) !important;
       border-radius: 6px !important;
       padding: 0.75rem !important;
       font-size: 1rem !important;
       color: var(--text-primary) !important;
       background: white !important;
       transition: border-color var(--transition) !important;
       box-shadow: none !important;
   }}
   
   .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {{
       border-color: var(--primary) !important;
       box-shadow: 0 0 0 3px rgba(109, 40, 217, 0.08) !important;
       outline: none !important;
   }}
   
   /* Labels */
   .stTextInput label, .stNumberInput label, .stTextArea label {{
       font-size: 0.95rem !important;
       font-weight: 500 !important;
       color: var(--text-primary) !important;
       margin-bottom: 0.5rem !important;
   }}
   ```

6. **Minimal metrics/cards**:

   ```python
   /* === METRICS (Clean, Card-Based) === */
   [data-testid="stMetric"] {{
       background: var(--bg-secondary) !important;
       border: 1px solid var(--border-light) !important;
       border-radius: 8px !important;
       padding: 1.25rem !important;
       transition: all var(--transition) !important;
   }}
   
   [data-testid="stMetric"]:hover {{
       border-color: var(--border-medium) !important;
   }}
   
   [data-testid="stMetric"] label {{
       font-size: 0.85rem !important;
       font-weight: 500 !important;
       color: var(--text-secondary) !important;
       text-transform: uppercase !important;
       letter-spacing: 0.05em !important;
       margin-bottom: 0.5rem !important;
   }}
   
   [data-testid="stMetric"] [data-testid="stMetricValue"] {{
       font-size: 2rem !important;
       font-weight: 600 !important;
       color: var(--primary) !important;
       line-height: 1.2 !important;
   }}
   
   [data-testid="stMetric"] [data-testid="stMetricDelta"] {{
       font-size: 0.9rem !important;
       font-weight: 400 !important;
   }}
   ```

7. **Ample white space**:

   ```python
   /* === SPACING (Generous, Breathable) === */
   .main .block-container {{
       padding: 2rem 3rem !important;
       max-width: 1400px !important;
       margin: 0 auto !important;
   }}
   
   /* Section spacing */
   .element-container {{
       margin-bottom: 1.5rem !important;
   }}
   
   h1, h2, h3 {{
       margin-top: 2.5rem !important;
       margin-bottom: 1rem !important;
   }}
   
   p {{
       margin-bottom: 1rem !important;
   }}
   
   /* Horizontal dividers */
   hr {{
       border: none !important;
       border-top: 1px solid var(--border-light) !important;
       margin: 2.5rem 0 !important;
   }}
   ```

8. **Clean alerts/messages**:

   ```python
   /* === ALERTS & MESSAGES (Minimal Design) === */
   .stSuccess {{
       background: var(--success-light) !important;
       border: none !important;
       border-left: 4px solid var(--success) !important;
       border-radius: 6px !important;
       padding: 1rem 1.25rem !important;
       color: var(--text-primary) !important;
   }}
   
   .stError {{
       background: var(--error-light) !important;
       border: none !important;
       border-left: 4px solid var(--error) !important;
       border-radius: 6px !important;
       padding: 1rem 1.25rem !important;
       color: var(--text-primary) !important;
   }}
   
   .stWarning {{
       background: var(--warning-light) !important;
       border: none !important;
       border-left: 4px solid var(--warning) !important;
       border-radius: 6px !important;
       padding: 1rem 1.25rem !important;
       color: var(--text-primary) !important;
   }}
   
   .stInfo {{
       background: var(--info-light) !important;
       border: none !important;
       border-left: 4px solid var(--info) !important;
       border-radius: 6px !important;
       padding: 1rem 1.25rem !important;
       color: var(--text-primary) !important;
   }}
   ```

9. **Update `.streamlit/config.toml`** to match:

   ```toml
   [theme]
   base = "light"
   primaryColor = "#6D28D9"
   backgroundColor = "#FFFFFF"
   secondaryBackgroundColor = "#F8F9FA"
   textColor = "#2C3E50"
   font = "sans serif"
   ```

---

## **Priority Implementation Order**

Based on impact and dependencies:

1. **Issue 2** (Container visibility) - 30 min - Critical bug fix
2. **Issue 5** (Screen compatibility) - 2 hours - Foundation for all UI
3. **Issue 6** (Aesthetics) - 3 hours - Visual polish, affects all views
4. **Issue 1** (Loading screen) - 1 hour - High-impact UX improvement
5. **Issue 3** (QR code) - 2 hours - New feature, critical for usability
6. **Issue 4** (Protocol declutter) - 1.5 hours - UX polish

**Total estimated time: ~10 hours**

---

## **Testing Checklist**

### Functional Testing
- [ ] All phases render in isolation without overlap
- [ ] Phase transitions are smooth and complete
- [ ] QR codes generate and scan correctly
- [ ] Session URLs construct properly based on host
- [ ] Protocol selection updates state correctly
- [ ] Canvas scales appropriately on both devices

### Visual Testing (Reference Site Match)
- [ ] Typography matches (light headers, readable body)
- [ ] Color palette matches (purple accent, neutral grays)
- [ ] Spacing feels generous and breathable
- [ ] Design is flat/minimal (no heavy shadows)
- [ ] Cards have subtle borders only
- [ ] Buttons have clean, flat design

### Responsive Testing (Target Devices)
- [ ] **Moderator (13" laptop)**:
  - [ ] 1366x768 resolution
  - [ ] 1440x900 resolution
  - [ ] All dashboard elements visible without scrolling
  - [ ] Protocol manager fully functional
  - [ ] Session info panel accessible
  
- [ ] **Subject (11" tablet)**:
  - [ ] 1024x768 resolution
  - [ ] 1280x800 resolution
  - [ ] Canvas sized appropriately (touch-friendly)
  - [ ] All touch targets ≥44px
  - [ ] Text readable without zooming
  - [ ] Loading screens clear and visible

### Cross-browser Testing
- [ ] Chrome (primary)
- [ ] Firefox
- [ ] Safari (for tablets)

---

## **Implementation Notes**

### Code Organization
- All CSS centralized in `robotaste/components/styles.py`
- New components in `robotaste/components/` (e.g., `session_info.py`)
- View-specific logic stays in `robotaste/views/`
- Call `apply_styles()` early in `main_app.py`

### Key Files to Modify
1. `robotaste/components/styles.py` - All CSS changes
2. `robotaste/utils/ui_helpers.py` - Loading screen enhancement
3. `robotaste/views/subject.py` - Phase isolation refactor
4. `robotaste/components/canvas.py` - Canvas sizing optimization
5. `robotaste/components/session_info.py` - New file (QR code)
6. `robotaste/views/protocol_manager.py` - Selection screen simplification
7. `robotaste/views/moderator.py` - Integrate session info panel

### Dependencies to Add
```txt
qrcode[pil]>=7.4.2
```

### Streamlit Best Practices
- Use `st.session_state` for persistent data
- Use `st.rerun()` for phase transitions
- Use unique keys for all widgets: `key=f"widget_{cycle_num}"`
- Never overlap phase rendering (use exclusive if/elif)
- Always sync with database via `sync_session_state()`

### Loading Configuration
- Already exists in protocol JSON under `loading_screen` key
- Configurable via: `duration_seconds`, `message`, `show_cycle_info`, `show_progress_bar`, `message_size`
- Access via: `get_loading_screen_config(protocol)` from `ui_helpers.py`
- No changes needed to configuration structure

### URL Construction
- Logic already exists: `st.query_params.get("_host", "localhost:8501")`
- Works automatically based on deployment environment
- QR code will use the same logic

---

## **Questions Resolved**

1. ✓ Target devices: 13" laptop (moderator), 11" tablet (subject)
2. ✓ URL construction: Based on runtime host (already in code)
3. ✓ Design reference: Match https://mashaniv.wixsite.com/niv-taste-lab
4. ✓ Loading duration: Configurable (already in protocol JSON)
5. ✓ Session info visibility: Implement as expander (flexible)
6. ✓ Dark mode: Not needed
