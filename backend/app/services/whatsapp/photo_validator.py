"""Photo validation for WhatsApp uploads: GPS, quality, boundary checks."""

import io
from typing import Any, Dict, Optional

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from app.core.logging import get_logger

logger = get_logger(__name__)

MIN_IMAGE_WIDTH = 640
MIN_IMAGE_HEIGHT = 480
MIN_FILE_SIZE_KB = 50
MAX_FILE_SIZE_MB = 10


class PhotoValidator:
    """Validates photos uploaded via WhatsApp for MRV data collection."""

    def validate(self, image_bytes: bytes, project_boundary: Optional[Dict] = None) -> Dict[str, Any]:
        """Run all validation checks on an image."""
        checks = {
            "format_valid": False,
            "size_valid": False,
            "quality_valid": False,
            "gps_present": False,
            "gps_valid": False,
            "inside_boundary": True,  # Default pass if no boundary provided
            "errors": [],
            "metadata": {},
        }

        # 1. File size check
        size_kb = len(image_bytes) / 1024
        size_mb = size_kb / 1024
        checks["metadata"]["file_size_kb"] = round(size_kb, 2)

        if size_kb < MIN_FILE_SIZE_KB:
            checks["errors"].append(f"Image too small ({size_kb:.0f} KB). Minimum: {MIN_FILE_SIZE_KB} KB")
        elif size_mb > MAX_FILE_SIZE_MB:
            checks["errors"].append(f"Image too large ({size_mb:.1f} MB). Maximum: {MAX_FILE_SIZE_MB} MB")
        else:
            checks["size_valid"] = True

        # 2. Format and dimensions
        try:
            img = Image.open(io.BytesIO(image_bytes))
            checks["metadata"]["format"] = img.format
            checks["metadata"]["width"] = img.width
            checks["metadata"]["height"] = img.height
            checks["metadata"]["mode"] = img.mode

            if img.width < MIN_IMAGE_WIDTH or img.height < MIN_IMAGE_HEIGHT:
                checks["errors"].append(
                    f"Image resolution too low ({img.width}x{img.height}). "
                    f"Minimum: {MIN_IMAGE_WIDTH}x{MIN_IMAGE_HEIGHT}"
                )
            else:
                checks["quality_valid"] = True

            checks["format_valid"] = True

            # 3. GPS extraction
            gps = self._extract_gps(img)
            if gps:
                checks["gps_present"] = True
                checks["metadata"]["gps_latitude"] = gps["latitude"]
                checks["metadata"]["gps_longitude"] = gps["longitude"]

                # Validate GPS coordinates are in valid range
                if -90 <= gps["latitude"] <= 90 and -180 <= gps["longitude"] <= 180:
                    checks["gps_valid"] = True
                else:
                    checks["errors"].append("GPS coordinates are out of valid range")

                # 4. Boundary check
                if project_boundary and checks["gps_valid"]:
                    inside = self._check_boundary(
                        gps["latitude"], gps["longitude"], project_boundary
                    )
                    checks["inside_boundary"] = inside
                    if not inside:
                        checks["errors"].append("Photo location is outside project boundary")
            else:
                checks["errors"].append("GPS location missing from photo. Please enable location services.")

            # 5. Timestamp check
            timestamp = self._extract_timestamp(img)
            if timestamp:
                checks["metadata"]["timestamp"] = timestamp

            img.close()

        except Exception as exc:
            checks["errors"].append(f"Could not process image: {str(exc)}")
            logger.error("photo_validation_error", error=str(exc))

        # Overall validity
        checks["valid"] = (
            checks["format_valid"]
            and checks["size_valid"]
            and checks["quality_valid"]
            and checks["gps_valid"]
            and checks["inside_boundary"]
            and len(checks["errors"]) == 0
        )

        return checks

    def _extract_gps(self, img: Image.Image) -> Optional[Dict[str, float]]:
        """Extract GPS coordinates from EXIF data."""
        try:
            exif = img._getexif()
            if not exif:
                return None

            gps_info = {}
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == "GPSInfo":
                    for key in value:
                        sub_tag = GPSTAGS.get(key, key)
                        gps_info[sub_tag] = value[key]

            if not gps_info:
                return None

            lat = self._convert_dms(gps_info.get("GPSLatitude"), gps_info.get("GPSLatitudeRef"))
            lon = self._convert_dms(gps_info.get("GPSLongitude"), gps_info.get("GPSLongitudeRef"))

            if lat is not None and lon is not None:
                return {"latitude": lat, "longitude": lon}
        except Exception as exc:
            logger.debug("gps_extraction_failed", error=str(exc))

        return None

    def _convert_dms(self, dms, ref) -> Optional[float]:
        """Convert degrees/minutes/seconds to decimal degrees."""
        if not dms or not ref:
            return None
        try:
            degrees = float(dms[0])
            minutes = float(dms[1])
            seconds = float(dms[2])
            decimal = degrees + minutes / 60 + seconds / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return round(decimal, 6)
        except (TypeError, IndexError, ZeroDivisionError):
            return None

    def _extract_timestamp(self, img: Image.Image) -> Optional[str]:
        """Extract timestamp from EXIF data."""
        try:
            exif = img._getexif()
            if exif:
                for tag_id, value in exif.items():
                    if TAGS.get(tag_id) == "DateTimeOriginal":
                        return str(value)
        except Exception:
            logger.debug("exif_extraction_failed", exc_info=True)
        return None

    def _check_boundary(self, lat: float, lon: float, boundary: Dict) -> bool:
        """Check if coordinates are inside project boundary (simple bounding box)."""
        try:
            min_lat = boundary.get("min_latitude")
            max_lat = boundary.get("max_latitude")
            min_lon = boundary.get("min_longitude")
            max_lon = boundary.get("max_longitude")

            if all(v is not None for v in [min_lat, max_lat, min_lon, max_lon]):
                return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

            # Fallback: check against center + radius
            center_lat = boundary.get("center_latitude")
            center_lon = boundary.get("center_longitude")
            radius_km = boundary.get("radius_km", 10)

            if center_lat is not None and center_lon is not None:
                from math import radians, sin, cos, sqrt, atan2
                R = 6371  # Earth radius in km
                lat1, lon1 = radians(center_lat), radians(center_lon)
                lat2, lon2 = radians(lat), radians(lon)
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                distance = R * c
                return distance <= radius_km

        except Exception as exc:
            logger.error("boundary_check_error", error=str(exc))

        return True  # Pass if boundary check fails


# Global singleton
photo_validator = PhotoValidator()
