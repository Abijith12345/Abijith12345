terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_instance" "test" {
  ami           = var.ami
  instance_type = var.instance_type
 
  tags = {
    Name = "test2"
  }
}

