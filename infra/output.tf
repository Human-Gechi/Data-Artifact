output "cloudfront_domain_name" {
  description = "Public URL to be added in the index.html as base_url"
  value       = "https://${aws_cloudfront_distribution.artifact_cdn.domain_name}"
}

output "s3_bucket_name" {
  description = "S3 bucket arn"
  value       = aws_s3_bucket.artifact_bucket.arn
}