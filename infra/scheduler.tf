resource "aws_iam_role" "scheduler_role" {
  name = "myths-agent-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "scheduler_invoke_policy" {
  name        = "myths-agent-scheduler-invoke-policy"
  description = "Allow EventBridge Scheduler to invoke the remix-agent Lambda"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "InvokeLambda"
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.myths_agent.arn
      }
    ]
  })
}
resource "aws_iam_role_policy_attachment" "scheduler_attach" {
  role       = aws_iam_role.scheduler_role.name
  policy_arn = aws_iam_policy.scheduler_invoke_policy.arn
}
resource "aws_scheduler_schedule" "daily_myths_agent" {
  name = "daily-myths-agent"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 7 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_lambda_function.myths_agent.arn
    role_arn = aws_iam_role.scheduler_role.arn
  }
}