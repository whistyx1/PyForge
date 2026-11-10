data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "server_ssm" {
  name               = "pyforge-lab-server-ssm"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_role_policy_attachment" "server_ssm" {
  role       = aws_iam_role.server_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "server_ssm" {
  name = "pyforge-lab-server-ssm"
  role = aws_iam_role.server_ssm.name
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_deploy_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:whistyx1@186757401/PyForge@1374843217:ref:refs/heads/main"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "pyforge-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_deploy_assume_role.json
}

data "aws_iam_policy_document" "github_deploy_permissions" {
  statement {
    actions   = ["ssm:SendCommand"]
    resources = [aws_instance.server.arn, "arn:aws:ssm:us-east-1::document/AWS-RunShellScript"]
  }

  statement {
    actions   = ["ssm:GetCommandInvocation", "ec2:DescribeInstances"]
    resources = ["*"]
  }

  statement {
    actions   = ["ssm:PutParameter"]
    resources = ["arn:aws:ssm:us-east-1:266294231268:parameter/pyforge/production/DJANGO_SECRET_KEY"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy_permissions.json
}

data "aws_iam_policy_document" "server_secret_read" {
  statement {
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:us-east-1:266294231268:parameter/pyforge/production/DJANGO_SECRET_KEY"]
  }
}

resource "aws_iam_role_policy" "server_secret_read" {
  role   = aws_iam_role.server_ssm.id
  policy = data.aws_iam_policy_document.server_secret_read.json
}