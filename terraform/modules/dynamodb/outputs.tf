output "chat_sessions_table_name" {
  value = aws_dynamodb_table.chat_sessions.name
}

output "chat_sessions_table_arn" {
  value = aws_dynamodb_table.chat_sessions.arn
}

output "chat_messages_table_name" {
  value = aws_dynamodb_table.chat_messages.name
}

output "chat_messages_table_arn" {
  value = aws_dynamodb_table.chat_messages.arn
}
