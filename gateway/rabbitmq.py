import aio_pika
import asyncio
from config import Config
from logging_setup import logger


async def get_rabbitmq_connection():
    max_retries = 5
    retry_count = 0
    retry_delay = 2  # секунд

    while retry_count < max_retries:
        try:
            connection = await aio_pika.connect_robust(
                host=Config.RABBITMQ_HOST,
                port=Config.RABBITMQ_PORT,
                login=Config.RABBITMQ_USER,
                password=Config.RABBITMQ_PASSWORD,
            )
            logger.info("Successfully connected to RabbitMQ")
            return connection
        except Exception as e:
            retry_count += 1
            logger.error(f"Failed to connect to RabbitMQ (attempt {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("Max retries reached. Failed to connect to RabbitMQ")
                raise


async def declare_queue(channel):
    await channel.declare_queue("notifications", durable=True)
    logger.info("Queue 'notifications' declared successfully")
