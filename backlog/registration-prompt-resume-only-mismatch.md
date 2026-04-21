# Registration Prompt Resume-Only Mismatch

Created on: 2026-04-20
Created by: Tyler (discovered by spring-cleaning agents)

## Details

The registration prompt appears to assume a resume-only flow, which conflicts with
the baseline registration sequence documented in `docs/application_interface.md`
(Net ID → email → nickname → roles). This mismatch could cause prompt behavior
to diverge from the intended registration workflow.

- Problem addressed: Prompt instructions may not reflect the configured or
  expected registration workflow.
- Intent: Align registration prompt guidance with actual workflow usage.
- Known details:
  - `prompts/production-prompts/registration.txt` includes “Resume Assumption”
    and “Entry Logic” language that suggests resume-only behavior.
  - `docs/application_interface.md` describes a general registration flow.

## Out-of-scope

- Updating the actual registration workflow implementation.
- Changing behavior in `registration` flow without a separate design/update pass.

## Dependencies

- None noted.
