import os
import json
from pathlib import Path
from io import BytesIO, StringIO

import pandas as pd
import boto3
from openai import OpenAI

# ---------------------------
# CONFIGURATION
# ---------------------------

# Environment variables required:
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, OPENAI_API_KEY

MODEL = "gpt-4.1-mini"
MAX_CATEGORIES = 3  # Maximum unique categorical values to list before using "etc."

print("[DEBUG] Initializing OpenAI client...")
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
if not client.api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable not set")
print("[DEBUG] OpenAI client initialized successfully.")

# ---------------------------
# File Type Helpers
# ---------------------------

def _is_csv(key: str) -> bool:
    return key.lower().endswith(".csv")

def _is_txt(key: str) -> bool:
    return key.lower().endswith(".txt")

# ---------------------------
# S3 Helpers
# ---------------------------

def _metadata_exists(s3, bucket: str, meta_key: str) -> bool:
    """Check if metadata JSON exists in S3."""
    try:
        s3.head_object(Bucket=bucket, Key=meta_key)
        return True
    except s3.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise

def _write_metadata_to_s3(s3, bucket: str, key: str, metadata: dict):
    """Write a metadata dict as JSON to S3."""
    json_body = json.dumps(metadata, indent=2)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json_body,
        ContentType="application/json"
    )
    print(f"[DEBUG] Metadata written to s3://{bucket}/{key}")

def _convert_txt_to_csv_in_s3(
        s3,
        bucket: str,
        txt_key: str,
        overwrite: bool = False
) -> str:
    """
    Convert a TXT file in S3 to a CSV file, trying multiple delimiters.
    Logs clearly if a non-standard delimiter is detected.
    """
    if not txt_key.lower().endswith(".txt"):
        raise ValueError("txt_key must point to a .txt file")

    csv_key = txt_key.replace(".txt", ".csv")

    if not overwrite:
        try:
            s3.head_object(Bucket=bucket, Key=csv_key)
            print(f"[DEBUG] CSV already exists for {txt_key}, skipping.")
            return csv_key
        except s3.exceptions.ClientError as e:
            if e.response["Error"]["Code"] != "404":
                raise

    print(f"[DEBUG] Converting TXT to CSV: {txt_key}")
    obj = s3.get_object(Bucket=bucket, Key=txt_key)
    raw_bytes = obj["Body"].read()
    try:
        txt_body = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        print(f"[WARNING] UTF-8 decoding failed for {txt_key}, trying latin-1...")
        txt_body = raw_bytes.decode("latin-1")

    delimiter_trials = [
        ("whitespace", {"sep": r"\s+"}),
        ("semicolon", {"sep": ";"}),
        ("tab", {"sep": "\t"}),
        ("comma", {"sep": ","}),
    ]

    best_df = None
    best_label = None

    for label, read_kwargs in delimiter_trials:
        try:
            df = pd.read_csv(StringIO(txt_body), **read_kwargs)
            if df.shape[1] == 0:
                continue
            if all(pd.to_numeric(df.columns, errors="coerce").notna()):
                continue
            best_df = df
            best_label = label
            break
        except Exception:
            continue

    if best_df is None:
        raise RuntimeError(
            f"Could not infer delimiter for {txt_key}. Manual inspection required."
        )

    if best_label != "whitespace":
        print(f"[WARNING] Non-standard delimiter detected for {txt_key}: {best_label}")

    csv_buffer = StringIO()
    best_df.to_csv(csv_buffer, index=False)

    s3.put_object(
        Bucket=bucket,
        Key=csv_key,
        Body=csv_buffer.getvalue(),
        ContentType="text/csv"
    )

    print(f"[DEBUG] CSV written to s3://{bucket}/{csv_key} (delimiter={best_label})")
    return csv_key

def _load_csv_from_s3(s3, bucket: str, key: str) -> pd.DataFrame:
    """Load a CSV from S3 with UTF-8 fallback encoding."""
    obj = s3.get_object(Bucket=bucket, Key=key)
    data_bytes = obj["Body"].read()
    try:
        df = pd.read_csv(BytesIO(data_bytes))
    except UnicodeDecodeError:
        print(f"[WARNING] UTF-8 decoding failed for {key}, trying latin-1...")
        df = pd.read_csv(BytesIO(data_bytes), encoding="latin-1")
    return df

# ---------------------------
# Data Helpers
# ---------------------------

