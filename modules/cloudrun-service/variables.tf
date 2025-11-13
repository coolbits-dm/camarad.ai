variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "Region for Cloud Run"
}

variable "service_name" {
  type        = string
  description = "Name of the Cloud Run service"
}

variable "image" {
  type        = string
  description = "Container image"
}

variable "env" {
  type        = map(string)
  default     = {}
  description = "Environment variables"
}

variable "ingress" {
  type    = string
  default = "all"
}

variable "vpc_connector" {
  type    = string
  default = null
}

variable "vpc_egress" {
  type    = string
  default = "all-traffic"
}
