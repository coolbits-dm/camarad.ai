variable "project_id" {}
variable "region" {
  default = "europe-west3"
}
variable "postgres_password" {
  type      = string
  sensitive = true
}
variable "domain" {
  default = "camarad.ai"
}
variable "api_domain" {
  default = "api.camarad.ai"
}
