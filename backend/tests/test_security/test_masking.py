from app.security.masking import (
    mask_gps,
    mask_id,
    mask_email,
    mask_phone,
    mask_field,
    mask_data,
    mask_survey_response,
)
from app.models import UserRoleEnum


class TestDataMasking:
    def test_mask_gps_precision(self):
        assert mask_gps(1.234567, precision=2) == 1.23
        assert mask_gps(1.234567, precision=1) == 1.2
        assert mask_gps(None, precision=2) is None

    def test_mask_id(self):
        assert mask_id("HH-12345", visible_chars=4) == "****2345"
        assert mask_id("AB", visible_chars=4) == "**"
        assert mask_id(None) is None

    def test_mask_email(self):
        assert mask_email("john@example.com") == "j***@example.com"
        assert mask_email("a@b.com") == "*@b.com"
        assert mask_email(None) is None

    def test_mask_phone(self):
        assert mask_phone("+254712345678", visible=3) == "*********678"
        assert mask_phone("123", visible=3) == "***"
        assert mask_phone(None) is None

    def test_mask_field_admin_unmasked(self):
        """Admin should see all fields unmasked."""
        result = mask_field("gps_latitude", 1.234567, UserRoleEnum.admin)
        assert result == 1.234567

    def test_mask_field_operator_gps(self):
        """Operator should see GPS at 2 decimal places."""
        result = mask_field("gps_latitude", 1.234567, UserRoleEnum.operator)
        assert result == 1.23

    def test_mask_field_developer_gps(self):
        """Developer should see GPS at 1 decimal place."""
        result = mask_field("gps_latitude", 1.234567, UserRoleEnum.developer)
        assert result == 1.2

    def test_mask_field_viewer_gps(self):
        """Viewer should not see GPS."""
        result = mask_field("gps_latitude", 1.234567, UserRoleEnum.viewer)
        assert result is None

    def test_mask_field_household_id(self):
        result_dev = mask_field("household_id", "HH-12345", UserRoleEnum.developer)
        assert result_dev == "****2345"

        result_viewer = mask_field("household_id", "HH-12345", UserRoleEnum.viewer)
        assert result_viewer == "******45"

    def test_mask_field_email(self):
        result = mask_field("email", "test@example.com", UserRoleEnum.developer)
        assert result == "t***@example.com"

    def test_mask_field_phone(self):
        result = mask_field("phone_number", "+254712345678", UserRoleEnum.developer)
        assert result == "*********678"

    def test_mask_data_dictionary(self):
        data = {
            "gps_latitude": 1.234,
            "gps_longitude": 5.678,
            "household_id": "HH-001",
            "status": "active",
        }
        result = mask_data(data, UserRoleEnum.viewer)
        assert result["gps_latitude"] is None
        assert result["gps_longitude"] is None
        assert result["household_id"] == "****01"
        assert result["status"] == "active"

    def test_mask_survey_response(self):
        response = {
            "gps_latitude": 1.234,
            "gps_longitude": 5.678,
            "household_id": "HH-001",
            "village_name": "Kisumu",
            "fuel_type": "charcoal",
        }
        result = mask_survey_response(response, UserRoleEnum.viewer)
        assert result["gps_latitude"] is None
        assert result["village_name"] == "[REDACTED]"
        assert result["fuel_type"] == "charcoal"
