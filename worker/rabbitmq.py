import pika
import time
from config import Config
from logging_setup import logger


def get_rabbitmq_connection():
    """
    Устанавливает соединение с RabbitMQ с механизмом повторных попыток
    """
    max_retries = 5
    retry_count = 0
    retry_delay = 2  # секунд

    while retry_count < max_retries:
        try:
            credentials = pika.PlainCredentials(Config.RABBITMQ_USER, Config.RABBITMQ_PASSWORD)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=Config.RABBITMQ_HOST, port=Config.RABBITMQ_PORT, credentials=credentials)
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
    channel = connection.channel()
    channel.queue_declare(queue="notifications", durable=True)
    channel.basic_qos(prefetch_count=1)
    return channel
