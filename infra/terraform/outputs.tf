output "server_public_ip" {
  description = "Public IPv4 address of the lab server"
  value       = aws_instance.server.public_ip
}