import os
import logging
from typing import Optional

logger = logging.getLogger("gateway.tracing")

def init_tracing(app, engine=None):
    """
    Initialize OpenTelemetry distributed tracing with Jaeger exporter.
    Instruments FastAPI, HTTPX (outgoing HTTP requests), and SQLAlchemy (database queries).
    """
    service_name = os.getenv("OTEL_SERVICE_NAME", "api-gateway-portal")
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger-service:4318")
    tracing_enabled = os.getenv("TRACING_ENABLED", "true").lower() in ("true", "1", "yes")

    if not tracing_enabled:
        logger.info("OpenTelemetry tracing is disabled via TRACING_ENABLED=false")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        # 1. Setup Resource and TracerProvider
        resource = Resource.create({
            SERVICE_NAME: service_name,
            "service.namespace": "llm-platform",
            "deployment.environment": "kubernetes"
        })
        provider = TracerProvider(resource=resource)

        # 2. Setup OTLP HTTP Span Exporter
        traces_url = otlp_endpoint.rstrip("/")
        if not traces_url.endswith("/v1/traces"):
            traces_url = f"{traces_url}/v1/traces"

        otlp_exporter = OTLPSpanExporter(endpoint=traces_url, timeout=5)
        span_processor = BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=2048,
            schedule_delay_millis=2000,
            max_export_batch_size=512
        )
        provider.add_span_processor(span_processor)
        trace.set_tracer_provider(provider)

        # 3. Instrument FastAPI app
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=provider,
            excluded_urls="healthz,ready,metrics,static"
        )

        # 4. Instrument HTTPX client (outbound calls to Qwen LLM & Keycloak)
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)

        # 5. Instrument SQLAlchemy (database queries)
        if engine is not None:
            SQLAlchemyInstrumentor().instrument(
                engine=engine,
                tracer_provider=provider
            )

        logger.info(f"OpenTelemetry tracing successfully configured. Exporting to Jaeger at: {traces_url}")
    except Exception as e:
        logger.warning(f"Could not initialize OpenTelemetry tracing (running without tracing): {e}")

def get_current_span():
    """Retrieve active OpenTelemetry span for attaching custom metadata."""
    try:
        from opentelemetry import trace
        return trace.get_current_span()
    except Exception:
        return None
