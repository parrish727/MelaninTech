"""
Distributed Tracing — OpenTelemetry instrumentation for Melanin Technologies.

Provides:
  - Auto-initialization of OTEL tracer with service name
  - Decorator for adding spans to functions
  - Context propagation helpers for inter-service calls
  - Trace ID extraction for log correlation

Usage:
    from integrations.tracing import init_tracing, traced, get_trace_id

    # Initialize once at service startup
    init_tracing("orchestrator")

    # Decorate functions that should generate spans
    @traced("route_task")
    def route_task(task_text: str):
        ...

    # Get current trace ID for log correlation
    trace_id = get_trace_id()

Env vars:
    OTEL_ENDPOINT — OTEL Collector endpoint (default: http://otel-collector:4317)
    OTEL_ENABLED — Set to "false" to disable tracing (default: true)
"""
import os
import time
import functools
import logging
from typing import Optional, Callable
from contextlib import contextmanager

logger = logging.getLogger("tracing")

OTEL_ENDPOINT = os.environ.get("OTEL_ENDPOINT", "http://otel-collector:4317")
OTEL_ENABLED = os.environ.get("OTEL_ENABLED", "true").lower() != "false"

# Global tracer instance
_tracer = None
_initialized = False


def init_tracing(service_name: str, version: str = "1.0.0"):
    """
    Initialize OpenTelemetry tracing for a service.
    Call once at startup (e.g., in main.py or server.py).
    """
    global _tracer, _initialized

    if not OTEL_ENABLED:
        logger.info("Tracing disabled (OTEL_ENABLED=false)")
        _initialized = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        resource = Resource.create({
            SERVICE_NAME: service_name,
            SERVICE_VERSION: version,
            "deployment.environment": "production",
            "service.namespace": "melanin-tech",
        })

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        _tracer = trace.get_tracer(service_name, version)

        # Auto-instrument httpx (used by all our services)
        HTTPXClientInstrumentor().instrument()

        _initialized = True
        logger.info(f"Tracing initialized: service={service_name}, endpoint={OTEL_ENDPOINT}")

    except ImportError as e:
        logger.warning(f"OTEL dependencies not installed, tracing disabled: {e}")
        _initialized = True
    except Exception as e:
        logger.warning(f"Tracing init failed (non-fatal): {e}")
        _initialized = True


def get_tracer():
    """Get the global tracer instance."""
    return _tracer


def get_trace_id() -> str:
    """Get the current trace ID as a hex string (for log correlation)."""
    if not OTEL_ENABLED or _tracer is None:
        return "no-trace"

    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except Exception:
        pass

    return "no-trace"


def get_span_id() -> str:
    """Get the current span ID as a hex string."""
    if not OTEL_ENABLED or _tracer is None:
        return "no-span"

    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.span_id:
            return format(ctx.span_id, "016x")
    except Exception:
        pass

    return "no-span"


def traced(name: str = None, attributes: dict = None):
    """
    Decorator to add an OTEL span to a function.

    @traced("process_task")
    def process_task(task_text):
        ...

    @traced(attributes={"component": "router"})
    def route_request(req):
        ...
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not OTEL_ENABLED or _tracer is None:
                return func(*args, **kwargs)

            try:
                from opentelemetry import trace

                with _tracer.start_as_current_span(span_name) as span:
                    # Add custom attributes
                    if attributes:
                        for k, v in attributes.items():
                            span.set_attribute(k, v)

                    # Add function args as attributes (first arg only, truncated)
                    if args and isinstance(args[0], str):
                        span.set_attribute("input.text", args[0][:200])

                    try:
                        result = func(*args, **kwargs)
                        span.set_status(trace.StatusCode.OK)
                        return result
                    except Exception as e:
                        span.set_status(trace.StatusCode.ERROR, str(e))
                        span.record_exception(e)
                        raise
            except ImportError:
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not OTEL_ENABLED or _tracer is None:
                return await func(*args, **kwargs)

            try:
                from opentelemetry import trace

                with _tracer.start_as_current_span(span_name) as span:
                    if attributes:
                        for k, v in attributes.items():
                            span.set_attribute(k, v)

                    if args and isinstance(args[0], str):
                        span.set_attribute("input.text", args[0][:200])

                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(trace.StatusCode.OK)
                        return result
                    except Exception as e:
                        span.set_status(trace.StatusCode.ERROR, str(e))
                        span.record_exception(e)
                        raise
            except ImportError:
                return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


@contextmanager
def span(name: str, attributes: dict = None):
    """
    Context manager for creating spans inline.

    with span("llm_call", {"model": "claude-haiku"}):
        response = call_llm(...)
    """
    if not OTEL_ENABLED or _tracer is None:
        yield None
        return

    try:
        from opentelemetry import trace

        with _tracer.start_as_current_span(name) as s:
            if attributes:
                for k, v in attributes.items():
                    s.set_attribute(k, str(v))
            yield s
    except ImportError:
        yield None


def add_span_attributes(**kwargs):
    """Add attributes to the current active span."""
    if not OTEL_ENABLED or _tracer is None:
        return

    try:
        from opentelemetry import trace
        current_span = trace.get_current_span()
        for k, v in kwargs.items():
            current_span.set_attribute(k, str(v))
    except Exception:
        pass


def record_llm_call(model: str, tokens_in: int, tokens_out: int, latency_ms: int, status: str = "success"):
    """Record an LLM call as span attributes on the current span."""
    add_span_attributes(
        llm_model=model,
        llm_tokens_in=str(tokens_in),
        llm_tokens_out=str(tokens_out),
        llm_latency_ms=str(latency_ms),
        llm_status=status,
    )
