import io
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
from dateutil import parser as date_parser

from app.core.logging import get_logger

logger = get_logger(__name__)

REQUIRED_COLUMNS = [
    "stove_id",
    "household_id",
    "usage_hours",
    "fuel_consumed_kg",
    "gps_latitude",
    "gps_longitude",
    "timestamp",
]

VALIDATORS = {
    "usage_hours": {"max": 24, "min": 0},
    "fuel_consumed_kg": {"max": 50, "min": 0},
    "gps_latitude": {"max": 90, "min": -90},
    "gps_longitude": {"max": 180, "min": -180},
}


def auto_detect_date_format(series: pd.Series) -> pd.Series:
    """Attempt to parse dates from mixed formats."""
    parsed = []
    for val in series:
        if pd.isna(val):
            parsed.append(pd.NaT)
            continue
        try:
            if isinstance(val, (datetime, pd.Timestamp)):
                parsed.append(pd.Timestamp(val))
            else:
                parsed.append(pd.Timestamp(date_parser.parse(str(val))))
        except Exception:
            parsed.append(pd.NaT)
    return pd.Series(parsed)


def validate_row(row: pd.Series, row_idx: int) -> List[str]:
    """Validate a single row and return list of error messages."""
    errors = []
    for col, bounds in VALIDATORS.items():
        if col not in row.index:
            continue
        val = row[col]
        if pd.isna(val):
            errors.append(f"Row {row_idx}: {col} is missing")
            continue
        try:
            fval = float(val)
            if fval < bounds["min"] or fval > bounds["max"]:
                errors.append(
                    f"Row {row_idx}: {col}={fval} out of range [{bounds['min']}, {bounds['max']}]"
                )
        except (ValueError, TypeError):
            errors.append(f"Row {row_idx}: {col} has invalid value '{val}'")

    # GPS coordinate sanity check
    lat = row.get("gps_latitude")
    lon = row.get("gps_longitude")
    if not pd.isna(lat) and not pd.isna(lon):
        lat_f = float(lat)
        lon_f = float(lon)
        if abs(lat_f) < 0.01 and abs(lon_f) < 0.01:
            errors.append(f"Row {row_idx}: GPS coordinates ({lat_f}, {lon_f}) appear invalid (near 0,0)")

    return errors


def process_excel_csv(file_bytes: bytes, detected_type: str, filename: str) -> Dict[str, Any]:
    """Process Excel or CSV file and return structured result."""
    logger.info("processing_excel_csv", filename=filename, detected_type=detected_type)

    result = {
        "filename": filename,
        "detected_type": detected_type,
        "total_rows": 0,
        "valid_rows": 0,
        "invalid_rows": 0,
        "columns": [],
        "missing_columns": [],
        "data": [],
        "validation_errors": [],
        "data_types": {},
    }

    try:
        if detected_type == "excel":
            df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
        elif detected_type == "csv":
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            raise ValueError(f"Unsupported type: {detected_type}")
    except Exception as e:
        logger.error("parse_failed", filename=filename, error=str(e))
        result["validation_errors"].append(f"Failed to parse file: {str(e)}")
        return result

    result["total_rows"] = len(df)
    result["columns"] = list(df.columns)

    # Check required columns
    result["missing_columns"] = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if result["missing_columns"]:
        result["validation_errors"].append(
            f"Missing required columns: {', '.join(result['missing_columns'])}"
        )

    # Auto-detect data types
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            result["data_types"][col] = "datetime"
        elif pd.api.types.is_numeric_dtype(df[col]):
            result["data_types"][col] = "numeric"
        else:
            result["data_types"][col] = "text"

    # Auto-detect headers if first row looks like data
    if len(df) > 0:
        first_row = df.iloc[0]
        numeric_count = sum(1 for v in first_row if pd.api.types.is_number(v))
        if numeric_count >= 3:
            result["header_detected"] = True
        else:
            result["header_detected"] = False

    # Parse timestamp column
    if "timestamp" in df.columns:
        df["timestamp_parsed"] = auto_detect_date_format(df["timestamp"])
        unparsed = df["timestamp_parsed"].isna().sum()
        if unparsed > 0:
            result["validation_errors"].append(f"Could not parse {unparsed} timestamp values")

    # Validate each row
    for idx, row in df.iterrows():
        row_errors = validate_row(row, idx)
        if row_errors:
            result["validation_errors"].extend(row_errors)
            result["invalid_rows"] += 1
        else:
            result["valid_rows"] += 1

        # Store sample data (first 100 rows)
        if idx < 100:
            record = {}
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    record[col] = None
                elif isinstance(val, (pd.Timestamp, datetime)):
                    record[col] = val.isoformat()
                else:
                    record[col] = val
            result["data"].append(record)

    logger.info(
        "excel_csv_processed",
        filename=filename,
        total_rows=result["total_rows"],
        valid_rows=result["valid_rows"],
        invalid_rows=result["invalid_rows"],
    )
    return result
