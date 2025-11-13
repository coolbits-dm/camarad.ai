resource "google_cloud_run_v2_service" "service" {
  name     = var.service_name
  location = var.region
  project  = var.project_id

  ingress = var.ingress

  template {
    containers {
      image = var.image

      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }
    }

    dynamic "vpc_access" {
      for_each = var.vpc_connector != null ? [var.vpc_connector] : []
      content {
        connector = var.vpc_connector
        egress    = var.vpc_egress
      }
    }
  }
}
