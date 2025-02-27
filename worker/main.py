import json
import os
import logging
import pika
import time

# OpenTelemetry для трассировки
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка OpenTelemetry
resource = Resource(attributes={SERVICE_NAME: "notification-worker"})

jaeger_exporter = JaegerExporter(
    agent_host_name=os.getenv("JAEGER_AGENT_HOST", "jaeger"),
    agent_port=int(os.getenv("JAEGER_AGENT_PORT", 6831)),
)

provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(jaeger_exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


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


def get_rabbitmq_connection():
    """
    Устанавливает соединение с RabbitMQ с механизмом повторных попыток
    """
    # Параметры подключения к RabbitMQ
    rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    rabbitmq_port = int(os.getenv("RABBITMQ_PORT", 5672))
    rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
    rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")

    # Подключение к RabbitMQ
    max_retries = 5
    retry_count = 0
    retry_delay = 2  # секунд

    while retry_count < max_retries:
        try:
            # Установка соединения
            credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port, credentials=credentials)
            )
            logger.info("Successfully connected to RabbitMQ")
            return connection
        except Exception as e:
            retry_count += 1
            logger.error(f"Failed to connect to RabbitMQ (attempt {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("Max retries reached. Failed to connect to RabbitMQ")
                raise


def setup_rabbitmq_consumer(connection):
    """
    Настраивает канал и потребителя RabbitMQ
    """
    # Создание канала
    channel = connection.channel()

    # Объявление очереди
    channel.queue_declare(queue="notifications", durable=True)

    # Настройка обработки только одного сообщения за раз
    channel.basic_qos(prefetch_count=1)

    # Настройка обработчика сообщений
    channel.basic_consume(queue="notifications", on_message_callback=process_notification)

    return channel


def main():
    try:
        # Подключение к RabbitMQ
        connection = get_rabbitmq_connection()

        # Настройка потребителя
        channel = setup_rabbitmq_consumer(connection)

        # Запуск потребления сообщений
        logger.info("Worker started, waiting for messages...")
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
