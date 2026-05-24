resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project_name}-uploads-${var.environment}-${var.account_id}"

  tags = var.common_tags
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "backups" {
  bucket = "${var.project_name}-backups-${var.environment}-${var.account_id}"

  tags = var.common_tags
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_replication_configuration" "backups" {
  count  = var.environment == "production" ? 1 : 0
  role   = aws_iam_role.replication[0].arn
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "cross-region-replication"
    status = "Enabled"

    destination {
      bucket        = aws_s3_bucket.backups_replica[0].arn
      storage_class = "STANDARD_IA"
    }
  }
}

resource "aws_s3_bucket" "backups_replica" {
  count    = var.environment == "production" ? 1 : 0
  provider = aws.replica
  bucket   = "${var.project_name}-backups-${var.environment}-${var.account_id}-replica"

  tags = var.common_tags
}
