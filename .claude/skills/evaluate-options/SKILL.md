---
name: evaluate-options
description: Analytical framework to weigh 5 different business or code directions.
argument-hint: [path/to/scenarios.json]
---

# Skill: Evaluate Options (/evaluate-options)

Turn a scenario file of five candidate choices into a rigorous, comparable, graded decision. Every option is decomposed into the same XML risk framework, scored on identical axes, and assigned a letter grade — so the comparison is apples-to-apples, not vibes.

## Inputs

- **Argument:** a path to the scenario file (e.g. `/evaluate-options path/to/scenarios.json`).
- If no path is given, ask the user for one. Do NOT invent a scenario.
- The file must contain **exactly 5 distinct choices**.
- **Preferred format — JSON.** An array of 5 objects, or an object with an `options`/`choices` array of 5:
  ```json
  {
    "scenario": "Which direction for the Q3 rollout?",
    "options": [
      { "title": "Ship behind a flag", "description": "..." },
      { "title": "Full cutover", "description": "..." }
    ]
  }
  ```
  Read each option's `title` and `description` (or equivalent fields). If the JSON is malformed, report the parse error and the offending fragment — do not guess the structure.
- **Fallback formats.** If the file is markdown/text rather than JSON, accept choices delimited by markdown headings (`## Option ...`), a numbered/bulleted list of 5 items, or explicit `Option 1:` / `Choice A:` markers.

## Rules & Constraints

- **Exactly five.** Parse the file and count the choices first. If you find fewer or more than 5, STOP and report the count you found and how you delimited them — do not pad, split, or merge to force five. Ask the user to correct the file or confirm the intended split.
- **Framework before grade.** Never emit a grade for an option before its full `<risk-analysis>` block exists. The grade is *derived* from the scored axes, not asserted.
- **Same axes for all five.** Every option is scored on the identical five risk axes below. No bespoke axes for individual options.
- **Evidence, not adjectives.** Each axis score must cite a concrete reason grounded in the scenario text — not "seems risky."
- **No ties at the top.** If two options compute the same risk index, break the tie explicitly on Reversibility (more reversible wins), and say so.
- **Preserve the source language.** If the scenario file is written in another language, produce the evaluation in that same language.

## The XML Risk Framework

Score each axis from **1 (best / lowest risk) to 5 (worst / highest risk)**. Weights reflect how much each axis moves the decision.

| Axis | Weight | 1 (best) → 5 (worst) |
|---|---|---|
| `likelihood` | ×3 | How likely is the failure mode to actually occur? |
| `impact` | ×3 | If it fails, how severe is the blast radius? |
| `reversibility` | ×2 | Can we undo it cheaply? (1 = trivially reversible, 5 = one-way door) |
| `detectability` | ×1 | Will we notice the failure in time to react? (1 = obvious early, 5 = silent) |
| `cost` | ×1 | Resource/time/complexity cost to execute? (1 = cheap, 5 = expensive) |

**Risk index** = Σ (axis score × weight). Range: **10 (best) → 50 (worst)**.

Emit one block per option, in this exact shape:

```xml
<option id="1" title="...">
  <risk-analysis>
    <likelihood score="N">concrete reason grounded in the scenario</likelihood>
    <impact score="N">concrete reason</impact>
    <reversibility score="N">concrete reason</reversibility>
    <detectability score="N">concrete reason</detectability>
    <cost score="N">concrete reason</cost>
  </risk-analysis>
  <risk-index>NN</risk-index>
  <mitigation>the single highest-leverage action that lowers this option's worst axis</mitigation>
  <grade letter="X">one-sentence justification tied to the risk index</grade>
</option>
```

## Grading Scale

Map the risk index (10–50) to a letter grade:

| Risk index | Grade | Meaning |
|---|---|---|
| 10–17 | **A** | Low risk, high confidence — proceed |
| 18–25 | **B** | Sound with named mitigations |
| 26–33 | **C** | Viable but conditional; mitigate before committing |
| 34–41 | **D** | High risk; only if strategically forced |
| 42–50 | **F** | Reject; failure likely and/or irreversible |

## Workflow

### 1. Ingest & validate
Read the scenario file. Identify how the choices are delimited and extract them. State the count. If it is not exactly 5, stop per the rule above.

### 2. Frame each option
For all 5 options, emit the `<option>` XML block: score all five axes with grounded reasons, compute the `<risk-index>`, name the top mitigation, and assign the derived grade. Do the analysis before the letter — no back-filling scores to justify a preferred grade.

### 3. Ranking & recommendation matrix
After all five blocks, produce a summary table sorted by risk index (best first):

| Rank | Option | Risk index | Grade | Top mitigation |
|---|---|---|---|---|

### 4. Verdict
State the winning option, the runner-up, and the single non-negotiable mitigation the winner needs before execution. If the best available grade is D or F, say plainly that no option is safe and recommend reworking the scenario rather than picking the "least bad."
