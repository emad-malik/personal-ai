# Feedback Log

Track tool feedback as required by hackathon rules.

## Token Factory

| Date | Issue / Feedback | Resolution |
|------|-----------------|------------|
| Oct 5 | Setup: Nano (30B-A3B) and Super (120b-a12b) both respond on Token Factory. OpenAI-compatible client works out of the box. Nano model ID needed casing fix (nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B). | Working. |

## Hermes Agent

| Date | Issue / Feedback | Resolution |
|------|-----------------|------------|
| Oct 14 | Hermes `hermes model` custom endpoint wizard verified Token Factory via /v1/models (25 models listed) and a first chat with Super worked. Model list is useful, but Nemotron IDs have inconsistent casing across models (NVIDIA-Nemotron-3-Nano-30B-A3B vs nemotron-3-super-120b-a12b). | Worked. Copy IDs from the wizard list. |
| Oct 14 | Hermes gateway deliverable mode uploaded a .csv from a plain-text path in the reply but not a .ipynb (path stayed as text). The docs do not list which extensions are shipped or how to add one. | Workaround: own uploader using Slack files_upload_v2. Request: a config list of extra allowed extensions. |

## NemoClaw / OpenShell

| Date | Issue / Feedback | Resolution |
|------|-----------------|------------|
| | | |
