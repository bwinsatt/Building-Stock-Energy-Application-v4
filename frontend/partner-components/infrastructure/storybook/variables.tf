variable "basic_auth_username" {
  description = "Username for HTTP basic authentication"
  type        = string
  sensitive   = true
}

variable "basic_auth_password" {
  description = "Password for HTTP basic authentication"
  type        = string
  sensitive   = true
}
