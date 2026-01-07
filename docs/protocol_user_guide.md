# RoboTaste Protocol Management User Guide

**For Researchers and Experiment Designers**

**Last Updated:** January 2026

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Creating a Protocol](#creating-a-protocol)
4. [Managing Protocols](#managing-protocols)
5. [Running Experiments with Protocols](#running-experiments-with-protocols)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Introduction

### What is a Protocol?

A **protocol** is a reusable experiment template that defines:
- Which ingredients to use and their concentration ranges
- When to use predetermined samples, user selection, or Bayesian Optimization
- Which questionnaire participants will answer
- When the experiment should stop

### Why Use Protocols?

✅ **Reusability** - Save time by reusing successful experiment designs
✅ **Consistency** - Ensure all participants get the same experiment flow
✅ **Collaboration** - Share protocols with colleagues via JSON files
✅ **Reproducibility** - Document exact experimental parameters
✅ **Version Control** - Track protocol changes over time

---

## Getting Started

### Accessing the Protocol Manager

1. Launch RoboTaste application
2. Navigate to **Protocol Manager** (from main menu or sidebar)
3. You'll see three tabs:
   - **Browse Protocols** - View and search existing protocols
   - **Create/Edit** - Create new or edit existing protocols
   - **Preview** - View protocol details in read-only mode

### Understanding the Interface

**Protocol List View:**
- Search box for finding protocols by name
- Filter by tags
- Archive/Unarchive buttons
- Edit, Preview, and Delete actions

**Protocol Editor:**
- Basic Settings (name, version, description, tags)
- Ingredient Configuration
- Sample Selection Schedule
- Advanced Settings (questionnaire type, BO config)

---

## Creating a Protocol

### Step 1: Basic Information

1. Click **"Create New Protocol"** in the Protocol Manager
2. Fill in basic information:
   - **Name:** Give your protocol a descriptive name
     - ✅ Good: "Sugar-Salt Preference Learning v1"
     - ❌ Bad: "Test" or "Protocol1"
   - **Version:** Start with "1.0"
   - **Description:** Explain the experiment's purpose
   - **Tags:** Add tags for organization (e.g., "preference-learning", "two-ingredient")

**Example:**
```
Name: Two-Ingredient Optimization Study
Version: 1.0
Description: Adaptive BO experiment to find optimal Sugar-Salt blend
Tags: bo, optimization, sugar, salt
```

### Step 2: Configure Ingredients

1. Select ingredients from the dropdown menu
2. For each ingredient, specify:
   - **Min Concentration:** Lowest value (mM)
   - **Max Concentration:** Highest value (mM)

**Available Ingredients:**
- Sugar (typical range: 0-100 mM)
- Salt (typical range: 0-50 mM)
- Citric Acid (typical range: 0-30 mM)
- Caffeine (typical range: 0-10 mM)
- MSG (typical range: 0-20 mM)

**Tips:**
- Start with 2 ingredients for simpler experiments
- Use physiologically relevant ranges
- Refer to published literature for typical concentrations

**Example:**
```
Ingredient 1: Sugar (0 - 100 mM)
Ingredient 2: Salt (0 - 50 mM)
```

### Step 2.5: Configure Loading Screen (Optional)

The loading screen appears between experiment cycles while the robot prepares samples.

**Configuration options:**

1. **Message** - Instructions for participants (e.g., "Rinse your mouth with water")
2. **Duration** - How long to display the screen (1-60 seconds, default: 5)
3. **Show Progress** - Display animated progress bar (default: yes)
4. **Show Cycle Info** - Display cycle number like "Cycle 3 of 10" (default: yes)
5. **Message Size** - Font size: normal, large, or extra_large (default: large)

**When to customize:**
- **Longer duration** - If robot preparation takes more time
- **Custom message** - For specific instructions (e.g., "Drink water", "Wait quietly")
- **Extra large text** - For participants with visual impairments
- **Hide progress bar** - If you prefer a simpler display

**Example configurations:**

For a quick experiment with minimal wait:
```json
{
  "loading_screen": {
    "message": "Next sample coming soon...",
    "duration_seconds": 3
  }
}
```

For participants who need more time:
```json
{
  "loading_screen": {
    "message": "Please rinse your mouth thoroughly with water and wait for the next sample.",
    "duration_seconds": 10,
    "message_size": "extra_large"
  }
}
```

**Note:** If you don't configure this section, sensible defaults will be used.

---

### Step 3: Design Sample Selection Schedule

This is where you define **when to use each selection mode**.

#### Understanding Selection Modes

**1. Predetermined Mode**
- You specify exact concentrations for each cycle
- Use for: Calibration, validation samples, known references

**2. User Selected Mode**
- Participant manually chooses concentrations via UI
- Use for: Exploratory experiments, giving subjects control

**3. BO Selected Mode**
- Bayesian Optimization suggests next sample
- Use for: Adaptive optimization, preference learning

#### Creating the Schedule

1. Click **"Add Block"** to add a cycle range
2. For each block, specify:
   - **Start Cycle:** First cycle number (e.g., 1)
   - **End Cycle:** Last cycle number (e.g., 5)
   - **Mode:** Selection mode (predetermined/user/BO)

3. For **Predetermined Mode:**
   - Fill in the sample table with exact concentrations
   - One row per cycle

4. For **BO Mode:**
   - Configure acquisition function (default: UCB)
   - Set `allow_override` if subjects can reject suggestions

**Example Schedule:**

| Cycles | Mode | Purpose |
|--------|------|---------|
| 1-2 | Predetermined | Calibration samples |
| 3-5 | User Selected | Subject explores space |
| 6-20 | BO Selected | Adaptive optimization |

**Visual Timeline:**
```
[1-2: Predetermined] [3-5: User] [6-20: BO]
```

#### Tips for Schedule Design:
- Start with 2-3 predetermined samples for calibration
- Use 3-5 user-selected cycles for initial exploration
- Switch to BO after subjects have some experience
- Typical total: 15-25 cycles

### Step 4: Configure Questionnaire

Select which questionnaire participants will answer after each sample:

- **hedonic_continuous** - 9-point hedonic scale with slider (recommended)
- **hedonic_discrete** - 9-point hedonic scale with buttons
- **intensity** - Intensity rating
- **liking** - Simple liking scale

**Recommendation:** Use `hedonic_continuous` for most preference studies.

### Step 5: Configure Bayesian Optimization (if using BO mode)

If your schedule includes `bo_selected` mode, configure BO settings:

1. **Acquisition Function:** How BO balances exploration/exploitation
   - **UCB** (recommended): Good balance, use `kappa=2.5`
   - **EI**: For aggressive optimization, use `xi=0.01`
   - **POI**: For conservative optimization

2. **Parameters:**
   - `kappa` (for UCB): Higher = more exploration (default: 2.5)
   - `xi` (for EI/POI): Higher = more exploration (default: 0.01)

**Default Settings (Good Starting Point):**
```json
{
  "acquisition_function": "ucb",
  "kernel": "rbf",
  "params": {
    "kappa": 2.5
  }
}
```

### Step 6: Set Stopping Criteria

Define when the experiment should end:

- **Max Cycles:** Maximum number of cycles (e.g., 20)
- **Min Cycles:** Minimum before allowing early stop (e.g., 10)

**Example:**
```
Max Cycles: 20
Min Cycles: 10
```

### Step 7: Save Protocol

1. Click **"Apply Changes"** to validate the schedule
2. Check for validation errors (shown in red)
3. Fix any errors
4. Click **"Save Protocol"**
5. Protocol is now saved to the database!

---

## Managing Protocols

### Viewing Existing Protocols

1. Go to **Browse Protocols** tab
2. Use search box to find protocols by name
3. Filter by tags using tag selector
4. Click protocol name to preview

### Editing a Protocol

1. Find protocol in Browse tab
2. Click **"Edit"** button
3. Make changes
4. Click **"Save Protocol"**

**Note:** Editing creates a new version. Use `increment_protocol_version()` API for formal versioning.

### Archiving Protocols

To hide protocols without deleting them:

1. Find protocol in list
2. Click **"Archive"** button
3. To view archived protocols, check "Show Archived"

### Deleting Protocols

**⚠️ Warning:** Deletion is permanent!

1. Find protocol in list
2. Click **"Delete"** button
3. Confirm deletion

**Soft Delete:** Use Archive instead for reversibility

### Exporting/Importing Protocols

#### Exporting
1. Preview the protocol
2. Click **"Export to File"** button
3. Save JSON file to disk
4. Share file with colleagues

#### Importing
1. Click **"Import Protocol"** button
2. Select JSON file
3. Protocol is imported with new ID
4. Review and save

---

## Running Experiments with Protocols

### Starting a Session with a Protocol

1. **Create Session** (Moderator View)
2. Select **"Use Protocol"**
3. Choose protocol from dropdown
4. Click **"Start Session"**
5. Give session code to participant

### What Happens During the Session

The protocol controls:
- ✅ Which ingredients are used (from protocol)
- ✅ Concentration ranges (from protocol)
- ✅ Sample selection mode per cycle (from protocol)
- ✅ Questionnaire type (from protocol)
- ✅ When to stop (from protocol)

**Cycle 1-2 (Predetermined):**
- System automatically loads predetermined sample
- Participant tastes and answers questionnaire
- No sample selection UI shown

**Cycle 3-5 (User Selected):**
- Participant sees grid or sliders
- They choose next sample concentrations
- Participant tastes and answers questionnaire

**Cycle 6+ (BO Selected):**
- BO suggests next sample based on previous responses
- Suggestion shown to participant
- If `allow_override=true`, participant can reject and choose manually
- Participant tastes and answers questionnaire

### Monitoring Session Progress

1. Open **Moderator View**
2. Select session
3. View:
   - Current cycle number
   - Current phase (loading, questionnaire, selection)
   - Mode being used
   - Samples collected so far

---

## Best Practices

### Protocol Design

#### Start Simple
- ✅ Begin with 2 ingredients
- ✅ Use 15-20 cycles total
- ✅ Start with predetermined samples for calibration
- ❌ Don't jump straight to 4-5 ingredients

#### Calibration Samples
- ✅ Include 2-3 predetermined samples at start
- ✅ Use corner points (min/max combinations)
- ✅ Include a mid-range sample
- ❌ Don't skip calibration

#### Mode Selection
- ✅ Predetermined → User → BO is a good flow
- ✅ Let subjects explore before using BO
- ✅ Use BO for at least 10-15 cycles for good results
- ❌ Don't use BO immediately (needs initial data)

#### Naming and Documentation
- ✅ Use descriptive names with version numbers
- ✅ Document the experiment's purpose in description
- ✅ Add tags for easy searching
- ❌ Don't use generic names like "Test1"

### BO Configuration

#### For Preference Learning:
```json
{
  "acquisition_function": "ucb",
  "params": {"kappa": 2.5}
}
```

#### For Quick Optimization:
```json
{
  "acquisition_function": "ei",
  "params": {"xi": 0.01}
}
```

#### For Exploration-Heavy Studies:
```json
{
  "acquisition_function": "ucb",
  "params": {"kappa": 5.0}
}
```

### Stopping Criteria

**Typical Settings:**
- **Short study:** max_cycles=15, min_cycles=10
- **Standard study:** max_cycles=20, min_cycles=10
- **Thorough study:** max_cycles=30, min_cycles=15

---

## Troubleshooting

### Common Issues

#### "Protocol is invalid: Missing required field"

**Problem:** Protocol is missing a required field

**Solution:**
- Check that you have: name, version, ingredients, sample_selection_schedule, questionnaire_type
- All fields must be filled in before saving

#### "Cycle ranges overlap"

**Problem:** Two schedule blocks have overlapping cycle numbers

**Solution:**
- Check cycle ranges: Block 1 ends before Block 2 starts
- Example: ✅ [1-5], [6-10]  ❌ [1-5], [4-10]

#### "Predetermined mode requires predetermined_samples"

**Problem:** You selected predetermined mode but didn't specify samples

**Solution:**
- Add samples in the table for each cycle in the range
- Make sure every cycle has a concentration specified

####  "BO mode requires bayesian_optimization config"

**Problem:** Using `bo_selected` mode without BO configuration

**Solution:**
- Go to Advanced Settings
- Fill in Bayesian Optimization section
- Set acquisition function and parameters

#### Protocol not showing in list

**Problem:** Protocol might be archived

**Solution:**
- Check "Show Archived" checkbox in Browse tab
- Look for protocol in archived section

#### BO not working during session

**Problem:** Not enough samples collected yet

**Solution:**
- BO needs 3-5 samples before it can make good suggestions
- Make sure you have predetermined or user-selected cycles first

---

## Example Workflows

### Workflow 1: Simple Two-Ingredient Study

**Goal:** Find optimal sugar-salt blend

1. **Create Protocol:**
   - Name: "Sugar-Salt Preference Study v1.0"
   - Ingredients: Sugar (0-100), Salt (0-50)

2. **Schedule:**
   - Cycles 1-2: Predetermined (corners of space)
   - Cycles 3-5: User Selected
   - Cycles 6-20: BO Selected (UCB, kappa=2.5)

3. **Settings:**
   - Questionnaire: hedonic_continuous
   - Max Cycles: 20

4. **Run 10 participants** using this protocol
5. **Analyze** to see convergence across subjects

### Workflow 2: Multi-Stage Exploration

**Goal:** Let subjects explore, then optimize

1. **Create Protocol:**
   - Name: "Exploration then Optimization"
   - Ingredients: Sugar, Salt, Citric Acid

2. **Schedule:**
   - Cycles 1-10: User Selected (free exploration)
   - Cycles 11-25: BO Selected (optimize based on exploration)

3. **Settings:**
   - Questionnaire: hedonic_continuous
   - Max Cycles: 25
   - Min Cycles: 15

4. **Analyze** exploration patterns vs BO optima

---

## Getting Help

### Resources

- **Protocol Schema Reference:** [protocol_schema.md](protocol_schema.md)
- **API Documentation:** [week_3-4_api_reference.md](week_3-4_api_reference.md)
- **Example Protocols:** `tests/test_protocol_mixed_mode.json`

### Support

- Check validation error messages (they're usually specific)
- Review example protocols for correct format
- Contact development team with protocol JSON if issues persist

---

**Happy experimenting! 🧪**
