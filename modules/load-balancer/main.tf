resource "google_compute_global_address" "lb_ip" {
  name    = "${var.project_id}-lb-ip"
  project = var.project_id
}

resource "google_compute_managed_ssl_certificate" "lb_cert" {
  name    = "${var.project_id}-cert"
  project = var.project_id

  managed {
    domains = [
      var.domain,
      var.api_domain
    ]
  }
}

resource "google_compute_network_endpoint_group" "frontend_neg" {
  name                  = "${var.project_id}-frontend-neg"
  project               = var.project_id
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  cloud_run {
    service = var.frontend_service_name
  }
}

resource "google_compute_network_endpoint_group" "api_neg" {
  name                  = "${var.project_id}-api-neg"
  project               = var.project_id
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  cloud_run {
    service = var.backend_service_name
  }
}

resource "google_compute_backend_service" "frontend_backend" {
  name        = "${var.project_id}-frontend-backend"
  project     = var.project_id
  timeout_sec = 30
  backend {
    group = google_compute_network_endpoint_group.frontend_neg.id
  }
}

resource "google_compute_backend_service" "api_backend" {
  name        = "${var.project_id}-api-backend"
  project     = var.project_id
  timeout_sec = 30
  backend {
    group = google_compute_network_endpoint_group.api_neg.id
  }
}

resource "google_compute_url_map" "lb_map" {
  name    = "${var.project_id}-urlmap"
  project = var.project_id

  default_service = google_compute_backend_service.frontend_backend.id

  host_rule {
    hosts        = [var.domain]
    path_matcher = "frontend"
  }

  host_rule {
    hosts        = [var.api_domain]
    path_matcher = "api"
  }

  path_matcher {
    name            = "frontend"
    default_service = google_compute_backend_service.frontend_backend.id
  }

  path_matcher {
    name            = "api"
    default_service = google_compute_backend_service.api_backend.id
  }
}

resource "google_compute_target_https_proxy" "https_proxy" {
  name             = "${var.project_id}-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.lb_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.lb_cert.id]
}

resource "google_compute_global_forwarding_rule" "https_fr" {
  name       = "${var.project_id}-https-fr"
  project    = var.project_id
  port_range = "443"
  target     = google_compute_target_https_proxy.https_proxy.id
  ip_address = google_compute_global_address.lb_ip.id
}
