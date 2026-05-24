terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "${var.project_name}-${var.environment}"
  cluster_version = "1.29"

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
  }

  eks_managed_node_groups = {
    general = {
      desired_size = var.node_desired_size
      min_size     = var.node_min_size
      max_size     = var.node_max_size

      instance_types = var.instance_types
      capacity_type  = var.environment == "production" ? "ON_DEMAND" : "SPOT"

      disk_size = 50

      labels = {
        workload = "general"
      }

      update_config = {
        max_unavailable_percentage = 25
      }

      tags = var.common_tags
    }
  }

  manage_aws_auth_configmap = true
  aws_auth_roles = [
    {
      rolearn  = var.github_actions_role_arn
      username = "github-actions"
      groups   = ["system:masters"]
    }
  ]

  tags = var.common_tags
}

# IRSA for AWS Load Balancer Controller
module "lb_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name                              = "${var.project_name}-${var.environment}-lb-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }

  tags = var.common_tags
}

# IRSA for Cluster Autoscaler
module "cluster_autoscaler_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name                        = "${var.project_name}-${var.environment}-cluster-autoscaler"
  attach_cluster_autoscaler_policy = true
  cluster_autoscaler_cluster_names = [module.eks.cluster_name]

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:cluster-autoscaler"]
    }
  }

  tags = var.common_tags
}

# IRSA for External DNS
module "external_dns_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name                  = "${var.project_name}-${var.environment}-external-dns"
  attach_external_dns_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:external-dns"]
    }
  }

  tags = var.common_tags
}
