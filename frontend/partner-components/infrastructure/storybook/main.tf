locals {
  bucket_name = "partner-storybook-${data.aws_caller_identity.current.account_id}"
  # Base64 encode the credentials for basic auth
  basic_auth_credentials = base64encode("${var.basic_auth_username}:${var.basic_auth_password}")
}

data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# S3 Bucket for Storybook static files
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "storybook" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_versioning" "storybook" {
  bucket = aws_s3_bucket.storybook.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "storybook" {
  bucket = aws_s3_bucket.storybook.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "storybook" {
  bucket = aws_s3_bucket.storybook.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# CloudFront Origin Access Control
# -----------------------------------------------------------------------------

resource "aws_cloudfront_origin_access_control" "storybook" {
  name                              = "storybook-oac"
  description                       = "OAC for Storybook S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# -----------------------------------------------------------------------------
# S3 Bucket Policy - Allow CloudFront access
# -----------------------------------------------------------------------------

resource "aws_s3_bucket_policy" "storybook" {
  bucket = aws_s3_bucket.storybook.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipal"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.storybook.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.storybook.arn
          }
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# CloudFront Function for Basic Auth
# -----------------------------------------------------------------------------

resource "aws_cloudfront_function" "basic_auth" {
  name    = "storybook-basic-auth"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-EOF
    function handler(event) {
      var request = event.request;
      var headers = request.headers;
      var authString = "Basic ${local.basic_auth_credentials}";

      if (
        typeof headers.authorization === "undefined" ||
        headers.authorization.value !== authString
      ) {
        return {
          statusCode: 401,
          statusDescription: "Unauthorized",
          headers: {
            "www-authenticate": { value: "Basic realm=\"Storybook\"" }
          }
        };
      }

      return request;
    }
  EOF
}

# -----------------------------------------------------------------------------
# CloudFront Distribution
# -----------------------------------------------------------------------------

resource "aws_cloudfront_distribution" "storybook" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  comment             = "Partner Components Storybook"
  price_class         = "PriceClass_100" # US, Canada, Europe only (cheapest)
  aliases             = ["www.partner-components.com"]

  origin {
    domain_name              = aws_s3_bucket.storybook.bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.storybook.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.storybook.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.storybook.id}"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    # Use managed cache policy for caching
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6" # CachingOptimized

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.basic_auth.arn
    }
  }

  # Handle SPA routing - return index.html for 404s
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.storybook.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name = "partner-storybook"
  }

  depends_on = [aws_acm_certificate_validation.storybook]
}

# -----------------------------------------------------------------------------
# Route53 Hosted Zone (data source - created when domain was registered)
# -----------------------------------------------------------------------------

data "aws_route53_zone" "main" {
  name = "partner-components.com"
}

# -----------------------------------------------------------------------------
# ACM Certificate (must be in us-east-1 for CloudFront)
# -----------------------------------------------------------------------------

resource "aws_acm_certificate" "storybook" {
  provider          = aws.us_east_1
  domain_name       = "www.partner-components.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "partner-storybook"
  }
}

# -----------------------------------------------------------------------------
# Route53 DNS Validation Records for ACM
# -----------------------------------------------------------------------------

resource "aws_route53_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.storybook.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main.zone_id
}

resource "aws_acm_certificate_validation" "storybook" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.storybook.arn
  validation_record_fqdns = [for record in aws_route53_record.acm_validation : record.fqdn]
}

# -----------------------------------------------------------------------------
# Route53 A Record (alias to CloudFront)
# -----------------------------------------------------------------------------

resource "aws_route53_record" "storybook" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "www.partner-components.com"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.storybook.domain_name
    zone_id                = aws_cloudfront_distribution.storybook.hosted_zone_id
    evaluate_target_health = false
  }
}

