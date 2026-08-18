"""OpenTelemetry instrumentation: traces and metrics exported over OTLP.

There is no collector in front of this yet, so export goes straight to
whatever OTLP-compatible backend ``OTEL_EXPORTER_OTLP_ENDPOINT`` names. Left
unset, instrumentation is skipped entirely — local development and the test
suite otherwise retry export against an unreachable localhost:4318 on every
export interval and at every shutdown.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.engine import Engine

_sdk_configured = False

# Bound lazily: get_meter() returns a proxy that starts recording for real
# once _configure_sdk() installs the real MeterProvider, so these are safe to
# create — and safe to call .add() on — at any time, including at import time
# and while telemetry is off (where they're a no-op).
_meter = metrics.get_meter("sdip.backend")

sessions_created_counter = _meter.create_counter(
    "sdip.sessions.created",
    unit="1",
    description="Interview sessions (rooms) created.",
)

active_participants_counter = _meter.create_up_down_counter(
    "sdip.participants.active",
    unit="1",
    description="Participants currently connected to a realtime interview room.",
)

canvas_elements_created_counter = _meter.create_counter(
    "sdip.canvas.elements.created",
    unit="1",
    description="Canvas elements added across all interview rooms.",
)


def _resource() -> Resource:
    environment = os.getenv("SDIP_ENVIRONMENT", "development")
    return Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "sdip-backend"),
            "service.version": os.getenv("SDIP_GIT_COMMIT", "unknown"),
            # Both spellings: backends are still split on the semantic
            # conventions' pre- and post-1.27 attribute name.
            "deployment.environment": environment,
            "deployment.environment.name": environment,
        }
    )


def _configure_sdk() -> None:
    global _sdk_configured
    if _sdk_configured:
        return
    resource = _resource()

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    meter_provider = MeterProvider(
        resource=resource,
        # Short enough that a dashboard watching these feels live; the
        # default 60s is a long wait when you just clicked something.
        metric_readers=[
            PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=5000)
        ],
    )
    metrics.set_meter_provider(meter_provider)

    _sdk_configured = True


def instrument_app(app: FastAPI, engine: Engine | None = None) -> None:
    """Enable OTLP tracing and metrics for ``app``, and ``engine`` if given."""

    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return

    _configure_sdk()
    FastAPIInstrumentor.instrument_app(app, excluded_urls="/health")
    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine)
