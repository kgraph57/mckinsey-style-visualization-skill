# Security Policy

## Normal Skill Behavior

This package is a documentation-first Agent Skill. It has no install-time or
background behavior and requires no credentials. Core rendering makes no
network request. Authoring commands write only the explicit `-o` or
`--audit-out` destination selected by the user.

The validation script is optional and uses only the Python standard library.
It reads repository inputs, rebuilds reviewed HTML into temporary directories,
and prints validation results. Optional PDF, browser E2E, and audit workflows
use pinned Playwright browsers and Poppler outside the core validation lane.

## Data Handling

The skill does not retain user data. Agents using the skill may process business metrics, strategic notes, or confidential material provided by the user. Users should avoid sharing sensitive data with agent environments they do not control.

## Permissions

| Capability | Required |
| --- | --- |
| Network access | No |
| Filesystem write | Yes, explicit output destinations only |
| External tools | No |
| Credentials | No |
| Background execution | No |

Generated interactive decks make no automatic network request. A presenter
may explicitly activate only a build-validated `https:` or bounded `mailto:`
source link. Same-document fragments must not contain patient, credential,
confidential, or personal data. The self-contained meta CSP reduces local-file
capability but does not prove hosted `frame-ancestors`; verify server response
headers after deployment.

## Safety Rules

- Do not add hidden scripts or install-time automation.
- Root-confine manifest `spec` and `scene` paths and reject symlink escapes.
- Keep audit state traversal and outputs out of audience artifacts and public proof paths.
- Do not add network calls to validation without documenting them here.
- Do not embed private client data in examples.
- Do not imply affiliation with named consulting firms.
- Do not invent data, citations, confidential labels, or benchmark results.

## Reporting

Open a GitHub issue for suspected vulnerabilities, unsafe instructions, hidden behavior, or marketplace policy concerns. Do not include confidential business data in public reports.
