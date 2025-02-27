import json
import os
import logging
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import aio_pika
import asyncio

# OpenTelemetry для трассировки
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка OpenTelemetry
resource = Resource(attributes={SERVICE_NAME: "notification-gateway"})

jaeger_exporter = JaegerExporter(
    agent_host_name=os.getenv("JAEGER_AGENT_HOST", "jaeger"),
    agent_port=int(os.getenv("JAEGER_AGENT_PORT", 6831)),
)

provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(jaeger_exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# Создание приложения FastAPI
app = FastAPI(title="Notification Gateway")

# Инструментирование FastAPI
FastAPIInstrumentor.instrument_app(app)


# Модель запроса нотификации
class NotificationRequest(BaseModel):
    email: str
    message: str


# Соединение с RabbitMQ
async def get_rabbitmq_connection():
    rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    rabbitmq_port = int(os.getenv("RABBITMQ_PORT", 5672))
    rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
    rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")

    max_retries = 5
    retry_count = 0
    retry_delay = 2  # секунд

    while retry_count < max_retries:
        try:
            connection = await aio_pika.connect_robust(
                host=rabbitmq_host, port=rabbitmq_port, login=rabbitmq_user, password=rabbitmq_password
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


# Глобальная переменная для соединения
rabbitmq_connection = None
rabbitmq_channel = None


@app.on_event("startup")
async def startup_event():
    global rabbitmq_connection, rabbitmq_channel

    # Подключение к RabbitMQ с повторными попытками
    rabbitmq_connection = await get_rabbitmq_connection()

    # Создание канала
    rabbitmq_channel = await rabbitmq_connection.channel()

    # Объявление очереди
    await rabbitmq_channel.declare_queue("notifications", durable=True)
    logger.info("Queue 'notifications' declared successfully")


@app.on_event("shutdown")
async def shutdown_event():
    if rabbitmq_connection:
        await rabbitmq_connection.close()
        logger.info("Disconnected from RabbitMQ")


@app.post("/send-notification")
async def send_notification(request: NotificationRequest):
    with tracer.start_as_current_span("send_notification") as span:
        span.set_attribute("email", request.email)

        # Подготовка сообщения
        message_body = {"email": request.email, "message": request.message}

        # Отправка сообщения в RabbitMQ
        await rabbitmq_channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(message_body).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key="notifications",
        )

        logger.info(f"Notification for {request.email} sent to queue")
        return {"status": "success", "message": "Notification queued"}


@app.get("/health")
async def health_check():
    if rabbitmq_connection and not rabbitmq_connection.is_closed:
        return {"status": "ok", "rabbitmq_connection": "connected"}
    return {"status": "error", "rabbitmq_connection": "disconnected"}


# Обработка ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(status_code=500, content={"message": f"Internal server error: {str(exc)}"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
