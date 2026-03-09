terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "partner-components-terraform-state"
    key            = "storybook/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "partner-components-terraform-locks"
  }
}

provider "aws" {
  region = "us-west-2"

  default_tags {
    tags = {
      Project   = "partner-components"
      ManagedBy = "terraform"
    }
  }
}

# CloudFront requires ACM certificates in us-east-1
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project   = "partner-components"
      ManagedBy = "terraform"
    }
  }
}
