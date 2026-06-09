# Security Policy

## Normal Skill Behavior

This package is a documentation-first Agent Skill. Normal use requires no network access, no background processes, no credential access, and no filesystem writes.

The validation script is optional and uses only the Python standard library. It reads repository files and prints validation results.

## Data Handling

The skill does not retain user data. Agents using the skill may process business metrics, strategic notes, or confidential material provided by the user. Users should avoid sharing sensitive data with agent environments they do not control.

## Permissions

| Capability | Required |
| --- | --- |
| Network access | No |
| Filesystem write | No |
| External tools | No |
| Credentials | No |
| Background execution | No |

## Safety Rules

- Do not add hidden scripts or install-time automation.
- Do not add network calls to validation without documenting them here.
- Do not embed private client data in examples.
- Do not imply affiliation with named consulting firms.
- Do not invent data, citations, confidential labels, or benchmark results.

## Reporting

Open a GitHub issue for suspected vulnerabilities, unsafe instructions, hidden behavior, or marketplace policy concerns. Do not include confidential business data in public reports.
