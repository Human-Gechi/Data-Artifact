resource "aws_cloudfront_origin_access_control" "artifact_oac" {
  name                              = "myths-agent-artifact-oac"
  description                       = "OAC for remix-agent compendium bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}
resource "aws_cloudfront_distribution" "artifact_cdn" {
  enabled             = true
  default_root_object = "index.html"
  comment             = "myths-agent frontend + data"

  origin {
    domain_name              = aws_s3_bucket.artifact_bucket.bucket_regional_domain_name
    origin_id                = "s3-artifact-origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.artifact_oac.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-artifact-origin"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 300
    max_ttl     = 3600
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

resource "aws_s3_bucket_policy" "artifact_bucket_policy" {
  bucket = aws_s3_bucket.artifact_bucket.id

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
        Resource = "${aws_s3_bucket.artifact_bucket.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.artifact_cdn.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_cloudfront_distribution.artifact_cdn]
}

resource "aws_s3_object" "index_html" {
  bucket       = aws_s3_bucket.artifact_bucket.id
  key          = "index.html"
  source       = "${path.module}/../frontend/index.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/../frontend/index.html")
}


