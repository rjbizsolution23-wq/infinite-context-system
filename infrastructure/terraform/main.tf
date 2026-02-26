# 🏗️ ICS v4.0 — INFRASTRUCTURE AS CODE (TERRAFORM)
# Provisioning Google Cloud Platform (GCP) for Supreme Empire Deployment

variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "region" {
  default = "us-central1"
}

resource "google_container_cluster" "ics_cluster" {
  name     = "ics-supreme-cluster"
  location = var.region
  
  # Multi-zone for high availability
  node_locations = ["${var.region}-a", "${var.region}-b"]
  
  initial_node_count = 3
  
  # Shielded nodes for security
  enable_shielded_nodes = true
}

# Qdrant Vector Store (Cloud Run)
resource "google_cloud_run_service" "qdrant" {
  name     = "ics-qdrant"
  location = var.region
  
  template {
    spec {
      containers {
        image = "qdrant/qdrant:latest"
      }
    }
  }
}
