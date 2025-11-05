# RoboTaste - Next Session TODO List

**Last Updated**: November 2, 2025
**Branch**: feature/bayesian-optimization
**Status**: Questionnaire system complete, ready for testing and BO integration

---

## HIGH PRIORITY - Testing & Validation

### 1. End-to-End Workflow Testing
**Goal**: Verify complete questionnaire system functionality

**Test Steps**:
- [ ] Start new session as moderator
- [ ] Select questionnaire type (test hedonic_preference)
- [ ] Activate participant with random starting position
- [ ] Complete PRE_QUESTIONNAIRE and verify database save
- [ ] Test 2D grid interface: click multiple positions
- [ ] Complete POST_QUESTIONNAIRE for each sample
- [ ] Verify sample_id linkage in database
- [ ] Test final response submission
- [ ] Export CSV and validate data completeness
- [ ] Check questionnaire_response JSON format
- [ ] Verify target_variable_value extraction

**Expected Results**:
- All questionnaires saved with correct questionnaire_type
- Each sample has unique sample_id UUID
- target_variable_value populated correctly
- is_initial=1 for random starting point
- is_final_response=1 for final submission
- CSV export contains all questionnaire data

**Testing Script**:
```bash
cd tests
python test_questionnaire_system.py
python test_backward_compatibility.py
```

---

### 2. Multi-Questionnaire Type Testing
**Goal**: Verify all 4 questionnaire types work correctly

**Test Each Type**:
- [ ] hedonic_preference (9-point scale)
- [ ] unified_feedback (satisfaction + confidence + strategy)
- [ ] multi_attribute (overall_liking + sweetness + flavor + purchase_intent)
- [ ] composite_preference (liking + healthiness weighted combination)

**Validation**:
- [ ] Questionnaire renders correctly
- [ ] Scale labels display properly
- [ ] Response validation works
- [ ] Target variable extracted correctly
- [ ] Database stores questionnaire_type accurately

---

### 3. Slider Interface Testing
**Goal**: Verify slider interface works with questionnaire system

**Test Steps**:
- [ ] Create 3-6 ingredient experiment
- [ ] Adjust sliders to select mixture
- [ ] Click "Finish and Rate" button
- [ ] Verify sample_id generation
- [ ] Complete questionnaire
- [ ] Test multiple samples in single trial
- [ ] Verify each sample gets unique UUID
- [ ] Check database for proper linking

---

## MEDIUM PRIORITY - Bayesian Optimization Integration

### 4. Target Variable Extraction Implementation
**Goal**: Extract and save target variables from all questionnaire responses

**Implementation Tasks**:
- [ ] Review `extract_and_save_target_variable()` function (sql_handler.py:2169)
- [ ] Integrate into POST_QUESTIONNAIRE workflow
- [ ] Call after `update_response_with_questionnaire()` succeeds
- [ ] Verify target_variable_value column populated
- [ ] Handle composite targets (weighted combinations)
- [ ] Test with all 4 questionnaire types
- [ ] Validate extraction accuracy

**Code Location**:
- `subject_interface.py` POST_QUESTIONNAIRE phase (around line 840)
- Add call after successful questionnaire update

**Example Integration**:
```python
if success:
    # Extract and save target variable for Bayesian optimization
    from sql_handler import extract_and_save_target_variable
    extract_and_save_target_variable(
        response_id=response_id,  # Need to get this from update function
        questionnaire_response=responses,
        questionnaire_type=questionnaire_type
    )
```

---

### 5. Gaussian Process Model Integration
**Goal**: Implement Bayesian optimization recommendation engine

**Research & Planning**:
- [ ] Review scikit-learn GaussianProcessRegressor
- [ ] Choose acquisition function (Expected Improvement recommended)
- [ ] Design model training workflow
- [ ] Plan next-sample recommendation display

**Implementation Tasks**:
- [ ] Create `bayesian_optimizer.py` module
- [ ] Implement `train_gaussian_process()` function
- [ ] Implement `predict_next_sample()` function
- [ ] Implement `calculate_acquisition_function()` function
- [ ] Add `save_bayesian_prediction()` integration
- [ ] Test with synthetic data first

**Database Integration**:
- [ ] Use `get_participant_target_values()` to retrieve training data
- [ ] Store predictions in `bo_predicted_value` column
- [ ] Store acquisition values in `bo_acquisition_value` column
- [ ] Link predictions to samples via sample_id

---

### 6. Moderator BO Monitoring Dashboard
**Goal**: Real-time Bayesian optimization visualization for moderators

**UI Components to Add** (moderator_interface.py):
- [ ] Optimization convergence graph (target value over time)
- [ ] Current best sample display
- [ ] Predicted optimal region visualization (for 2D grid)
- [ ] Acquisition function heatmap
- [ ] Participant exploration vs exploitation balance
- [ ] Recommendation confidence intervals

**Data Sources**:
- [ ] Query `responses` table for target_variable_value history
- [ ] Query `bo_predicted_value` for GP predictions
- [ ] Query `bo_acquisition_value` for acquisition scores
- [ ] Calculate statistics (mean, std, best, latest)

**Plotly Visualizations**:
- [ ] Line chart: Target value progression
- [ ] Scatter plot: Explored samples (color by target value)
- [ ] Heatmap: Predicted preference landscape
- [ ] Confidence bounds: GP uncertainty regions

---

