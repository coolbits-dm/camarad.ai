output "id" {
  value       = google_artifact_registry_repository.repository.id
  description = "The full ID of the repository."
}

output "repository_url" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repository_id}"
  description = "The URL to the repository for Docker pushes."
}