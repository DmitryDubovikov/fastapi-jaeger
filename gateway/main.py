from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from logging_setup import logger
from tracing_setup import tracer
from rabbitmq import get_rabbitmq_connection, declare_queue
from models import NotificationRequest
import json
import aio_pika

app = FastAPI(title="Notification Gateway")
FastAPIInstrumentor.instrument_app(app)

rabbitmq_connection = None
rabbitmq_channel = None


@app.on_event("startup")
async def startup_event():
    global rabbitmq_connection, rabbitmq_channel
    rabbitmq_connection = await get_rabbitmq_connection()
    rabbitmq_channel = await rabbitmq_connection.channel()
    await declare_queue(rabbitmq_channel)


@app.on_event("shutdown")
async def shutdown_event():
    if rabbitmq_connection:
        await rabbitmq_connection.close()
        logger.info("Disconnected from RabbitMQ")


@app.post("/send-notification")
async def send_notification(request: NotificationRequest):
    with tracer.start_as_current_span("send_notification") as span:
        span.set_attribute("email", request.email)
        message_body = {"email": request.email, "message": request.message}
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(status_code=500, content={"message": f"Internal server error: {str(exc)}"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
