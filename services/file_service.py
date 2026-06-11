import os
import logging
import requests

logger = logging.getLogger(__name__)

S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_RECORDING_PREFIX = "recordings"


def _get_s3_client():
    if not S3_BUCKET:
        return None
    try:
        import boto3
        from botocore.config import Config as BotocoreConfig

        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        endpoint = os.environ.get("S3_ENDPOINT", "").strip() or None
        region = os.environ.get("AWS_REGION", "us-east-1")

        config = BotocoreConfig(s3={"addressing_style": "path"})
        kwargs = dict(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=config,
        )
        if endpoint:
            kwargs["endpoint_url"] = endpoint

        return boto3.client("s3", **kwargs)
    except Exception as e:
        logger.warning(f"S3 client init failed: {e}")
        return None


def upload_recording(recording_id: str, source_url: str) -> str | None:
    """Download audio from source_url and upload to S3.

    Returns the permanent S3 URL on success, or None on failure.
    The S3 key is: recordings/{recording_id}.mp3
    """
    client = _get_s3_client()
    if not client:
        logger.warning("S3 not configured — skipping upload")
        return None

    key = f"{S3_RECORDING_PREFIX}/{recording_id}.mp3"

    try:
        logger.info(f"Downloading recording {recording_id} from Telnyx S3...")
        response = requests.get(source_url, timeout=60)
        response.raise_for_status()
        audio_bytes = response.content
        logger.info(f"Downloaded {len(audio_bytes)} bytes for recording {recording_id}")
    except Exception as e:
        logger.error(f"Failed to download recording {recording_id}: {e}")
        return None

    try:
        client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=audio_bytes,
            ContentType="audio/mpeg",
        )
        logger.info(f"Uploaded recording {recording_id} to s3://{S3_BUCKET}/{key}")
    except Exception as e:
        logger.error(f"Failed to upload recording {recording_id} to S3: {e}")
        return None

    try:
        # Generate a long-lived presigned URL (7 days)
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=7 * 24 * 3600,
        )
        return url
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for {key}: {e}")
        # Fall back to path-style public URL
        endpoint = os.environ.get("S3_ENDPOINT", "").strip()
        if endpoint:
            return f"{endpoint}/{S3_BUCKET}/{key}"
        return f"https://{S3_BUCKET}.s3.amazonaws.com/{key}"


def get_recording_url(recording_id: str, expiry_seconds: int = 3600) -> str | None:
    """Generate a fresh presigned GET URL for a stored recording.

    Returns the presigned URL, or None if S3 is not configured or the object doesn't exist.
    """
    client = _get_s3_client()
    if not client:
        logger.warning("S3 not configured — cannot generate presigned URL")
        return None

    key = f"{S3_RECORDING_PREFIX}/{recording_id}.mp3"

    try:
        # Verify the object exists before generating a URL
        client.head_object(Bucket=S3_BUCKET, Key=key)
    except Exception as e:
        logger.error(f"Recording {recording_id} not found in S3: {e}")
        return None

    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expiry_seconds,
        )
        return url
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for {key}: {e}")
        return None


