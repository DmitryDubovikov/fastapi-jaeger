import os


class Config:
    JAEGER_AGENT_HOST = os.getenv("JAEGER_AGENT_HOST", "jaeger")
    JAEGER_AGENT_PORT = int(os.getenv("JAEGER_AGENT_PORT", 6831))
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
