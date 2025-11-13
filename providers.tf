terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.37"
    }
  }

  backend "gcs" {
    bucket = "coolbits-terraform-state"
    prefix = "camarad/terraform"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
