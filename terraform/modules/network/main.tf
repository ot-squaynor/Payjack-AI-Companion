resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-${var.environment}-alb-sg"
  description = "ALB security group for Payjack AI Companion"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_security_group_rule" "alb_ingress" {
  for_each = toset(var.alb_ingress_cidr_blocks)

  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  security_group_id = aws_security_group.alb.id
  cidr_blocks       = [each.value]
}

resource "aws_security_group_rule" "alb_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.alb.id
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group" "service" {
  name        = "${var.name_prefix}-${var.environment}-service-sg"
  description = "ECS service security group for Payjack AI Companion"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_security_group_rule" "service_ingress_from_alb" {
  type                     = "ingress"
  from_port                = var.app_port
  to_port                  = var.app_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.service.id
  source_security_group_id = aws_security_group.alb.id
}

resource "aws_security_group_rule" "service_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.service.id
  cidr_blocks       = ["0.0.0.0/0"]
}
