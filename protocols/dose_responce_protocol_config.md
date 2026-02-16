# Protocol Configuration Template

Fill in each section below. Delete any optional sections you don't need.
Use the examples in comments as guidance.

---

## 1. Basic Information

- **Name:** Sucrose Dose Response Curve
- **Version:** 1.0
- **Description:** Simple experiment with predetermined samples to showcase RoboTaste abilities
- **Tags:** dose-response, sucrose, predetermined_randomized, latin_square, pilot, pumps

---

## 2. Ingredients

<!-- List each ingredient. Available: Sugar, Salt, Citric Acid, Caffeine, MSG, Water -->
<!-- Water can be marked as diluent if used to fill remaining volume -->

| Ingredient | Min (mM) | Max (mM) | Stock Concentration (mM) | Is Diluent? |
|------------|----------|----------|--------------------------|-------------|
| Sugar      |     0    |   100    |           200            |     No      |
| Water      |     0    |     0    |           0              |     Yes     |

---

## 3. Pump Configuration

- **Enabled:** yes

<!-- If pumps are disabled, skip the rest of this section -->

- **Serial Port:** /dev/cu.PL2303G-USBtoUART120
- **Baud Rate:** 19200
- **Total Sample Volume (mL):** 10
- **Dispensing Rate (uL/min):** 90000
- **Simultaneous Dispensing:** yes
- **Burst Mode:** yes

### Pumps

| Address | Ingredient | Syringe Diameter (mm) | Max Rate (uL/min) | Stock Conc (mM) | Description |
|---------|------------|-----------------------|-------------------|------------------|-------------|
| 0       |     Water  |        29.00          |     90000         |       0          |             |
| 1       |     Sugar  |        29.00          |     90000         |       200        |             |

---

## 4. Sample Selection Schedule

<!-- Define what happens at each cycle range -->
<!-- Modes: predetermined, predetermined_randomized, user_selected, bo_selected -->

### Block 1

- **Cycles:** 1-6
- **Mode:** predetermined_randomized

-**Sample Bank**
| Sample ID | Label       | Ingredient1 | Ingredient2 |
|-----------|-------------|-------------|-------------|
| A         | No Sugar       |             |      0.0    |
| B         | Very Low Sugar |             |      20.0   |
| C         | Low Sugar      |             |      40.0   |
| D         | Medium Sugar   |             |      60.0   |
| E         | High Sugar     |             |      80.0   |
| F         | Very High Sugar|             |      100.0  |


- Design Type: latin_square
- Prevent Consecutive Repeats: yes
- Ensure All Used Before Repeat: yes

## 5. Questionnaire

<!-- Define the questions subjects answer after tasting each sample -->

- **Questionnaire Name:** 
- **Description:**

### Questions

#### Question 1

- **ID:** sweetness_intensity
- **Type:** slider
- **Label:** How sweet was the sample you just tasted?
- **Help Text:** <!-- optional -->
- **Min:** 1
- **Max:** 9
- **Default:** 5
- **Step:** 0.01
- **Required:** yes
- **Display Type:** slider_continuous
- **Scale Labels:** <!-- list anchor points -->
  - 1: Not Sweet at All
  - 3: Light Sweetness
  - 5: Medium Sweetness
  - 7: High Sweetness
  - 9: Intense Sweetness



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

- **Enabled:** / no
- **Acquisition Function:** 
- **Kernel:** rbf
- **Kappa:** <!-- for UCB, default 2.5 -->
- **Xi:** <!-- for EI/POI, default 0.01 -->

---

## 7. Stopping Criteria

- **Max Cycles:**
- **Min Cycles:**

---

## 8. Loading Screen

- **Message:** Please rinse your mouth with water before and after every tasting./r/nOnce the robot is done preparing your sample, take the cup and stirr the sample lighly with the provided wooden stirrer and *place a clean cup under the spout*.
- **Duration (seconds):** 12
- **Show Progress Bar:** yes
- **Show Cycle Info:** yes
- **Message Size:** large

---

## 9. Phase Sequence

<!-- Choose one or customize -->

- [ ] **Default:** registration → instructions → experiment loop → completion
- [V] **With consent:** consent → registration → instructions → experiment loop → completion
- [ ] **Custom** (describe below):

---

## 10. Additional Settings (optional)

- **Track Trajectory:** no
- **Track Interaction Times:** no
- **Collect Demographics:** yes
- **Custom Metadata:** <!-- any key-value pairs -->

## 11. Consent Form

- **Title:** Informed Consent
- **Text:**

> Dear Participant,
>
> Welcome to the RoboTaste pilot experiment.
> Participation will take approximately 5 minutes of your time. There are no right or wrong answers and we are only interested in your opinion.
> Participation in the study will not entitle you to any compensation and carries no risk. Your answers are confidential, and we will not include any information that would identify you in any type of public reporting. Only researchers will have access to the study data.
> Participation in the study is voluntary. You are free to choose not to participate in the study and to stop it at any time without providing a reason and without your rights being violated.
>
> In this study you will be asked to taste 6 samples and assess their sweetness on a scale from 1 (not sweet) to 9 (intensly sweet)
>
> If you have any questions, please contact: Prof. Masha Niv (masha.niv@mail.huji.ac.il) or Alon Nissan (alon.nissan1@mail.huji.ac.il)

- **Checkbox Label:** I have read the above information and received answers to my questions.
- **Required:** yes