## LOW PRIORITY - Documentation & Polish

### 7. Documentation Updates

**README.md Updates**:
- [ ] Add "Questionnaire System" section (see notes from summary)
- [ ] Document UUID-based sample tracking
- [ ] Explain 4 questionnaire types
- [ ] Add Bayesian optimization section (once implemented)
- [ ] Update database schema documentation
- [ ] Add screenshots of questionnaire UI

**API Documentation**:
- [ ] Document questionnaire_config.py functions
- [ ] Document new sql_handler.py functions
- [ ] Add usage examples for each questionnaire type
- [ ] Document BO prediction workflow

**User Guide**:
- [ ] Create moderator guide for questionnaire selection
- [ ] Explain when to use each questionnaire type
- [ ] Document sample_id workflow for researchers
- [ ] Add troubleshooting section

---

### 8. Code Quality & Refactoring

**subject_interface.py**:
- [ ] Remove TODO comment about unused col1, col3 variables (line 150)
- [ ] Extract questionnaire submission logic into helper function
- [ ] Consolidate sample_id generation (appears in multiple places)

**callback.py**:
- [ ] Review questionnaire rendering for DRY principles
- [ ] Consider extracting scale label rendering to helper function
- [ ] Add type hints to render_questionnaire()

**sql_handler.py**:
- [ ] Add return value (response_id) from update_response_with_questionnaire()
- [ ] Improve error messages with more context
- [ ] Consider connection pooling for high-concurrency scenarios

---

### 9. Performance Optimization

**Database Queries**:
- [ ] Verify index usage with EXPLAIN QUERY PLAN
- [ ] Test query performance with 1000+ responses
- [ ] Consider additional indexes if needed:
  - `CREATE INDEX idx_responses_participant_session ON responses(participant_id, session_id)`
  - `CREATE INDEX idx_responses_target_value ON responses(target_variable_value)`

**Memory Management**:
- [ ] Profile memory usage with multiple concurrent sessions
- [ ] Test with large questionnaire_response JSON objects
- [ ] Monitor session_state size in Streamlit

---

### 10. Additional Testing

**Edge Cases**:
- [ ] Test participant disconnection during questionnaire
- [ ] Test browser reload after sample selection (before questionnaire)
- [ ] Test session expiry during active trial
- [ ] Test concurrent questionnaire submissions
- [ ] Test extremely long text responses

**Stress Testing**:
- [ ] 10 concurrent sessions
- [ ] 100+ samples per participant
- [ ] Large JSON questionnaire responses (>10KB)
- [ ] Rapid sample selections (< 1 second apart)

**Error Scenarios**:
- [ ] Database locked error handling
- [ ] Invalid questionnaire_type in config
- [ ] Missing sample_id in session_state
- [ ] Duplicate sample_id (UUID collision, extremely rare)

---

## FUTURE ENHANCEMENTS (Backlog)

### Phase 2 - Advanced Features
- [ ] Custom questionnaire builder UI for moderators
- [ ] Conditional questionnaire logic (skip questions based on answers)
- [ ] Multi-page questionnaires with progress tracking
- [ ] Questionnaire templates library
- [ ] A/B testing different questionnaire types

### Phase 3 - Machine Learning
- [ ] Multi-objective Bayesian optimization
- [ ] Participant clustering based on preference patterns
- [ ] Predictive models for taste preferences
- [ ] Personalized recommendations per participant
- [ ] Active learning strategies

### Phase 4 - Analytics
- [ ] Statistical analysis dashboard
- [ ] Preference mapping visualizations
- [ ] Correlation analysis between ingredients and ratings
- [ ] Export to R/Python analysis-ready formats
- [ ] Automated report generation

---

## NOTES

### Current System State
- **Questionnaire System**: Complete and tested
- **Sample Tracking**: UUID-based, fully functional
- **Database Schema**: Migrated, backward compatible
- **Test Coverage**: 15 test cases passing
- **Branch**: feature/bayesian-optimization
- **Last Commit**: 8472856 - Complete questionnaire system

### Known Issues
- None currently identified

### Dependencies for BO Integration
```bash
pip install scikit-learn>=1.3.0  # For Gaussian Process
pip install scipy>=1.11.0        # For optimization
```

### Useful SQL Queries for Testing

**Check questionnaire data**:
```sql
SELECT participant_id, questionnaire_type, target_variable_value,
       questionnaire_response, is_initial, is_final_response
FROM responses
WHERE session_id = 'YOUR_SESSION_CODE'
ORDER BY created_at;
```

**Verify sample_id linkage**:
```sql
SELECT sample_id, COUNT(*) as count,
       GROUP_CONCAT(DISTINCT questionnaire_type) as types
FROM responses
WHERE sample_id IS NOT NULL
GROUP BY sample_id;
```

**Check BO columns**:
```sql
SELECT participant_id, target_variable_value,
       bo_predicted_value, bo_acquisition_value
FROM responses
WHERE target_variable_value IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;
```

---

## SESSION GOALS

**Primary Goal**: Complete end-to-end testing and verify system reliability

**Secondary Goal**: Begin Bayesian optimization integration (target variable extraction)

**Stretch Goal**: Implement basic GP model and predictions

---

**Status Tracking**:
- [ ] TODO.md created and reviewed
- [ ] Priorities understood
- [ ] Ready for next session

---

**Good luck with the next session!**
