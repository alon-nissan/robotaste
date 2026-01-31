# Conveyor Belt Integration Guide

This guide walks you through setting up the conveyor belt hardware with RoboTaste. It's written for someone who may not have much electronics experience but wants to understand what they're doing and why.

**What you'll accomplish:**
1. Wire up the Arduino and stepper motor
2. Upload firmware to the Arduino
3. Test the hardware manually
4. Configure RoboTaste to use the belt
5. Run a complete test cycle

**Time estimate:** 2-4 hours for first-time setup

---

## Table of Contents
1. [Understanding the System](#1-understanding-the-system)
2. [What You'll Need](#2-what-youll-need)
3. [Wiring the Hardware](#3-wiring-the-hardware)
4. [Setting Up the Arduino](#4-setting-up-the-arduino)
5. [Uploading the Firmware](#5-uploading-the-firmware)
6. [Testing the Hardware](#6-testing-the-hardware)
7. [Configuring RoboTaste](#7-configuring-robotaste)
8. [Running a Full Test](#8-running-a-full-test)
9. [Troubleshooting](#9-troubleshooting)
10. [Maintenance Tips](#10-maintenance-tips)

---

## 1. Understanding the System

Before diving into wiring, let's understand what we're building and why each piece matters.

### The Big Picture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CONVEYOR BELT SYSTEM                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Computer                    Arduino                  Belt Motor   │
│  ┌─────────┐    USB Cable    ┌─────────┐   Wires    ┌───────────┐  │
│  │RoboTaste│ ═══════════════>│ Arduino │ ──────────>│  Stepper  │  │
│  │   App   │   Serial Cmds   │  Uno    │   Driver   │   Motor   │  │
│  └─────────┘                 └─────────┘            └───────────┘  │
│       │                           │                       │        │
│       │                           │                       │        │
│       ▼                           ▼                       ▼        │
│  Sends commands            Interprets commands      Moves the belt │
│  like "MOVE_TO_SPOUT"      and controls motor       to position    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Why Each Component?

| Component | Purpose | Why We Need It |
|-----------|---------|----------------|
| **Arduino** | The "brain" that controls the motor | Computers can't directly control motors - Arduino translates software commands into electrical signals |
| **Stepper Motor** | Moves the belt precisely | Unlike regular motors, steppers move in exact increments (steps), so we know exactly where the belt is |
| **Stepper Driver** | Amplifies Arduino signals | Arduino outputs low power (5V); motors need higher power (12-24V). The driver bridges this gap |
| **Power Supply** | Powers the motor | Motors need more current than USB can provide |

### How Position Tracking Works

Since you're using **step counting from home position**, here's how it works:

1. When the system starts, the belt moves to a known "home" position (usually one end)
2. The Arduino counts every step the motor takes from home
3. To go to the spout, the Arduino moves a specific number of steps
4. To go to display, it moves a different number of steps
5. The Arduino always knows the position because it tracks every step

**Important:** If power is lost or the belt slips, the step count becomes wrong. That's why we "home" the belt at startup.

---

## 2. What You'll Need

### Hardware Checklist

**Electronics:**
- [ ] Arduino Uno (recommended) or Arduino Mega
- [ ] USB cable (Type A to Type B, like a printer cable)
- [ ] Stepper motor driver (A4988 or DRV8825 recommended)
- [ ] Stepper motor (NEMA 17 is common)
- [ ] 12V or 24V power supply (check your motor's voltage)
- [ ] Power supply connector/barrel jack

**Mechanical:**
- [ ] Conveyor belt assembly (belt, pulleys, frame)
- [ ] Motor mounting bracket
- [ ] Limit switch (optional but recommended for homing)

**Tools:**
- [ ] Small Phillips screwdriver
- [ ] Wire strippers
- [ ] Multimeter (helpful but not required)
- [ ] Soldering iron (if wires need connecting)

**Software (we'll install these):**
- [ ] Arduino IDE (free download)

### Before You Start

1. **Clear your workspace** - You'll need room to spread out components
2. **Have good lighting** - Small wire colors can be hard to distinguish
3. **Keep a notebook handy** - Write down any measurements or settings you use
4. **Take photos as you go** - Helps if you need to troubleshoot later

---

## 3. Wiring the Hardware

This is the most important section. Take your time and double-check connections.

### Safety First! ⚠️

- **Never connect/disconnect wires while power is on**
- **Keep 12V/24V motor power separate from 5V Arduino power**
- **If something smells like burning, disconnect power immediately**

### Step 3.1: Understand the Stepper Driver

The stepper driver (A4988 or DRV8825) is a small board that sits between the Arduino and motor. Here's what the pins do:

```
         A4988 Stepper Driver
    ┌─────────────────────────────┐
    │  VMOT  GND  2B  2A  1A  1B  │  ← Motor side (top)
    │   ●     ●   ●   ●   ●   ●  │
    │                             │
    │                             │
    │   ●     ●   ●   ●   ●   ●  │
    │  GND   VDD  STP DIR  SLP RST│  ← Arduino side (bottom)
    └─────────────────────────────┘
```

**Pin meanings:**
- **VMOT** = Motor power (12V or 24V from power supply)
- **GND** = Ground (0V reference, shared between motor power and Arduino)
- **2B, 2A, 1A, 1B** = Motor coil wires (4 wires from stepper motor)
- **VDD** = Logic power (5V from Arduino)
- **STP (STEP)** = Each pulse moves motor one step
- **DIR** = Direction (HIGH = one way, LOW = other way)
- **SLP (SLEEP)** = Low power mode (we'll tie this HIGH)
- **RST (RESET)** = Reset driver (we'll tie this HIGH)

### Step 3.2: Wire the Arduino to Driver

Connect these pins with jumper wires:

| Arduino Pin | Driver Pin | Purpose |
|-------------|------------|---------|
| 5V | VDD | Powers the driver logic |
| GND | GND | Common ground |
| Digital Pin 2 | STEP | Sends step pulses |
| Digital Pin 3 | DIR | Controls direction |
| 5V | SLP | Keeps driver awake (tie to VDD) |
| 5V | RST | Prevents random resets (tie to VDD) |

**Wiring diagram:**

```
    Arduino Uno                    A4988 Driver
    ┌──────────┐                  ┌──────────────┐
    │      5V  │──────┬──────────>│VDD           │
    │          │      │           │              │
    │          │      ├──────────>│SLP           │
    │          │      │           │              │
    │          │      └──────────>│RST           │
    │          │                  │              │
    │     GND  │─────────────────>│GND           │
    │          │                  │              │
    │Digital 2 │─────────────────>│STEP          │
    │          │                  │              │
    │Digital 3 │─────────────────>│DIR           │
    └──────────┘                  └──────────────┘
```

### Step 3.3: Wire the Motor to Driver

Your stepper motor has 4 wires (or 6, with 2 center-taps you won't use). These connect in pairs called "coils."

**Finding the coil pairs:**
1. Set your multimeter to resistance (Ω) mode
2. Touch two wires together
3. If resistance is low (1-10Ω), those wires are a pair
4. If resistance is infinite (OL), try different combinations

**Common wire colors:**
- Pair 1: Red + Blue (or Black + Green)
- Pair 2: Yellow + White (or Red + Yellow)

**Connect to driver:**

| Motor Wire | Driver Pin |
|------------|------------|
| Coil 1, Wire A | 1A |
| Coil 1, Wire B | 1B |
| Coil 2, Wire A | 2A |
| Coil 2, Wire B | 2B |

**If the motor moves the wrong direction later, just swap 1A and 1B.**

### Step 3.4: Wire the Power Supply

**⚠️ IMPORTANT: Double-check polarity! Wrong polarity can destroy components.**

```
    12V Power Supply              A4988 Driver
    ┌──────────────┐             ┌──────────────┐
    │         +12V │────────────>│VMOT          │
    │              │             │              │
    │          GND │──────┬─────>│GND (motor)   │
    └──────────────┘      │      │              │
                          │      │              │
    Arduino Uno           │      │              │
    ┌──────────────┐      │      │              │
    │          GND │──────┴─────>│GND (logic)   │
    └──────────────┘             └──────────────┘
```

**Key point:** The GND from power supply and Arduino must be connected together. This is called a "common ground" and is required for the signals to work correctly.

### Step 3.5: Optional - Add a Limit Switch for Homing

A limit switch tells the Arduino when the belt has reached the home position.

```
    Limit Switch                   Arduino
    ┌──────────┐                  ┌──────────┐
    │  Common  │─────────────────>│GND       │
    │          │                  │          │
    │  NO      │─────────────────>│Digital 4 │
    └──────────┘                  └──────────┘
    
    NO = "Normally Open" - switch closes when pressed
```

The Arduino will use its internal pull-up resistor, so no external resistor is needed.

### Step 3.6: Final Wiring Checklist

Before powering on, verify:

- [ ] All connections are secure (give wires a gentle tug)
- [ ] No bare wires are touching each other
- [ ] Motor power (12V) is only connected to VMOT and GND on driver
- [ ] Arduino is only connected to logic pins (VDD, GND, STEP, DIR, SLP, RST)
- [ ] Common ground exists between power supply and Arduino
- [ ] Motor wires are connected to correct coil pairs (1A/1B, 2A/2B)

---

## 4. Setting Up the Arduino

### Step 4.1: Download Arduino IDE

1. Go to: https://www.arduino.cc/en/software
2. Download the version for your operating system (Mac, Windows, or Linux)
3. Install it like any other application

### Step 4.2: Connect Arduino to Computer

1. Plug the USB cable into the Arduino
2. Plug the other end into your computer
3. You should see a small LED on the Arduino light up (power indicator)

### Step 4.3: Configure Arduino IDE

1. Open Arduino IDE
2. Go to **Tools → Board** and select **Arduino Uno** (or your board type)
3. Go to **Tools → Port** and select the port that appeared
   - On Mac: looks like `/dev/cu.usbmodem14101` or `/dev/cu.usbserial-1420`
   - On Windows: looks like `COM3` or `COM4`
   - **Write this port name down - you'll need it later!**

**Can't find the port?**
- Try a different USB cable (some cables are charge-only)
- Try a different USB port
- On Windows, you may need to install drivers: https://www.arduino.cc/en/Guide/DriverInstallation

---

## 5. Uploading the Firmware

The "firmware" is the program that runs on the Arduino. It listens for commands from RoboTaste and controls the motor accordingly.

### Step 5.1: Create New Sketch

1. In Arduino IDE, go to **File → New Sketch**
2. Delete any existing code
3. Copy and paste the firmware code below

### Step 5.2: The Firmware Code

```cpp
/*
 * RoboTaste Conveyor Belt Controller
 * 
 * Commands (sent via Serial at 9600 baud):
 *   MOVE_TO_SPOUT    - Move cup to dispensing position
 *   MOVE_TO_DISPLAY  - Move cup to pickup position
 *   MIX <count>      - Oscillate belt for mixing (e.g., "MIX 5")
 *   STOP             - Emergency stop
 *   HOME             - Move to home position
 *   STATUS           - Report current position
 * 
 * Responses:
 *   OK               - Command completed successfully
 *   ERROR: <message> - Something went wrong
 *   POSITION: <pos>  - Current position (SPOUT, DISPLAY, MOVING, UNKNOWN)
 */

// ============== CONFIGURATION ==============
// Adjust these values to match your hardware!

// Pin assignments
const int STEP_PIN = 2;        // Pulse pin on driver
const int DIR_PIN = 3;         // Direction pin on driver
const int LIMIT_PIN = 4;       // Limit switch for homing (optional)
const bool USE_LIMIT_SWITCH = false;  // Set true if you have a limit switch

// Motor settings
const int STEPS_PER_REV = 200;       // Steps per revolution (most NEMA 17 = 200)
const int MICROSTEPPING = 16;        // Driver microstepping setting (1, 2, 4, 8, 16)
const int STEP_DELAY_US = 500;       // Microseconds between steps (lower = faster)

// Belt positions (in steps from home)
const long SPOUT_POSITION = 1000;    // Steps from home to spout
const long DISPLAY_POSITION = 2000;  // Steps from home to display
const long MIX_DISTANCE = 200;       // Steps to move during one mix oscillation

// ============== STATE VARIABLES ==============
long currentPosition = 0;            // Current position in steps
bool isHomed = false;                // Have we found home position?

// ============== SETUP ==============
void setup() {
  // Initialize serial communication
  Serial.begin(9600);
  Serial.setTimeout(1000);
  
  // Configure pins
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  
  if (USE_LIMIT_SWITCH) {
    pinMode(LIMIT_PIN, INPUT_PULLUP);  // Use internal pull-up resistor
  }
  
  // Start with motor idle
  digitalWrite(STEP_PIN, LOW);
  digitalWrite(DIR_PIN, LOW);
  
  Serial.println("READY: RoboTaste Belt Controller v1.0");
  
  // Auto-home on startup if limit switch is available
  if (USE_LIMIT_SWITCH) {
    homePosition();
  } else {
    // Assume current position is home
    currentPosition = 0;
    isHomed = true;
    Serial.println("INFO: No limit switch - assuming current position is home");
  }
}

// ============== MAIN LOOP ==============
void loop() {
  // Check for incoming commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();  // Remove whitespace
    command.toUpperCase();  // Make case-insensitive
    
    processCommand(command);
  }
}

// ============== COMMAND PROCESSING ==============
void processCommand(String command) {
  if (command == "MOVE_TO_SPOUT") {
    moveToPosition(SPOUT_POSITION);
  }
  else if (command == "MOVE_TO_DISPLAY") {
    moveToPosition(DISPLAY_POSITION);
  }
  else if (command.startsWith("MIX ")) {
    int count = command.substring(4).toInt();
    if (count > 0 && count <= 20) {
      performMix(count);
    } else {
      Serial.println("ERROR: Mix count must be 1-20");
    }
  }
  else if (command == "MIX") {
    // Default to 5 oscillations
    performMix(5);
  }
  else if (command == "STOP") {
    // Immediate stop - just acknowledge
    Serial.println("OK: Stopped");
  }
  else if (command == "HOME") {
    if (USE_LIMIT_SWITCH) {
      homePosition();
    } else {
      currentPosition = 0;
      isHomed = true;
      Serial.println("OK: Position reset to home");
    }
  }
  else if (command == "STATUS") {
    reportStatus();
  }
  else if (command == "PING") {
    Serial.println("PONG");
  }
  else if (command.length() > 0) {
    Serial.print("ERROR: Unknown command '");
    Serial.print(command);
    Serial.println("'");
  }
}

// ============== MOTOR CONTROL ==============
void moveToPosition(long targetPosition) {
  if (!isHomed && USE_LIMIT_SWITCH) {
    Serial.println("ERROR: Must home first");
    return;
  }
  
  long stepsToMove = targetPosition - currentPosition;
  
  if (stepsToMove == 0) {
    Serial.println("OK: Already at position");
    return;
  }
  
  // Set direction
  if (stepsToMove > 0) {
    digitalWrite(DIR_PIN, HIGH);  // Forward
  } else {
    digitalWrite(DIR_PIN, LOW);   // Backward
    stepsToMove = -stepsToMove;   // Make positive for counting
  }
  
  // Move the motor
  for (long i = 0; i < stepsToMove; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(STEP_DELAY_US);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(STEP_DELAY_US);
    
    // Check for stop command during movement
    if (Serial.available() > 0) {
      String cmd = Serial.readStringUntil('\n');
      cmd.trim();
      cmd.toUpperCase();
      if (cmd == "STOP") {
        // Update position to where we stopped
        if (digitalRead(DIR_PIN) == HIGH) {
          currentPosition += i;
        } else {
          currentPosition -= i;
        }
        Serial.println("OK: Stopped mid-move");
        return;
      }
    }
  }
  
  // Update current position
  currentPosition = targetPosition;
  
  // Report success
  if (targetPosition == SPOUT_POSITION) {
    Serial.println("OK: At spout");
  } else if (targetPosition == DISPLAY_POSITION) {
    Serial.println("OK: At display");
  } else {
    Serial.print("OK: At position ");
    Serial.println(currentPosition);
  }
}

void performMix(int oscillations) {
  Serial.print("INFO: Starting ");
  Serial.print(oscillations);
  Serial.println(" mix oscillations");
  
  long startPosition = currentPosition;
  
  for (int i = 0; i < oscillations; i++) {
    // Move forward
    moveSteps(MIX_DISTANCE, true);
    delay(50);  // Brief pause at end
    
    // Move backward
    moveSteps(MIX_DISTANCE, false);
    delay(50);
    
    // Check for stop command
    if (Serial.available() > 0) {
      String cmd = Serial.readStringUntil('\n');
      cmd.trim();
      cmd.toUpperCase();
      if (cmd == "STOP") {
        // Return to start position
        moveToPosition(startPosition);
        Serial.println("OK: Mix stopped early");
        return;
      }
    }
  }
  
  // Make sure we're back at start position
  moveToPosition(startPosition);
  Serial.println("OK: Mix complete");
}

void moveSteps(long steps, bool forward) {
  digitalWrite(DIR_PIN, forward ? HIGH : LOW);
  
  for (long i = 0; i < steps; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(STEP_DELAY_US);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(STEP_DELAY_US);
  }
  
  // Update position
  if (forward) {
    currentPosition += steps;
  } else {
    currentPosition -= steps;
  }
}

void homePosition() {
  if (!USE_LIMIT_SWITCH) {
    Serial.println("ERROR: No limit switch configured");
    return;
  }
  
  Serial.println("INFO: Homing...");
  
  // Move backward until limit switch is triggered
  digitalWrite(DIR_PIN, LOW);  // Backward direction
  
  long maxSteps = (DISPLAY_POSITION + 500) * MICROSTEPPING;  // Safety limit
  
  for (long i = 0; i < maxSteps; i++) {
    // Check if limit switch is pressed (LOW because of pull-up)
    if (digitalRead(LIMIT_PIN) == LOW) {
      currentPosition = 0;
      isHomed = true;
      delay(100);  // Debounce
      
      // Move slightly forward to release switch
      digitalWrite(DIR_PIN, HIGH);
      for (int j = 0; j < 50; j++) {
        digitalWrite(STEP_PIN, HIGH);
        delayMicroseconds(STEP_DELAY_US);
        digitalWrite(STEP_PIN, LOW);
        delayMicroseconds(STEP_DELAY_US);
      }
      currentPosition = 50;
      
      Serial.println("OK: Homed");
      return;
    }
    
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(STEP_DELAY_US);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(STEP_DELAY_US);
  }
  
  Serial.println("ERROR: Homing failed - limit switch not found");
}

void reportStatus() {
  Serial.print("POSITION: ");
  
  if (!isHomed && USE_LIMIT_SWITCH) {
    Serial.println("UNKNOWN");
  } else if (currentPosition == SPOUT_POSITION) {
    Serial.println("SPOUT");
  } else if (currentPosition == DISPLAY_POSITION) {
    Serial.println("DISPLAY");
  } else if (currentPosition == 0) {
    Serial.println("HOME");
  } else {
    Serial.print("STEPS:");
    Serial.println(currentPosition);
  }
}
```

### Step 5.3: Customize the Settings

Before uploading, adjust these values at the top of the code to match your hardware:

```cpp
// MEASURE THESE ON YOUR BELT AND UPDATE!
const long SPOUT_POSITION = 1000;    // Steps from home to spout
const long DISPLAY_POSITION = 2000;  // Steps from home to display
const long MIX_DISTANCE = 200;       // Steps for one mix oscillation
```

**How to find the right values:**
1. Upload the code with default values first
2. Use the test procedure in Section 6 to manually find the right step counts
3. Update the code with correct values
4. Re-upload

### Step 5.4: Upload to Arduino

1. Click the **Upload** button (right arrow icon) in Arduino IDE
2. Wait for "Done uploading" message
3. If you see errors, check:
   - Correct board selected in Tools → Board
   - Correct port selected in Tools → Port
   - USB cable is plugged in securely

### Step 5.5: Test Serial Communication

1. Open **Tools → Serial Monitor** in Arduino IDE
2. Set baud rate to **9600** (dropdown at bottom right)
3. Set line ending to **Newline** (dropdown next to baud rate)
4. Type `STATUS` and press Enter
5. You should see: `POSITION: HOME` (or similar)
6. Type `PING` and press Enter
7. You should see: `PONG`

**If you get no response:**
- Check USB connection
- Check baud rate is 9600
- Check line ending is set to Newline
- Try pressing Arduino's reset button

---

## 6. Testing the Hardware

Now let's test the physical movement. **Keep hands clear of moving parts!**

### Step 6.1: First Movement Test

With Serial Monitor open:

1. Type `MOVE_TO_SPOUT` and press Enter
2. The motor should spin and the belt should move
3. You should see `OK: At spout`

**If the motor doesn't move:**
- Check power supply is on and connected
- Check all wiring connections
- Motor making noise but not spinning? Motor wires might be wrong pairs

**If the motor moves the wrong direction:**
- Swap wires 1A and 1B on the driver

### Step 6.2: Calibration Procedure

Now we need to find the exact step counts for your belt positions:

1. **Find home position manually**
   - Type `HOME` to reset step count to 0
   - Note where the belt/cup holder is - this is position 0

2. **Find spout position**
   - Type `MOVE_TO_SPOUT`
   - If the cup isn't under the spout:
     - Note how far off it is
     - Adjust `SPOUT_POSITION` in the code (higher = further from home)
     - Re-upload and test again

3. **Find display position**
   - Type `MOVE_TO_DISPLAY`
   - Adjust `DISPLAY_POSITION` in the code similarly

4. **Find mix distance**
   - Position cup under spout
   - Type `MIX 3`
   - The cup should oscillate back and forth
   - Adjust `MIX_DISTANCE` if oscillation is too big or small

### Step 6.3: Write Down Your Calibration Values!

```
My Belt Calibration (Date: __________)

SPOUT_POSITION = ________ steps
DISPLAY_POSITION = ________ steps  
MIX_DISTANCE = ________ steps
STEP_DELAY_US = ________ (speed - lower = faster)
```

Save these! If you ever need to re-upload the firmware, you'll need them.

---

## 7. Configuring RoboTaste

Now that the hardware works, let's tell RoboTaste about it.

### Step 7.1: Find the Arduino's Serial Port

1. Open Arduino IDE
2. Go to **Tools → Port**
3. Note the port name (e.g., `/dev/cu.usbmodem14101` on Mac, `COM3` on Windows)

### Step 7.2: Update Your Protocol Configuration

In your experiment protocol JSON, add a `belt_config` section:

```json
{
  "protocol_name": "My Experiment",
  "experiment_type": "binary_mixture",
  
  "pump_config": {
    "enabled": true,
    "..."
  },
  
  "belt_config": {
    "enabled": true,
    "serial_port": "/dev/cu.usbmodem14101",
    "baud_rate": 9600,
    "timeout_seconds": 30,
    "cup_count": 10,
    "mixing": {
      "enabled": true,
      "oscillations": 5,
      "speed": "medium"
    }
  }
}
```

**Configuration options explained:**

| Setting | What it does | Typical value |
|---------|--------------|---------------|
| `enabled` | Turns belt on/off | `true` |
| `serial_port` | Arduino's USB port | From Step 7.1 |
| `baud_rate` | Communication speed | `9600` (must match firmware) |
| `timeout_seconds` | Max time to wait for response | `30` |
| `cup_count` | How many cups in your queue | `10` |
| `mixing.enabled` | Enable mixing after dispense | `true` |
| `mixing.oscillations` | Number of back-forth movements | `5` |
| `mixing.speed` | How fast to oscillate | `"slow"`, `"medium"`, or `"fast"` |

### Step 7.3: Start the Belt Control Service

Open a terminal and run:

```bash
cd /path/to/RoboTaste/Software
python belt_control_service.py --db-path robotaste.db --poll-interval 0.5
```

You should see:
```
INFO - Belt control service starting...
INFO - Connected to database: robotaste.db
INFO - Polling for belt operations...
```

**Keep this terminal running!** The belt service needs to run alongside the main RoboTaste app.

---

## 8. Running a Full Test

### Step 8.1: Pre-Flight Checklist

Before running an experiment:

- [ ] Arduino is connected via USB
- [ ] Motor power supply is on
- [ ] Belt moves freely (nothing blocking it)
- [ ] Belt service is running (`belt_control_service.py`)
- [ ] Pump service is running (if using pumps)
- [ ] RoboTaste app is running

### Step 8.2: Run the Hardware Test Script

This tests the belt without running a full experiment:

```bash
cd /path/to/RoboTaste/Software
python robotaste/hardware/test_belt.py --port /dev/cu.usbmodem14101
```

(Use `--mock` flag to test without hardware)

The interactive test will guide you through:
1. Connecting to the belt
2. Moving to spout position
3. Moving to display position
4. Running a mix cycle
5. Emergency stop test

### Step 8.3: Run a Test Experiment

1. Start RoboTaste: `streamlit run main_app.py`
2. Create a new session with a pump+belt enabled protocol
3. Run through one complete cycle
4. Watch the terminal running `belt_control_service.py` for status messages
5. Verify the sequence: 
   - Cup moves to spout ✓
   - Pump dispenses ✓
   - Cup oscillates for mixing ✓
   - Cup moves to display ✓

---

## 9. Troubleshooting

### Motor Issues

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| Motor doesn't move | No power | Check power supply is on and connected |
| Motor doesn't move | Wrong pins | Verify STEP is pin 2, DIR is pin 3 |
| Motor vibrates but doesn't spin | Wrong coil wiring | Check coil pairs with multimeter |
| Motor moves wrong direction | Wiring | Swap 1A and 1B wires |
| Motor skips steps | Moving too fast | Increase `STEP_DELAY_US` value |
| Motor is very hot | Too much current | Adjust current limit on driver |

### Communication Issues

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| "Port not found" | Wrong port name | Check port in Arduino IDE Tools menu |
| No response to commands | Wrong baud rate | Ensure 9600 in both firmware and config |
| Garbled text | Baud mismatch | Reset Arduino and check settings |
| "Device busy" | Another program using port | Close Arduino IDE Serial Monitor |

### Belt Service Issues

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| "Connection failed" | Port in use | Close other programs, try `--mock` mode |
| Operations stay "pending" | Service not running | Start belt_control_service.py |
| Operations fail immediately | Wrong port in protocol | Update belt_config.serial_port |

### Position Issues

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| Cup not under spout | Wrong calibration | Recalibrate SPOUT_POSITION |
| Belt overshoots | Belt slipping | Check belt tension, recalibrate |
| Position drifts over time | Steps being lost | Add limit switch for homing |

---

## 10. Maintenance Tips

### Daily (Before Each Experiment Session)
- Check belt tension (should be snug, not loose)
- Clear any debris from belt path
- Verify cups are properly seated
- Run a quick test cycle

### Weekly
- Check all wire connections are secure
- Clean belt surface with damp cloth
- Inspect motor mounting

### Monthly
- Recalibrate positions (they may drift slightly)
- Check for worn pulleys or belt
- Tighten any loose screws

### If Things Go Wrong During an Experiment
1. **Stay calm** - The subject doesn't need to know there's an issue
2. **Use STOP command** if belt is moving dangerously
3. **Check belt_control_service.py terminal** for error messages
4. **Can continue without belt?** Manually deliver cups if needed
5. **Document the issue** for later troubleshooting

---

## Quick Reference Card

Print this and keep it near the hardware!

```
╔════════════════════════════════════════════════════════════════╗
║                  ROBOTASTE BELT QUICK REFERENCE                ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  SERIAL COMMANDS (9600 baud):                                  ║
║    MOVE_TO_SPOUT  - Position cup for dispensing                ║
║    MOVE_TO_DISPLAY - Position cup for pickup                   ║
║    MIX 5          - Oscillate 5 times                          ║
║    STOP           - Emergency stop                              ║
║    STATUS         - Report current position                    ║
║    HOME           - Reset to home position                     ║
║                                                                ║
║  START SERVICES:                                               ║
║    streamlit run main_app.py                                   ║
║    python belt_control_service.py --db-path robotaste.db       ║
║    python pump_control_service.py --db-path robotaste.db       ║
║                                                                ║
║  TEST HARDWARE:                                                ║
║    python robotaste/hardware/test_belt.py --port /dev/XXX      ║
║                                                                ║
║  MY SETTINGS:                                                  ║
║    Serial Port: _______________________                        ║
║    Spout Steps: _______________________                        ║
║    Display Steps: _____________________                        ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

---

## Need More Help?

1. **Check the logs**: `logs/` folder contains detailed operation logs
2. **Database inspection**: Use DB Browser for SQLite to view `belt_operations` table
3. **Arduino debugging**: Open Serial Monitor to see what commands are being received
4. **Code reference**: See `robotaste/hardware/belt_controller.py` for Python-side implementation

Good luck with your setup! 🎉
