# Sources and trust levels

| Label | Meaning | How to use it |
| --- | --- | --- |
| VERIFIED | Reviewable technical evidence has been checked | Include the command, result, file, or version; state the scope of verification |
| USER_CONFIRMED | The user explicitly made a decision or accepted the work | Record the decision and its scope; do not present it as technical verification |
| AGENT_REPORTED | An AI or worker says it happened, but the lead has not checked independently | Preserve the source and wait for review |
| UNKNOWN | Evidence is missing or the item has not been tested | State what needs confirmation; do not infer completion |

For example, a passing test can be VERIFIED. If the user says the visual result is ready to publish, that is USER_CONFIRMED. A worker saying it fixed a bug is initially AGENT_REPORTED. Technical checks do not replace human acceptance.