def _infer_dtype_dynamic(series: pd.Series, max_categories: int = MAX_CATEGORIES) -> str:
    """
    Dynamically infer dtype from the actual CSV column.
    - Numeric → int or float
    - String / object → string: val1, val2, etc.
    """
    s = series.dropna()
    if s.empty:
        return "string"

    if pd.api.types.is_integer_dtype(s):
        return "int"
    if pd.api.types.is_float_dtype(s):
        if (s % 1 == 0).all():
            return "int"
        return "float"

    try:
        s_numeric = pd.to_numeric(s, errors="coerce")
        if s_numeric.notna().all():
            return "int" if (s_numeric % 1 == 0).all() else "float"
    except Exception:
        pass

    unique_vals = pd.Series(s.astype(str).str.strip()).unique()
    if len(unique_vals) == 0:
        return "string"
    elif len(unique_vals) <= max_categories:
        return f"string: {', '.join(unique_vals)}"
    else:
        return f"string: {', '.join(unique_vals[:max_categories])}, etc."

def _draft_metadata(df: pd.DataFrame, dataset_name: str, bucket: str, key: str) -> dict:
    """Create draft metadata dict from a DataFrame."""
    columns = []
    for col in df.columns:
        dtype = _infer_dtype_dynamic(df[col])
        columns.append({
            "name": col,
            "display_name": col.replace("_", " ").title(),
            "description": "",
            "dtype": dtype
        })
        print(f"[DEBUG] Column {col}: dtype={dtype}")
    draft_meta = {
        "name": dataset_name,
        "description": f"Dataset loaded from s3://{bucket}/{key}",
        "columns": columns
    }
    return draft_meta

# ---------------------------
# GPT Helpers
# ---------------------------

def _refine_metadata_with_gpt(draft_meta: dict) -> dict:
    """Uses GPT to improve display_name, descriptions, and normalize dtypes."""
    print(f"[DEBUG] Sending draft metadata to GPT: {draft_meta['name']}")
    prompt = f"""
You are a data catalog assistant.

Rules:
- Improve display_name capitalization and wording
- Write concise, professional column descriptions
- Normalize dtype to one of: int, float, string, string: value1, value2, ...
- If string is of a specified format (date, time, etc.) set the dtype to that format
- Do NOT invent categories
- Do NOT rename columns
- Output valid JSON only

---

Draft metadata:
{json.dumps(draft_meta, indent=2)}
"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Return metadata JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    refined = json.loads(response.choices[0].message.content)
    print(f"[DEBUG] Received refined metadata from GPT for {draft_meta['name']}")
    return refined

# ---------------------------
# Dataset Processing Helper
# ---------------------------

def _process_dataset(s3, bucket: str, key: str, mode: str) -> dict | None:
    """
    Process a single dataset: load CSV, draft metadata, refine with GPT, and write to S3.
    Returns the refined metadata dict, or None if skipped.
    """
    dataset_name = Path(key).stem
    meta_key = key.replace(".csv", ".meta.json")

    print(f"[DEBUG] Processing dataset: {dataset_name}")

    if mode == "create" and _metadata_exists(s3, bucket, meta_key):
        print(f"[DEBUG] Metadata exists for {dataset_name}, skipping.")
        return None

    df = _load_csv_from_s3(s3, bucket, key)
    draft_meta = _draft_metadata(df, dataset_name, bucket, key)
    refined_meta = _refine_metadata_with_gpt(draft_meta)
    _write_metadata_to_s3(s3, bucket, meta_key, refined_meta)
    return refined_meta

# ---------------------------
# Main S3 Metadata Generator
# ---------------------------

def generate_s3_metadata(s3_prefix: str, bucket: str, mode: str = "create") -> dict:
    """
    Reads all CSV datasets under the given S3 prefix and generates GPT-refined metadata.
    Returns: dict of {dataset_name: meta_json_dict}
    """
    print(f"[DEBUG] Connecting to S3 bucket: {bucket}")
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")

    data_keys = []

    for page in paginator.paginate(Bucket=bucket, Prefix=s3_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if _is_txt(key):
                key = _convert_txt_to_csv_in_s3(s3, bucket, key)
            if _is_csv(key):
                data_keys.append(key)

    metadata_dict = {}
    for key in data_keys:
        refined_meta = _process_dataset(s3, bucket, key, mode)
        if refined_meta:
            metadata_dict[Path(key).stem] = refined_meta

    print(f"[DEBUG] Metadata generation complete. Total metadata files created: {len(metadata_dict)}")
    return metadata_dict

# ---------------------------
# Script Entry Point
# ---------------------------

if __name__ == "__main__":
    bucket = "stats121-datasets"
    prefix = "datasets/"

    print("[DEBUG] Starting metadata generation...")
    all_meta = generate_s3_metadata(prefix, bucket)

    for dataset_name, meta in all_meta.items():
        print(f"\n--- Metadata for {dataset_name} ---\n")
        print(json.dumps(meta, indent=2))