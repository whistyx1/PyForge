output "server_public_ip" {
  description = "Public IPv4 address of the lab server"
  value       = aws_instance.server.public_ip
}

output "backup_bucket_name" {
  description = "Private bucket that stores PyForge SQLite snapshots"
  value       = aws_s3_bucket.backups.id
}
