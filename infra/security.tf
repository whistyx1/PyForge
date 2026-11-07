resource "aws_security_group" "server" {
  name        = "pyforge-lab-server"
  description = "Network access for the PyForge lab server"
  vpc_id      = aws_vpc.lab.id

  tags = {
    Name = "pyforge-lab-server"
  }
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.server.id
  description       = "SSH from my public IP"
  cidr_ipv4         = var.ssh_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "outbound" {
  security_group_id = aws_security_group.server.id
  description       = "Allow package and image downloads"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}