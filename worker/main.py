from rabbitmq import get_rabbitmq_connection, setup_rabbitmq_consumer
from notification_processor import process_notification
from logging_setup import logger


def main():
    try:
        # Подключение к RabbitMQ
        connection = get_rabbitmq_connection()

        # Настройка потребителя
        channel = setup_rabbitmq_consumer(connection)
        channel.basic_consume(queue="notifications", on_message_callback=process_notification)

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
