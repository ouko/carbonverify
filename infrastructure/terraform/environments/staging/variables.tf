variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "github_actions_role_arn" {
  type    = string
  default = ""
}
