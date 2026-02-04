# clean_data.py
import argparse
import json
import re
import os
from datetime import datetime, timezone

import pandas as pd
from dateutil import parser as date_parser
from pandas.api.types import is_object_dtype, is_string_dtype


NULL_TOKENS = {
    "",
    " ",
    "  ",
    "n/a",
    "na",
    "null",
    "none",
    "nil",
    "nan",
    "-",
    "--",
    "unknown",
    "?",
    "today",
    "yesterday",
    "tomorrow",
}

TAG_SEPARATORS = re.compile(r"\s*[;,|/]\s*")

def is_text_series(series):
    return is_string_dtype(series) or is_object_dtype(series)


def normalize_column_name(name):
    name = name.strip()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[^\w\s]", "", name)
    name = name.replace(" ", "_").lower()
    return name


def collapse_whitespace(value):
    if not isinstance(value, str):
        return value
    value = value.replace("\\t", " ").replace("\\n", " ").replace("\\r", " ")
    return re.sub(r"\s+", " ", value).strip()


def normalize_nulls(series, report, col_name):
    before_nulls = series.isna().sum()
    series = series.apply(lambda v: None if (isinstance(v, str) and v.strip().lower() in NULL_TOKENS) else v)
    after_nulls = series.isna().sum()
    report["nulls_normalized"][col_name] = int(after_nulls - before_nulls)
    return series


def trim_strings(series, report, col_name):
    if not is_text_series(series):
        return series
    before = series.copy()
    series = series.apply(collapse_whitespace)
    changed = (before != series) & ~(before.isna() & series.isna())
    report["trimmed_values"][col_name] = int(changed.sum())
    return series


def merge_duplicate_columns(df, report):
    seen = {}
    to_drop = []
    for col in df.columns:
        base = col
        if base in seen:
            primary = seen[base]
            df[primary] = df[primary].combine_first(df[base])
            to_drop.append(base)
        else:
            seen[base] = base
    if to_drop:
        report["merged_columns"] = to_drop
        df = df.drop(columns=to_drop)
    return df


def parse_numeric(series, report, col_name):
    if not is_text_series(series):
        return series

    force_numeric = any(key in col_name for key in ["price", "cost", "amount", "qty", "quantity", "tax", "discount", "total"])
    if not force_numeric and "id" in col_name:
        return series
    if not force_numeric and any(key in col_name for key in ["phone", "address", "email", "name", "country", "status", "method", "tag", "note", "product"]):
        return series
    if not force_numeric:
        sample = series.dropna().astype(str).head(200)
        if sample.empty:
            return series
        numeric_like = sample.str.contains(r"[\d]", regex=True).mean()
        if numeric_like < 0.3:
            return series

    cleaned = series.astype(str)
    cleaned = cleaned.str.replace(r"\s+", "", regex=True)
    cleaned = cleaned.str.replace(r"\$", "", regex=True)
    cleaned = cleaned.str.replace(r"usd", "", regex=True)
    cleaned = cleaned.str.replace(r"us\$", "", regex=True)
    cleaned = cleaned.str.replace(r"[^\d,.\-%()]", "", regex=True)
    cleaned = cleaned.str.replace(r"\((.+)\)", r"-\1", regex=True)

    range_mask = cleaned.str.match(r"^\d+(\.\d+)?-\d+(\.\d+)?$", na=False)
    range_vals = cleaned[range_mask].str.split("-", expand=True).astype(float)
    range_avg = range_vals.mean(axis=1)

    percent_mask = cleaned.str.match(r"^-?\d+(\.\d+)?%$", na=False)
    percent_values = pd.to_numeric(cleaned.str.replace("%", ""), errors="coerce")
    percent_values = percent_values / 100.0

    comma_decimal_mask = cleaned.str.match(r"^\d+,\d+$", na=False)
    cleaned = cleaned.where(~comma_decimal_mask, cleaned.str.replace(",", ".", regex=False))
    cleaned = cleaned.str.replace(r",", "", regex=True)

    numeric_values = pd.to_numeric(cleaned, errors="coerce")
    if range_mask.any():
        numeric_values[range_mask] = range_avg.values
        report["ranges_normalized"][col_name] = int(range_mask.sum())
    parsed_count = numeric_values.notna().sum()
    percent_count = percent_mask.sum()

    total_non_null = series.notna().sum()
    if total_non_null == 0:
        return series

    threshold = 0.3 if force_numeric else 0.6
    if (parsed_count + percent_count) / total_non_null >= threshold:
        numeric_values[percent_mask] = percent_values[percent_mask]
        report["numeric_parsed"][col_name] = int(parsed_count + percent_count)
        return numeric_values

    return series


