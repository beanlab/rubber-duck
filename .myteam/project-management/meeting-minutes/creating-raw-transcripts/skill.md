---
name: Creating Raw Transcripts
description: |
   Load this skill if you need to create raw transcripts from audio recordings
   or from raw text.
---

# Creating Raw Transcripts

Workflow:

- Transcribe audio to raw text, if needed.
- Clean raw text
- Save to raw-transcripts folder
- Report on location of raw-transcript

## Overview

- Name the transcript file `YYYY-MM-DD-HHMM.raw.md`
- Put this file in `../raw-transcripts/<repo name>/`

This file should **not** be checked in to Git. 
This is why it resides outside the project repo.

When asking for permission to create files,
ask for permission to modify or create files in 
the `../raw-transcripts/<repo>/` folder.
If the permission is scoped to the specific files, 
permission has to be granted for each run of this process, 
and that's not helpful.

## Transcribing From Audio

If the input is raw text, save this text as the raw-transcript file
and proceed to the cleaning step. 
If the user hasn't provided the time of the meeting, ask them for it. 

If the input is an audio file, follow these steps.

This step depends on `faster-whisper` for audio transcription.
If this package is not installed in the current environment,
and you need to transcribe from an audio input,
offer to install it.

Read the file creation timestamp from the source audio file.
On macOS, `stat -f '%SB' -t '%Y-%m-%d-%H%M' <file>` works.

Save the raw transcript to the raw-transcripts folder.

- Use repository-local caches when practical so downloaded model
  artifacts stay in the workspace.
- If `faster-whisper` is used, a workable pattern is:
  `HF_HOME=<repo>/.cache/huggingface`
  `XDG_CACHE_HOME=<repo>/.cache`
- CPU transcription is acceptable for one-off meeting recordings.
- make sure the `.cache` folder is NOT tracked by git.


## Cleaning Raw Text

Using the `.raw.md` file from the previous step as input:

- fix obvious punctuation and capitalization
- merge sentence fragments into readable paragraphs
- correct obvious recognition mistakes
- **do not invent missing content**
- if a phrase is too garbled to recover, mark it as `[unclear]`
- keep line lengths to less than 70 characters per line

Save the result back to the same file. 

## Wrap Up

- Verify that the transcript is **not** tracked by Git.
- Report the path to the transcript file you created.

