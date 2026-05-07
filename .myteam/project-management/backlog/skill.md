---
name: "Github Issues"
description: |
  Backlog and project-management instructions using GitHub Issues.
  Load this skill when reading, listing, searching,
  understanding, or modifying project backlog issues.
---

# Github Issues

This project's backlog is managed with GitHub Issues tracked in the
Bean Lab GitHub Project.

## Authentication

- GitHub issue work uses the `gh` CLI with the current repository
  by default.
- Check authentication with `gh auth status` when needed.
- If `gh auth status` reports an environment-token problem, verify
  whether the needed `gh` commands actually fail before stopping. Some
  environments report an invalid `GITHUB_TOKEN` while the keychain or
  approved command path still works.
- If the needed `gh` commands cannot authenticate, ask the user to
  provide a GitHub token or authenticate `gh` before proceeding.
- Use `-R OWNER/REPO` when working outside the current repository.

## Project Target

These skills use the Bean Lab GitHub Project as the
project-management surface:

- Project URL: `https://github.com/orgs/beanlab/projects/13`
- Project owner: `beanlab`
- Project number: `13`

Use project item listing as the source of truth for what is currently
tracked in the backlog:

```sh
gh project item-list 13 --owner beanlab --format json
```

## Reading Issues

Use these commands to inspect the issue tracker:

- List all available issues:
  ```sh
  gh issue list \
    --state all \
    --limit 100 \
    --json number,title,state,labels,url,updatedAt
  ```
- List open issues:
  ```sh
  gh issue list \
    --limit 100 \
    --json number,title,state,labels,url,updatedAt
  ```
- Search issues:
  ```sh
  gh issue list \
    --state all \
    --search "<query>" \
    --json number,title,state,labels,url,updatedAt
  ```
- View an issue with comments:
  `gh issue view <number-or-url> --comments`
- View structured issue data:
  ```sh
  gh issue view <number-or-url> --comments \
    --json number,title,body,labels,state,url,comments
  ```
- List repository labels:
  `gh label list --sort name --limit 200 --json name,description`
- Show issues relevant to the authenticated user:
  `gh issue status`

## Modifying Issues

Use these commands when updating an existing backlog issue:

- Edit title, labels, or body:
  ```sh
  gh issue edit <number-or-url> \
    --title "<title>" \
    --body-file <body-file> \
    --add-label "<label>"
  ```
- Add a discussion note or clarification:
  `gh issue comment <number-or-url> --body-file <body-file>`
- Close a completed or obsolete issue:
  `gh issue close <number-or-url> --comment "<short reason>"`
- Reopen an issue:
  `gh issue reopen <number-or-url>`

## Issue Structure

Backlog issues should use this durable structure:

```md
Created on: <YYYY-MM-DD>
Created by: <user or agent>

## Details

<Overview of the item. Capture the problem, intent, and details
currently known.>

## Out-of-scope

<Changes or features left for other backlog items. Reference related
issues when known.>

## Dependencies

<Other backlog issues this item depends on. Reference related issues
when known.>
```

GitHub also tracks:

- Number or URL: stable identifiers for referencing the issue.
- Title: short summary of the work or problem.
- Type: exactly one of `Touch Code` or `Task`.
- Body: durable backlog description using the structure above.
- Labels: optional metadata used for filtering. By default, only use
  `needs-clarification` when the issue is ambiguous or incomplete.
- State: `open` or `closed`.
- Comments: discussion, follow-up, and implementation notes.

Some older backlog issues may follow a different format. If you modify
one, update it as best you can to match this format and ask the user
for missing information when needed.

## Guidance

- Prefer JSON output when the result will be used for planning,
  filtering, or follow-up automation.
- Use `--comments` when discussion history may affect the current
  task.
- Check labels before assuming available workflow categories.
- Treat the issue body as the source of durable requirements; comments
  may contain later clarifications.
- Treat backlog issues as placeholders for ideas or TODO items, not
  implementation plans.
- Capture the information immediately on hand from the conversation.
- Think through what information should and should not be included.
  Do not flesh out the idea beyond what is known.
- Keep implementation details in the issue only when they already
  exist or are necessary context.

## Creating Issues

When asked to create a GitHub issue, load and follow
`project-management/backlog/create-issue`.