variable "project_name" {
  type    = string
  default = "payjack-ai-companion"
}

variable "tf_state_bucket_name" {
  type = string
}

variable "tf_lock_table_name" {
  type = string
}

variable "ecr_repository_name" {
  type    = string
  default = "payjack-ai-companion-backend"
}

variable "tags" {
  type    = map(string)
  default = {}
}
