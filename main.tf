module "artifact_registry" {
  source     = "./modules/artifact-registry"
  project_id = var.project_id
  region     = var.region
}

module "cloudsql" {
  source            = "./modules/cloudsql"
  project_id        = var.project_id
  region            = var.region
  postgres_password = var.postgres_password
}

module "vpc_connector" {
  source     = "./modules/vpc-connector"
  project_id = var.project_id
  region     = var.region
}

module "backend_service" {
  source       = "./modules/cloudrun-service"
  project_id   = var.project_id
  region       = var.region
  service_name = "camarad-backend"
  image        = "europe-west3-docker.pkg.dev/${var.project_id}/camarad/camarad-backend:latest"
  env = {
    DATABASE_URL = module.cloudsql.connection_string
  }
  vpc_connector = module.vpc_connector.name
}

module "frontend_service" {
  source       = "./modules/cloudrun-service"
  project_id   = var.project_id
  region       = var.region
  service_name = "camarad-frontend"
  image        = "europe-west3-docker.pkg.dev/${var.project_id}/camarad/camarad-frontend:latest"
}

module "load_balancer" {
  source       = "./modules/load-balancer"
  project_id   = var.project_id
  domain       = var.domain
  api_domain   = var.api_domain
  backend_service_name  = module.backend_service.name
  frontend_service_name = module.frontend_service.name
  region       = var.region
}