def parse_dates(series, report, col_name):
    if not is_text_series(series):
        return series

    sample = series.dropna().astype(str).head(200)
    if sample.empty:
        return series

    force_date = "date" in col_name or "time" in col_name
    if not force_date:
        date_like = sample.str.contains(
            r"(?:\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})|(?:\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})|(?:[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})",
            regex=True,
        ).mean()
        if date_like < 0.3:
            return series

    parsed_values = []
    parsed_count = 0
    total_non_null = series.notna().sum()
    for v in series:
        if pd.isna(v):
            parsed_values.append(pd.NaT)
            continue
        if isinstance(v, str) and v.strip().lower() in NULL_TOKENS:
            parsed_values.append(pd.NaT)
            continue
        if isinstance(v, str):
            v_clean = collapse_whitespace(v)
        else:
            v_clean = v
        try:
            dt = date_parser.parse(str(v_clean), dayfirst=False, fuzzy=True)
            parsed_values.append(dt)
            parsed_count += 1
        except Exception:
            try:
                dt = date_parser.parse(str(v_clean), dayfirst=True, fuzzy=True)
                parsed_values.append(dt)
                parsed_count += 1
            except Exception:
                parsed_values.append(pd.NaT if force_date else v)

    if total_non_null == 0:
        return series

    threshold = 0.3 if force_date else 0.6
    if parsed_count / total_non_null < threshold:
        return series

    parsed = pd.to_datetime(parsed_values, errors="coerce")
    report["dates_parsed"][col_name] = int(parsed.notna().sum())
    return parsed


def normalize_emails(series, report, col_name):
    if not is_text_series(series):
        return series
    if "email" not in col_name:
        return series
    before = series.copy()
    series = series.apply(lambda v: collapse_whitespace(v).lower() if isinstance(v, str) else v)
    changed = (before != series) & ~(before.isna() & series.isna())
    report["emails_normalized"][col_name] = int(changed.sum())
    return series


def normalize_phones(series, report, col_name):
    if not is_text_series(series):
        return series
    if "phone" not in col_name and "tel" not in col_name:
        return series
    before = series.copy()

    def clean_phone(v):
        if not isinstance(v, str):
            return v
        digits = re.sub(r"\D+", "", v)
        return digits if len(digits) >= 7 else collapse_whitespace(v)

    series = series.apply(clean_phone)
    changed = (before != series) & ~(before.isna() & series.isna())
    report["phones_normalized"][col_name] = int(changed.sum())
    return series


def normalize_codes(series, report, col_name):
    if not is_text_series(series):
        return series
    if any(key in col_name for key in ["currency", "code", "iso"]):
        before = series.copy()
        series = series.apply(lambda v: v.upper().strip() if isinstance(v, str) else v)
        changed = (before != series) & ~(before.isna() & series.isna())
        report["codes_normalized"][col_name] = int(changed.sum())
        return series
    return series


def normalize_names(series, report, col_name):
    if not is_text_series(series):
        return series
    if any(key in col_name for key in ["name", "customer", "client"]) and "id" not in col_name:
        before = series.copy()
        series = series.apply(lambda v: v.title() if isinstance(v, str) else v)
        changed = (before != series) & ~(before.isna() & series.isna())
        report["names_normalized"][col_name] = int(changed.sum())
        return series
    return series


def normalize_tags(series, report, col_name):
    if not is_text_series(series):
        return series
    if "tag" not in col_name and "label" not in col_name and "category" not in col_name:
        return series
    before = series.copy()

    def clean_tags(v):
        if not isinstance(v, str):
            return v
        parts = [p.strip().lower() for p in TAG_SEPARATORS.split(v) if p.strip()]
        return ";".join(parts) if parts else v

    series = series.apply(clean_tags)
    changed = (before != series) & ~(before.isna() & series.isna())
    report["tags_normalized"][col_name] = int(changed.sum())
    return series


