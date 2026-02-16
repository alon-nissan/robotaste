# Protocol Configuration Template

Fill in each section below. Delete any optional sections you don't need.
Use the examples in comments as guidance.

---

## 1. Basic Information

- **Name:**
- **Version:** 1.0
- **Description:**
- **Tags:** <!-- e.g., calibration, sugar, preference-learning, no_pumps -->

---

## 2. Ingredients

<!-- List each ingredient. Available: Sugar, Salt, Citric Acid, Caffeine, MSG, Water -->
<!-- Water can be marked as diluent if used to fill remaining volume -->

| Ingredient | Min (mM) | Max (mM) | Stock Concentration (mM) | Is Diluent? |
|------------|----------|----------|--------------------------|-------------|
|            |          |          |                          |             |
|            |          |          |                          |             |

---

## 3. Pump Configuration

- **Enabled:** yes / no

<!-- If pumps are disabled, skip the rest of this section -->

- **Serial Port:** <!-- e.g., /dev/cu.PL2303G-USBtoUART120 -->
- **Baud Rate:** 19200
- **Total Sample Volume (mL):**
- **Dispensing Rate (uL/min):**
- **Simultaneous Dispensing:** yes / no
- **Burst Mode:** yes / no

### Pumps

| Address | Ingredient | Syringe Diameter (mm) | Max Rate (uL/min) | Stock Conc (mM) | Description |
|---------|------------|-----------------------|--------------------|------------------|-------------|
| 0       |            |                       |                    |                  |             |
| 1       |            |                       |                    |                  |             |

---

## 4. Sample Selection Schedule

<!-- Define what happens at each cycle range -->
<!-- Modes: predetermined, predetermined_randomized, user_selected, bo_selected -->

### Block 1

- **Cycles:** <!-- e.g., 1-4 -->
- **Mode:** <!-- predetermined / predetermined_randomized / user_selected / bo_selected -->

<!-- FOR predetermined: list exact concentrations per cycle -->
<!--
| Cycle | Ingredient1 | Ingredient2 |
|-------|-------------|-------------|
| 1     | 0.0         | 10.0        |
| 2     | 25.0        | 10.0        |
-->

<!-- FOR predetermined_randomized: define sample bank -->
<!--
| Sample ID | Label       | Ingredient1 | Ingredient2 |
|-----------|-------------|-------------|-------------|
| A         | No Sugar    | 0.0         |             |
| B         | Low Sugar   | 25.0        |             |

- Design Type: latin_square / random
- Prevent Consecutive Repeats: yes / no
- Ensure All Used Before Repeat: yes / no
-->

<!-- FOR bo_selected: -->
<!--
- Allow Subject Override: yes / no
-->

### Block 2 (copy this section for additional blocks)

- **Cycles:**
- **Mode:**

---

## 5. Questionnaire

<!-- Define the questions subjects answer after tasting each sample -->

- **Questionnaire Name:**
- **Description:**

### Questions

#### Question 1

- **ID:** <!-- e.g., overall_liking, sweetness_intensity -->
- **Type:** slider / dropdown
- **Label:** <!-- e.g., "How much do you like this sample?" -->
- **Help Text:** <!-- optional -->
- **Min:** <!-- e.g., 1 -->
- **Max:** <!-- e.g., 9 -->
- **Default:** <!-- e.g., 5 -->
- **Step:** <!-- e.g., 0.01 for continuous, 1 for discrete -->
- **Required:** yes / no
- **Display Type:** slider_continuous / pillboxes
- **Scale Labels:** <!-- list anchor points -->
  - 1:
  - 5:
  - 9:

#### Question 2 (copy for more questions)

- **ID:**
- **Type:**
- **Label:**
- **Min:**
- **Max:**
- **Default:**
- **Step:**
- **Required:**
- **Display Type:**
- **Scale Labels:**

### Bayesian Target

<!-- Which question does BO optimize? -->

- **Target Variable:** <!-- question ID from above -->
- **Higher is Better:** yes / no
- **Transform:** identity / log / normalize
- **Expected Range:** <!-- e.g., [1, 9] -->
- **Optimal Threshold:** <!-- e.g., 7.0 -->
- **Description:** <!-- e.g., "Maximize overall liking score" -->

<!-- For composite targets using multiple questions: -->
<!-- - Formula: e.g., "0.7 * liking + 0.3 * healthiness" -->

---

## 6. Bayesian Optimization

<!-- Skip if not using bo_selected mode -->

- **Enabled:** yes / no
- **Acquisition Function:** ucb / ei / poi
- **Kernel:** rbf
- **Kappa:** <!-- for UCB, default 2.5 -->
- **Xi:** <!-- for EI/POI, default 0.01 -->

---

## 7. Stopping Criteria

- **Max Cycles:**
- **Min Cycles:**

---

## 8. Loading Screen

- **Message:** <!-- e.g., "Please rinse your mouth with water" -->
- **Duration (seconds):** <!-- default 5 -->
- **Show Progress Bar:** yes / no
- **Show Cycle Info:** yes / no
- **Message Size:** normal / large / extra_large

---

## 9. Phase Sequence

<!-- Choose one or customize -->

- [ ] **Default:** registration → instructions → experiment loop → completion
- [ ] **With consent:** consent → registration → instructions → experiment loop → completion
- [ ] **Custom** (describe below):

---

## 10. Additional Settings (optional)

- **Track Trajectory:** yes / no
- **Track Interaction Times:** yes / no
- **Collect Demographics:** yes / no
- **Custom Metadata:** <!-- any key-value pairs -->
