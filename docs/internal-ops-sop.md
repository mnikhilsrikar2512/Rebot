# Client Chatbot Operations SOP

## 1) Onboarding

- Collect client essentials: business domain, goals, and guardrails.
- Complete one-time integration checklist.
- Assign default behavior profile.
- Run acceptance test prompts and capture sign-off.

## 2) Request Intake

- Capture request in a standard template:
  - client
  - desired change
  - priority
  - success criteria
- Classify request as one of:
  - profile tuning
  - policy adjustment
  - platform bug or feature

## 3) Execution

- Apply client-specific profile changes centrally.
- Validate with a fixed prompt pack (before/after comparison).
- Ensure no cross-client impact.

## 4) Verification

- Functional checks pass.
- Quality checks pass (relevance, domain fit, concise style).
- Stakeholder preview completed when needed.

## 5) Release

- Publish change to target client profile.
- Monitor first responses after release.
- Keep rollback ready.

## 6) Communication

- Send concise update:
  - what changed
  - what to expect
  - when it went live
- Request client confirmation that behavior matches expectations.

## 7) Incident Handling

- If degraded behavior is detected:
  - roll back profile immediately
  - notify client
  - log root cause
  - apply corrective action and retest

## 8) Continuous Improvement

- Weekly review:
  - common client requests
  - repeated pain points
  - candidate default profile improvements
- Convert repeat manual adjustments into reusable profile presets.
