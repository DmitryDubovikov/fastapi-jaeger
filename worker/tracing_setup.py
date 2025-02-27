from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from config import Config


def setup_tracing(service_name):
    resource = Resource(attributes={SERVICE_NAME: service_name})
    jaeger_exporter = JaegerExporter(
        agent_host_name=Config.JAEGER_AGENT_HOST,
        agent_port=Config.JAEGER_AGENT_PORT,
    )
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(jaeger_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


tracer = setup_tracing("notification-worker")
