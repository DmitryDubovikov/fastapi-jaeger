import json
import time
from logging_setup import logger
from tracing_setup import tracer


def process_notification(ch, method, properties, body):
    with tracer.start_as_current_span("process_notification"):
        try:
            # Получение и декодирование сообщения
            message = json.loads(body)
            email = message.get("email")
            msg_content = message.get("message")

            # Создаем дочерний span для отправки нотификации
            with tracer.start_as_current_span("send_email") as span:
                span.set_attribute("email", email)
                span.set_attribute("message_length", len(msg_content))

                # Имитация отправки сообщения
                logger.info(f"Sending notification to {email}: {msg_content}")
                time.sleep(0.5)  # Имитация времени обработки

            # Подтверждение обработки сообщения
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Notification to {email} processed successfully")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Повторная очередь сообщения в случае ошибки
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
