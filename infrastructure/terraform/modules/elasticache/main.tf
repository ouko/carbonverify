resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.project_name}-${var.environment}-redis-"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = var.common_tags
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.project_name}-${var.environment}"
  description          = "Redis cluster for ${var.project_name}"

  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.node_type
  num_cache_clusters   = var.environment == "production" ? 2 : 1
  automatic_failover_enabled = var.environment == "production"
  multi_az_enabled     = var.environment == "production"

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  snapshot_retention_limit = var.environment == "production" ? 7 : 1
  snapshot_window          = "05:00-06:00"

  tags = var.common_tags
}
