import io
from datetime import datetime
from typing import Dict, Any, List, Optional

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from app.core.logging import get_logger
from app.models import ImageCategoryEnum

logger = get_logger(__name__)

IMAGE_CATEGORY_PATTERNS = {
    ImageCategoryEnum.stove_installation: [
        "installation", "installed", "setup", "deployed", "stove install"
    ],
    ImageCategoryEnum.kpt_weighing: [
        "weigh", "weight", "scale", "kpt", "kitchen performance", "fuel weight"
    ],
    ImageCategoryEnum.stove_condition: [
        "condition", "damage", "wear", "broken", "repair", "maintenance"
    ],
    ImageCategoryEnum.enumerator_verification: [
        "enumerator", "surveyor", "interview", "household visit", "verification"
    ],
}


def extract_exif(image: Image.Image) -> Dict[str, Any]:
    """Extract EXIF data from image."""
    exif_data = {}
    try:
        raw_exif = image._getexif()
        if raw_exif:
            for tag_id, value in raw_exif.items():
                tag_name = TAGS.get(tag_id, tag_id)
                exif_data[tag_name] = value
    except Exception as e:
        logger.warning("exif_extraction_failed", error=str(e))
    return exif_data


def extract_gps(exif_data: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Extract GPS coordinates from EXIF data."""
    gps_info = exif_data.get("GPSInfo")
    if not gps_info:
        return None

    try:
        gps_data = {}
        for key in gps_info.keys():
            decode = GPSTAGS.get(key, key)
            gps_data[decode] = gps_info[key]

        def convert_to_degrees(value):
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)

        lat = None
        lon = None

        if "GPSLatitude" in gps_data and "GPSLatitudeRef" in gps_data:
            lat = convert_to_degrees(gps_data["GPSLatitude"])
            if gps_data["GPSLatitudeRef"] != "N":
                lat = -lat

        if "GPSLongitude" in gps_data and "GPSLongitudeRef" in gps_data:
            lon = convert_to_degrees(gps_data["GPSLongitude"])
            if gps_data["GPSLongitudeRef"] != "E":
                lon = -lon

        if lat is not None and lon is not None:
            return {"latitude": lat, "longitude": lon}
    except Exception as e:
        logger.warning("gps_extraction_failed", error=str(e))

    return None


def parse_exif_timestamp(exif_data: Dict[str, Any]) -> Optional[str]:
    """Extract timestamp from EXIF."""
    for key in ["DateTimeOriginal", "DateTime", "DateTimeDigitized"]:
        if key in exif_data:
            try:
                dt_str = exif_data[key]
                # EXIF format: "2024:01:15 10:30:00"
                dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                return dt.isoformat()
            except (ValueError, TypeError):
                continue
    return None


def classify_image_category(filename: str, exif_data: Dict[str, Any]) -> ImageCategoryEnum:
    """Classify image category based on filename and metadata."""
    filename_lower = filename.lower()
    scores = {}
    for category, keywords in IMAGE_CATEGORY_PATTERNS.items():
        score = sum(1 for kw in keywords if kw in filename_lower)
        scores[category] = score

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return ImageCategoryEnum.other
    return best


def validate_gps_boundary(
    gps: Dict[str, float], project_boundary: Optional[List[List[float]]] = None
) -> List[str]:
    """Validate GPS coordinates against project boundary."""
    errors = []
    lat = gps.get("latitude")
    lon = gps.get("longitude")

    if lat is None or lon is None:
        errors.append("GPS coordinates missing")
        return errors

    if not (-90 <= lat <= 90):
        errors.append(f"Latitude {lat} out of range [-90, 90]")
    if not (-180 <= lon <= 180):
        errors.append(f"Longitude {lon} out of range [-180, 180]")
    if abs(lat) < 0.01 and abs(lon) < 0.01:
        errors.append("GPS coordinates appear invalid (near 0,0)")

    if project_boundary:
        try:
            from shapely.geometry import Point, Polygon
            point = Point(lon, lat)
            polygon = Polygon(project_boundary)
            if not polygon.contains(point):
                errors.append("GPS coordinates outside project boundary")
        except Exception as e:
            logger.warning("boundary_check_failed", error=str(e))

    return errors


def validate_timestamp(
    timestamp_str: Optional[str],
    monitoring_period_start: Optional[datetime] = None,
    monitoring_period_end: Optional[datetime] = None,
) -> List[str]:
    """Validate image timestamp against monitoring period."""
    errors = []
    if not timestamp_str:
        errors.append("Image timestamp missing")
        return errors

    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if monitoring_period_start and ts < monitoring_period_start:
            errors.append(f"Image timestamp {ts.date()} before monitoring period start")
        if monitoring_period_end and ts > monitoring_period_end:
            errors.append(f"Image timestamp {ts.date()} after monitoring period end")
    except ValueError:
        errors.append("Could not parse image timestamp")

    return errors


def process_image(
    file_bytes: bytes,
    filename: str,
    project_boundary: Optional[List[List[float]]] = None,
    monitoring_period_start: Optional[datetime] = None,
    monitoring_period_end: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Process image file and return structured result."""
    logger.info("processing_image", filename=filename)

    result = {
        "filename": filename,
        "detected_type": "image",
        "width": None,
        "height": None,
        "format": None,
        "exif": {},
        "gps": None,
        "timestamp": None,
        "camera_model": None,
        "category": ImageCategoryEnum.other.value,
        "validation_errors": [],
    }

    try:
        image = Image.open(io.BytesIO(file_bytes))
        result["width"] = image.width
        result["height"] = image.height
        result["format"] = image.format

        exif = extract_exif(image)
        result["exif"] = {k: str(v) for k, v in exif.items() if k not in ["GPSInfo"]}

        gps = extract_gps(exif)
        if gps:
            result["gps"] = gps
            gps_errors = validate_gps_boundary(gps, project_boundary)
            result["validation_errors"].extend(gps_errors)

        ts = parse_exif_timestamp(exif)
        if ts:
            result["timestamp"] = ts
            ts_errors = validate_timestamp(ts, monitoring_period_start, monitoring_period_end)
            result["validation_errors"].extend(ts_errors)

        camera = exif.get("Model") or exif.get("Make")
        if camera:
            result["camera_model"] = str(camera)

        result["category"] = classify_image_category(filename, exif).value

    except Exception as e:
        logger.error("image_processing_failed", filename=filename, error=str(e))
        result["validation_errors"].append(f"Failed to process image: {str(e)}")

    logger.info(
        "image_processed",
        filename=filename,
        category=result["category"],
        has_gps=result["gps"] is not None,
        has_timestamp=result["timestamp"] is not None,
    )
    return result
