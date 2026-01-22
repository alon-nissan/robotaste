# Coding Agent Efficiency Guide

## Token Usage Optimization

### ❌ Bad Prompt (Wasteful)
"Can you help me fix the issue where the pump isn't working? I'm not sure what's wrong."

### ✓ Good Prompt (Efficient)
"Pump at address 0 not responding to dispense commands. Serial port: /dev/ttyUSB0. Error: timeout after 5s. Check `hardware/pump_controller.py` connection logic."

### Why Better?
- Specific file path provided (no exploration needed)
- Error details included (skip debugging)
- Exact symptom described (targeted fix)

## When to Use Which Agent Type

| Agent Type | Use Case | Example |
|------------|----------|---------|
| **Explore** | Find files, understand patterns | "Where is BO convergence checked?" |
| **Plan** | Design complex changes | "Add new questionnaire type with multi-scale rating" |
| **Direct Execution** | Simple, known changes | "Fix typo in moderator.py line 145" |

## Providing Context Efficiently

### Option 1: File Paths (Best)
"Update `robotaste/core/state_machine.py` to add CUSTOM phase"

### Option 2: Grep Pattern (Good)
"Find all calls to `validate_transition()` and add logging"

### Option 3: Requirements (Acceptable)
"Add phase validation to all phase changes"

### Option 4: Vague Description (Avoid)
"Make the state machine better"

## Common Mistakes to Avoid
1. **Asking for full code reprints** → Request diffs only
2. **Vague error descriptions** → Include stack traces, file:line
3. **Not specifying test scope** → Say "run pytest tests/test_protocol_integration.py"
4. **Exploring when you know the file** → Directly reference file paths
5. **Requesting multiple unrelated changes** → Break into separate prompts

## Iterative Development Pattern
1. **Explore**: "Find all BO-related files"
2. **Plan**: "Design approach to add UCB acquisition function"
3. **Execute**: "Implement UCB in `core/bo_engine.py` based on plan"
4. **Verify**: "Run `pytest tests/test_bo_engine.py -v`"

## Token-Saving Templates

### Bug Fix Template
```
Bug: [symptom]
File: [exact path:line]
Error: [stack trace or error message]
Expected: [correct behavior]
```

### Feature Template
```
Feature: [what to add]
Location: [file or module]
Pattern: [similar existing feature to follow]
Tests: [which tests to run]
```

### Refactoring Template
```
Refactor: [function/module name]
Reason: [why - performance, clarity, etc.]
Constraints: [what must stay the same]
Verify: [how to test nothing broke]
```

## Advanced Tips
1. **Grep before reading**: Use Grep to find exact lines, then Read file
2. **Leverage git history**: "Check git log for `pump_manager.py` changes"
3. **Reference tests**: "Follow pattern in `tests/test_protocol_integration.py`"
4. **Ask for examples**: "Show me one example of protocol validation, not all"
5. **Use quick reference**: Check CLAUDE.md Section 2.5 before exploring
