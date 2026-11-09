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
7. [Exported Data](#exported-data)
8. [Troubleshooting](#troubleshooting)

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
- Questionnaire (scale library, question editor, optimization target)
- Advanced Settings (BO config)

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

### Step 2.5: Configure Instructions Screen (Optional)

The instructions screen is shown to participants before the experiment begins. You can customize the text, confirmation checkbox, and button label.

**Configuration options:**

1. **Title** - Heading displayed at the top (default: "Instructions")
2. **Text** - Main body of instructions (supports markdown: bold, lists, etc.)
3. **Confirm Label** - Checkbox text participants must agree to (default: "I understand the instructions.")
4. **Button Label** - Text on the proceed button (default: "Start Tasting")

**Example:**
```json
{
  "instructions_screen": {
    "title": "Instructions",
    "text": "**Welcome!**\n\nYou will taste 6 samples and rate their sweetness.\n\n1. Taste the sample.\n2. Rate on the scale.\n3. Rinse your mouth with water.",
    "confirm_label": "I have read and understand the instructions.",
    "button_label": "Begin Experiment"
  }
}
```

**Note:** If you don't configure this section, a generic default instructions screen will be shown.

### Step 2.6: Configure Loading Screen (Optional)

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

### Step 2.7: Configure Pumps (Optional)

If your experiment uses automated pumps, add a `pump_config` block to the
protocol JSON. Each pump entry can specify its own `volume_unit`.

**Per-pump volume units:**
- `ML` uses milliliters for volume commands.
- `UL` uses microliters (max 9999).

See `docs/pump_config.md` for the full pump configuration fields and examples.

#### Pump Rate Limits

The NE-4000 pump has **maximum flow rate limits** based on syringe diameter.
Exceeding these limits will cause an Out-Of-Range (OOR) error and pump failure.

**Maximum Flow Rates by Syringe Size (B-D Syringes):**

| Syringe Size | Diameter (mm) | Max Rate (mL/min) | Max Rate (µL/min) |
|-------------|---------------|-------------------|-------------------|
| 1 mL        | 4.699         | 3.135             | 3,135             |
| 3 mL        | 8.585         | 10.46             | 10,460            |
| 5 mL        | 11.99         | 20.41             | 20,410            |
| 10 mL       | 14.43         | 29.56             | 29,560            |
| 20 mL       | 19.05         | 51.53             | 51,530            |
| 30 mL       | 21.59         | 66.19             | 66,190            |
| 60 mL       | 26.59         | 100.3             | 100,300           |

**Example:** If using 20mL syringes (19.05mm diameter), set `dispensing_rate_ul_min` to **51000 or less**.

⚠️ The protocol validator will **reject protocols** where the rate exceeds the limit for any configured syringe.

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
   - For automated BO flow, set `auto_accept_suggestion=true` and `allow_override=false`
   - Only set `allow_override=true` when you intentionally want manual override UI

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

The questionnaire is what participants answer after each sample. In the protocol
wizard (Step 4) you can:

1. **Start from a template** — e.g. *gLMS Intensity*, *gVAS Intensity*, *VAS Liking*,
   *9-point Hedonic*, *LHS Liking*, *Liking + CATA*, or the classic 1–9 sliders.
   Templates replace the current questions; everything stays editable.
2. **Add questions from the scale library** (*+ Add Question*). Each scale shows a
   live preview, its intended use and citation. Scales marked **anchors unverified**
   (LMS, LAM, LHS) use label positions that should be checked against the original
   paper before a study.
3. **Edit any question**: text, help text, required, and type-specific settings —
   anchor positions and labels (line scales), options and icons (category scales,
   CATA, ranking), orientation, whether the line starts without a marker, whether the
   number is shown, CATA min/max selections, option randomization, magnitude-estimation
   modulus. A question built from a library scale shows *Based on gLMS v1.0*; if you
   change its anchors/options it is marked **Modified** and can be reset.
4. **Questionnaire settings**: the page title subjects see, and the display mode
   (*all questions on one page* or *one question at a time*).
5. **Optimization target** (only needed if the schedule has BO cycles): pick a numeric
   question (or a composite formula) and a transform. *Scale default* uses the scale's
   recommended transform — e.g. `log10(x + 1)` for gLMS and magnitude estimation. For
   JAR questions use `ideal_point` with the "just about right" value to optimize toward
   the ideal rather than "more".

Subjects never see a pre-placed marker or a number on line scales by default, and
must answer every required question before continuing.

#### Choosing a scale

| Scale | Type | Use it for | Notes |
|---|---|---|---|
| **VAS** | horizontal line, 0–100, end labels only | Within-subject intensity or liking | Edit the end labels to your attribute (e.g. *Not sweet at all* / *Extremely sweet*). Stone et al. 1974 |
| **gVAS** | line, *no sensation* → *strongest imaginable sensation of any kind* | Comparing intensity **between groups** (e.g. taster status) | No intermediate labels → no clustering at labels. Hayes et al. 2013 |
| **gLMS** | vertical line, 0 / 1.4 / 6 / 17 / 35 / 53 / 100 | Intensity with cross-group validity (supertasters, clinical groups) | Ratio-like; log-transformed by default. Tell subjects to rate relative to *all* sensations. Bartoshuk et al. 2004 |
| **LMS** | vertical line, oral top anchor | Replicating older LMS studies | Prefer gLMS for group comparisons. Anchors unverified. Green et al. 1993 |
| **Hedonic VAS** | horizontal line, dislike → like extremely | Within-subject liking | |
| **Hedonic gLMS** | vertical bipolar line, −100…+100 | Liking compared between groups | Kalva et al. 2014 |
| **LHS** | vertical bipolar line, −100…+100 | Ratio-level liking with little ceiling effect | Anchors unverified. Lim, Wood & Green 2009 |
| **LAM** | vertical line, 0–100 | Liking of well-liked products where the 9-point scale hits the ceiling | Anchors unverified. Schutz & Cardello 2001 |
| **9-point hedonic** | 9 labelled categories | Consumer liking; comparable with decades of data | Peryam & Pilgrim 1957 |
| **Likert (5/7)**, **5-point intensity** | labelled categories | Attitudes, statements, quick intensity screening | Ordinal data |
| **JAR (5-point)** | bipolar categories, 3 = just about right | Diagnosing whether an attribute is too weak/strong | Use `ideal_point` transform to optimize toward JAR |
| **Facial scales (3/5/7)** | emoji faces | Children (~3, ~4, 5+ years) | Chen et al. 1996 |
| **Magnitude estimation** | free number (optional fixed modulus) | Ratio-scaled intensity with trained panels | Log-transformed by default. Stevens 1956 |
| **CATA** | check-all-that-apply list | Qualitative profile next to a liking question | Option order randomized per subject. Ares & Jaeger 2013 |
| **Ranking** | tap items in order | Preference order among named options | |
| **Classic 1–9 slider** | slider with visible value | Backwards compatibility with older protocols | Starts at a default position and shows the number (not recommended for new psychophysics studies) |

The full anchor tables live in `robotaste/config/scales.py` and are served at
`GET /api/protocols/scale-presets`. See `docs/protocol_schema.md` for the JSON format.

Example protocols: `protocols/glms_sweetness_example.json` (gLMS + 9-point hedonic +
CATA, hand-served, one question at a time) and `protocols/vas_liking_bo_example.json`
(hedonic VAS liking optimized with BO, plus a JAR question).

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
- ✅ Questionnaire (questions and scales from the protocol, frozen for the session)
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
- With `auto_accept_suggestion=true`, sample selection is automatic (same UX as predetermined cycles)
- If `auto_accept_suggestion=false` and `allow_override=true`, participant can reject and choose manually
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

## Exported Data

**Analysis → Export samples** (`GET /api/analysis/export/samples`) downloads one row per
tasted sample. Each session's answers are expanded using that session's questionnaire:

| Column | Meaning |
|---|---|
| `session_id`, `participant_name`, `cycle_number`, `selection_mode` | Which subject/cycle, and how the sample was chosen |
| `<ingredient>_concentration`, `sample_temperature` | What was tasted |
| `<question>_rating` | Single-value answers (line scales, category scales, sliders, magnitude estimation, dropdown, text) |
| `<question>__<option>` | CATA: 1 if the option was ticked, 0 otherwise (every option gets a column) |
| `<question>__n_selected` | CATA: number of options ticked |
| `<question>__rank__<option>` | Ranking: rank given to the option (1 = most preferred) |
| `<question>__interacted` | 1 if the subject touched the question (0 = left untouched) |
| `<question>__rt_ms` | Milliseconds from the question appearing to the subject's last change |
| `<question>__n_changes` | How many times the subject changed the answer |

The session CSV export uses the same columns with a `q_` prefix. In the dose-response
dashboard, CATA options appear as response variables whose mean is the **proportion of
subjects selecting the attribute** at each concentration, and a *Log scale (y)* toggle is
available for gLMS / magnitude-estimation data.

---

## Troubleshooting

### Common Issues

#### "Protocol is invalid: Missing required field"

**Problem:** Protocol is missing a required field

**Solution:**
- Check that you have: name, version, ingredients, sample_selection_schedule, and a questionnaire with at least one question
- If the schedule uses BO-selected cycles, the questionnaire also needs an optimization target that is a numeric question
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

#### Pump OOR (Out Of Range) Error

**Problem:** Pump shows OOR error or fails to dispense

**Solution:**
- The dispensing rate exceeds the maximum for your syringe size
- Check the [Pump Rate Limits](#pump-rate-limits) table above
- Reduce `dispensing_rate_ul_min` in your protocol's pump_config
- For 20mL syringes (19.05mm): max 51,530 µL/min
- For 30mL syringes (21.59mm): max 66,190 µL/min

**Example fix:**
```json
"pump_config": {
  "dispensing_rate_ul_min": 50000,  // Reduced from 66300
  ...
}
```

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
   - Questionnaire: 9-point hedonic (or hedonic VAS) liking as the optimization target
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
   - Questionnaire: hedonic VAS liking (target) + CATA basic tastes
   - Max Cycles: 25
   - Min Cycles: 15

4. **Analyze** exploration patterns vs BO optima

---

## Getting Help

### Resources

- **Protocol Schema Reference:** [protocol_schema.md](protocol_schema.md)
- **Workflow Guide:** [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md)
- **Example Protocols:** `protocols/test_protocol_mixed_mode_new_format.json`

### Support

- Check validation error messages (they're usually specific)
- Review example protocols for correct format
- Contact development team with protocol JSON if issues persist

---

**Happy experimenting! 🧪**
