variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "domain" {
  type        = string
  description = "Primary domain (example.com)"
}

variable "api_domain" {
  type        = string
  description = "API subdomain (api.example.com)"
}

variable "backend_service_name" {
  type        = string
  description = "Name of the backend Cloud Run service"
}

variable "frontend_service_name" {
  type        = string
  description = "Name of the frontend Cloud Run service"
}

variable "region" {
  type        = string
  description = "Region for Cloud Run services"
}
