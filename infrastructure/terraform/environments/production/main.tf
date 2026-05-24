terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "carbonverify-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "carbonverify-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "carbonverify"
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}

provider "aws" {
  alias  = "replica"
  region = "us-west-2"
}

data "aws_caller_identity" "current" {}

module "vpc" {
  source = "../../modules/vpc"

  environment    = "production"
  vpc_cidr       = "10.0.0.0/16"
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

module "eks" {
  source = "../../modules/eks"

  environment             = "production"
  vpc_id                  = module.vpc.vpc_id
  private_subnet_ids      = module.vpc.private_subnet_ids
  node_desired_size       = 3
  node_min_size           = 2
  node_max_size           = 10
  instance_types          = ["t3.large", "t3.xlarge"]
  github_actions_role_arn = var.github_actions_role_arn
}

module "rds" {
  source = "../../modules/rds"

  environment           = "production"
  vpc_id                = module.vpc.vpc_id
  vpc_cidr              = module.vpc.vpc_cidr
  private_subnet_ids    = module.vpc.private_subnet_ids
  instance_class        = "db.r6g.large"
  allocated_storage     = 100
  max_allocated_storage = 500
  db_password           = var.db_password
}

module "elasticache" {
  source = "../../modules/elasticache"

  environment        = "production"
  vpc_id             = module.vpc.vpc_id
  vpc_cidr           = module.vpc.vpc_cidr
  private_subnet_ids = module.vpc.private_subnet_ids
  node_type          = "cache.r6g.large"
}

module "s3" {
  source = "../../modules/s3"

  environment = "production"
  account_id  = data.aws_caller_identity.current.account_id
}

module "ecr" {
  source = "../../modules/ecr"

  environment = "production"
}