def normalize_status(series, report, col_name):
    if not is_text_series(series):
        return series
    if "status" not in col_name:
        return series
    before = series.copy()
    series = series.apply(lambda v: collapse_whitespace(v).lower() if isinstance(v, str) else v)
    changed = (before != series) & ~(before.isna() & series.isna())
    report["status_normalized"][col_name] = int(changed.sum())
    return series


def remove_exact_duplicates(df, report):
    before = len(df)
    df = df.drop_duplicates()
    report["duplicate_rows_removed"] = int(before - len(df))
    return df


def clean_dataframe(df):
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "column_mapping": {},
        "nulls_normalized": {},
        "trimmed_values": {},
        "numeric_parsed": {},
        "ranges_normalized": {},
        "dates_parsed": {},
        "emails_normalized": {},
        "phones_normalized": {},
        "codes_normalized": {},
        "names_normalized": {},
        "tags_normalized": {},
        "status_normalized": {},
        "merged_columns": [],
        "duplicate_rows_removed": 0,
    }

    # Normalize column names
    mapping = {c: normalize_column_name(c) for c in df.columns}
    report["column_mapping"] = mapping
    df = df.rename(columns=mapping)

    # Merge duplicate columns created by normalization
    df = merge_duplicate_columns(df, report)

    # Clean per-column
    for col in df.columns:
        series = df[col]
        series = normalize_nulls(series, report, col)
        series = trim_strings(series, report, col)
        series = normalize_emails(series, report, col)
        series = normalize_phones(series, report, col)
        series = normalize_codes(series, report, col)
        series = normalize_names(series, report, col)
        series = normalize_tags(series, report, col)
        series = normalize_status(series, report, col)
        series = parse_dates(series, report, col)
        series = parse_numeric(series, report, col)
        df[col] = series

    df = remove_exact_duplicates(df, report)

    return df, report


def write_report(report, json_path, text_path):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(text_path, "w", encoding="utf-8") as f:
        f.write("Generic cleaning report\n")
        f.write(f"Generated at: {report['generated_at']}\n\n")
        f.write("Column mapping (original -> cleaned):\n")
        for k, v in report["column_mapping"].items():
            f.write(f"- {k} -> {v}\n")
        f.write("\nCounts by category:\n")
        for key in [
            "nulls_normalized",
            "trimmed_values",
            "numeric_parsed",
            "ranges_normalized",
            "dates_parsed",
            "emails_normalized",
            "phones_normalized",
            "codes_normalized",
            "names_normalized",
            "tags_normalized",
            "status_normalized",
        ]:
            f.write(f"\n{key}:\n")
            for col, count in report[key].items():
                f.write(f"- {col}: {count}\n")
        f.write(f"\nMerged columns: {report['merged_columns']}\n")
        f.write(f"Duplicate rows removed: {report['duplicate_rows_removed']}\n")


def main():
    parser = argparse.ArgumentParser(description="Generic data cleaning for messy CSVs.")
    parser.add_argument("input", nargs="?", default="shopify_dirty_data.csv", help="Input CSV file")
    parser.add_argument("output", nargs="?", default="shopify_clean_data.csv", help="Output cleaned CSV file")
    parser.add_argument("--report-json", default=None, help="JSON report output")
    parser.add_argument("--report-text", default=None, help="Text report output")
    args = parser.parse_args()

    df = pd.read_csv(args.input, dtype=str)
    cleaned, report = clean_dataframe(df)

    cleaned.to_csv(args.output, index=False)
    output_dir = os.path.dirname(os.path.abspath(args.output)) or "."
    report_json = args.report_json or os.path.join(output_dir, "clean_report.json")
    report_text = args.report_text or os.path.join(output_dir, "clean_report.txt")
    write_report(report, report_json, report_text)

    print(f"Cleaned data written to: {args.output}")
    print(f"Reports written to: {report_json}, {report_text}")


if __name__ == "__main__":
    main()
