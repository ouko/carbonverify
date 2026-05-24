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

variable "vpc_cidr" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "instance_class" {
  type    = string
  default = "db.t3.medium"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "max_allocated_storage" {
  type    = number
  default = 100
}

variable "db_name" {
  type    = string
  default = "carbonverify"
}

variable "db_username" {
  type    = string
  default = "carbonverify"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "common_tags" {
  type = map(string)
}
