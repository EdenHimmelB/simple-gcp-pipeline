variable "project" {
  description = "Your GCP Project ID"
  default     = "<your-gcp-project-id>" # update here
}

variable "region" {
  description = "Region for GCP resources. Choose as per your location: https://cloud.google.com/about/locations"
  default     = "asia-southeast1"
  type        = string
}

variable "gcp_service_apis" {
  description = "The list of apis necessary for the project"
  type        = list(string)
  default = [
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "iam.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com"
  ]
}


variable "storage_class" {
  description = "Storage class type for your bucket. Check official docs for more info."
  default     = "STANDARD"
}

variable "account_id" {
  description = "Main service account which performs all operations in the cloud."
  default     = "<your-account-id>" #update here
}

variable "service_account_roles" {
  description = "The list of roles necessary for your service account"
  type        = list(string)
  default = [
    "roles/storage.admin",
    "roles/bigquery.admin"
  ]
}

variable "gcs_bucket_name" {
  description = "Your GCS bucket name."
  default     = "<your-unique-storage-id>" #update here
}


variable "bigquery_dataset" {
  description = "BigQuery Dataset that raw data (from GCS) will be written to."
  type        = string
  default     = "<your-bigquery-dataset>" #update here
}
