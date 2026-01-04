"""
Shared runtime services (streaming, memory, cancellation, etc.).

This package provides core services for:
- Streaming pipeline execution
- Memory management
- Cancellation handling
- Long-running operations
"""

from .pipeline import (
    # State & Config
    PipelineState,
    PipelineStats,
    PipelineConfig,
    PipelineResult,
    # Cancellation
    CancellationToken,
    SimpleCancellationToken,
    PipelineCancelledException,
    # Callbacks
    ProgressCallback,
    # Protocols
    StreamReaderProtocol,
    StreamProcessorProtocol,
    StreamAggregatorProtocol,
    # Pipeline
    StreamingPipeline,
    # Utilities
    create_pipeline_from_format,
)

__all__ = [
    # Pipeline
    "PipelineState",
    "PipelineStats",
    "PipelineConfig",
    "PipelineResult",
    "CancellationToken",
    "SimpleCancellationToken",
    "PipelineCancelledException",
    "ProgressCallback",
    "StreamReaderProtocol",
    "StreamProcessorProtocol",
    "StreamAggregatorProtocol",
    "StreamingPipeline",
    "create_pipeline_from_format",
]
