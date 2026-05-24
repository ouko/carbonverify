variable "project_name" {
  type    = string
  default = "carbonverify"
}

variable "environment" {
  type = string
}

variable "common_tags" {
  type = map(string)
}
