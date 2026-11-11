resource "aws_key_pair" "operator" {
  key_name   = "pyforge-lab-operator-v2"
  public_key = file(pathexpand("~/.ssh/pyforge_ec2.pub"))
}

resource "aws_instance" "server" {
  ami                         = "ami-0d6dd9e8265d48906"
  instance_type               = "t3.small"
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.server.id]
  key_name                    = aws_key_pair.operator.key_name
  iam_instance_profile        = aws_iam_instance_profile.server_ssm.name
  associate_public_ip_address = true

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 16
    encrypted             = true
    delete_on_termination = true
  }

  credit_specification {
    cpu_credits = "standard"
  }

  metadata_options {
    http_tokens = "required"
  }

  tags = {
    Name = "pyforge-lab-server"
  }
}