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

variable "shared_kb_source_bucket_name" {
  type    = string
  default = null
}

variable "shared_kb_artifacts_bucket_name" {
  type    = string
  default = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
