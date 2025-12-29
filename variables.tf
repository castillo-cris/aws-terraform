############################################
# variables.tf
############################################

variable "aws_region" {
  type        = string
  description = "Región AWS"
  default     = "us-east-2"
}

variable "project_name" {
  type        = string
  description = "Nombre del proyecto"
  default     = "ml-infer-free-tier"
}

