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
    key            = "staging/terraform.tfstate"
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
      Environment = "staging"
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

module "vpc" {
  source = "../../modules/vpc"

  environment     = "staging"
  vpc_cidr        = "10.1.0.0/16"
  private_subnets = ["10.1.1.0/24", "10.1.2.0/24"]
  public_subnets  = ["10.1.101.0/24", "10.1.102.0/24"]
}

module "eks" {
  source = "../../modules/eks"

  environment             = "staging"
  vpc_id                  = module.vpc.vpc_id
  private_subnet_ids      = module.vpc.private_subnet_ids
  node_desired_size       = 2
  node_min_size           = 1
  node_max_size           = 4
  instance_types          = ["t3.medium"]
  github_actions_role_arn = var.github_actions_role_arn
}

module "rds" {
  source = "../../modules/rds"

  environment           = "staging"
  vpc_id                = module.vpc.vpc_id
  vpc_cidr              = module.vpc.vpc_cidr
  private_subnet_ids    = module.vpc.private_subnet_ids
  instance_class        = "db.t3.medium"
  allocated_storage     = 20
  max_allocated_storage = 100
  db_password           = var.db_password
}

module "elasticache" {
  source = "../../modules/elasticache"

  environment        = "staging"
  vpc_id             = module.vpc.vpc_id
  vpc_cidr           = module.vpc.vpc_cidr
  private_subnet_ids = module.vpc.private_subnet_ids
  node_type          = "cache.t3.micro"
}

module "s3" {
  source = "../../modules/s3"

  environment = "staging"
  account_id  = data.aws_caller_identity.current.account_id
}

module "ecr" {
  source = "../../modules/ecr"

  environment = "staging"
}
