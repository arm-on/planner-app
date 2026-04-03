import os


def disable_crewai_telemetry() -> None:
    """
    Disable CrewAI/OpenTelemetry network telemetry to avoid external calls and
    timeout noise in local deployments.
    """
    os.environ["OTEL_SDK_DISABLED"] = "true"
    os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
    os.environ["CREWAI_DISABLE_TRACKING"] = "true"
    os.environ["OTEL_TRACES_EXPORTER"] = "none"

