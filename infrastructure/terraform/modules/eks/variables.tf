variable "project_name" {
  type    = string
  default = "carbonverify"
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 5
}

variable "instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}

variable "github_actions_role_arn" {
  type    = string
  default = ""
}

variable "common_tags" {
  type = map(string)
}
