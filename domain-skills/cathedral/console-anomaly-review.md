# Cathedral runbook — Console anomaly review

Use this when another signal already suggests a problem, and the browser must determine what the console is actually warning about.

Examples:
- deploy looks broken
- domain looks half-configured
- dashboard shows warnings not visible in API output
- permissions or org/team mismatch is suspected

## Goal

Turn a vague anomaly into a precise statement:
- where the warning is
- what the UI says
- whether it is actionable
- whether it needs approval

## Method

1. open the exact console and scope
2. capture overview screenshot
3. drill into warning badge / banner / failed status
4. record visible message text and nearby controls
5. map it to one of: cosmetic, configuration drift, blocked workflow, production risk, billing risk, security risk

## Output

- anomaly source
- visible warning text
- blast radius
- recommended next action
- approval boundary