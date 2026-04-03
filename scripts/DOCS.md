## Purpose

`scripts/generate_metadata.py` generates `.meta.json` files for CSV datasets in S3.
It can target:

- One dataset file (`s3://bucket/path/file.csv`)
- One TXT file (`s3://bucket/path/file.txt`, converted to CSV first)
- A prefix containing many datasets (`s3://bucket/path/prefix/`)

The script drafts metadata from column data types, refines it with an OpenAI model, and writes JSON metadata next to the dataset in S3.

## Operational Flow

1. Parse CLI flags (`--s3-uri`, `--mode`, `--dry-run`, `--model`).
2. Resolve target S3 bucket/key or prefix from `--s3-uri`.
3. Collect matching `.csv` and `.txt` objects.
4. Convert `.txt` to `.csv` when needed.
5. Load dataset into pandas.
6. Build draft metadata:
   - `dataset_name`
   - `description` (initially blank)
   - `columns[]` with `col_name`, draft `display_name`, blank `description`, inferred `dtype`
7. Refine the draft using OpenAI.
8. Write `<dataset>.meta.json` to S3 unless `--dry-run` is set.

If `--s3-uri` is not provided, default behavior remains:
- bucket: `stats121-datasets`
- prefix: `datasets/`

## CLI Reference

```bash
python scripts/generate_metadata.py [options]
```

- `--s3-uri <s3://bucket/key-or-prefix>`
- `--mode {create,overwrite}`:
  - `create` skips datasets with existing `.meta.json`
  - `overwrite` regenerates metadata even when `.meta.json` exists
- `--dry-run`: runs full generation but does not write metadata files
- `--model <name>`: overrides the model used for refinement
- `--debug`: enables debug logging

## Environment Requirements

Set these before running:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `OPENAI_API_KEY`

Also ensure AWS credentials have permissions for:

- `s3:GetObject`
- `s3:ListBucket`
- `s3:PutObject` (not required for `--dry-run`)
- `s3:HeadObject`

## Common Commands

Generate metadata for one CSV (skip if metadata already exists):

```bash
python scripts/generate_metadata.py \
  --s3-uri s3://byu-cms-metrics/cs-merged-dashboard.csv \
  --mode create \
  --model gpt-5-mini
```

Dry run for one CSV (recommended first):

```bash
python scripts/generate_metadata.py \
  --s3-uri s3://byu-cms-metrics/cs-merged-dashboard.csv \
  --mode overwrite \
  --dry-run \
  --model gpt-5-mini
```

Generate for an entire prefix:

```bash
python scripts/generate_metadata.py \
  --s3-uri s3://byu-cms-metrics/ \
  --mode create \
  --model gpt-5-mini
```

Run default legacy behavior:

```bash
python scripts/generate_metadata.py --model gpt-5-mini
```

## Output Contract

For each dataset `path/name.csv`, metadata is written to:

- `path/name.meta.json`

JSON shape:

```json
{
  "dataset_name": "Example Dataset",
  "description": "Short dataset summary",
  "columns": [
    {
      "col_name": "raw_column_name",
      "display_name": "Raw Column Name",
      "description": "Column meaning",
      "dtype": "int | float | string | string: category1, category2, ..."
    }
  ]
}
```

## Failure Modes and Guardrails

- If `--s3-uri` is malformed, the script exits with a validation error.
- If no CSV/TXT keys are found for a target URI, the script logs a warning and exits successfully.
- In `create` mode, existing metadata is skipped.
- In `dry-run` mode, no `.meta.json` files are written.
- If OpenAI model access is denied (for example model not enabled for the project), rerun with a permitted model using `--model`.
- TXT conversion tries multiple delimiters; non-standard delimiter usage is logged.

## Notes for Safe Use

- Start with `--dry-run` for new buckets or prefixes.
- Use `--mode overwrite` only when intentional metadata replacement is desired.
- Prefer explicit file URIs when testing a new model or permissions.
