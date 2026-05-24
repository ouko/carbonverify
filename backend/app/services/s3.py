import boto3
from botocore.exceptions import ClientError
from datetime import timedelta
from app.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        )
    return _s3_client


def generate_presigned_url(object_name: str, expiration: int = 3600, method: str = "get_object") -> str:
    try:
        client = get_s3_client()
        url = client.generate_presigned_url(
            method,
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": object_name},
            ExpiresIn=expiration,
        )
        return url
    except ClientError as e:
        logger.error("s3_presign_error", error=str(e), object_name=object_name)
        raise


def generate_upload_presigned_url(object_name: str, content_type: str = "application/pdf", expiration: int = 3600) -> str:
    try:
        client = get_s3_client()
        url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": object_name,
                "ContentType": content_type,
            },
            ExpiresIn=expiration,
        )
        return url
    except ClientError as e:
        logger.error("s3_upload_presign_error", error=str(e), object_name=object_name)
        raise


def upload_bytes(file_bytes: bytes, s3_key: str, content_type: str = "application/octet-stream") -> str:
    """Upload bytes directly to S3 and return the S3 key."""
    try:
        client = get_s3_client()
        client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        logger.info("s3_upload_success", bucket=settings.S3_BUCKET_NAME, key=s3_key, size=len(file_bytes))
        return s3_key
    except ClientError as e:
        logger.error("s3_upload_error", error=str(e), key=s3_key)
        raise
