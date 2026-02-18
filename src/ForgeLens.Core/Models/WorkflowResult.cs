namespace ForgeLens.Core.Models;

/// <summary>
/// Complete result of a ForgeLens workflow execution.
/// </summary>
public record WorkflowResult
{
    /// <summary>
    /// Unique identifier for this workflow run.
    /// </summary>
    public required string RunId { get; init; }

    /// <summary>
    /// Result of trend analysis phase.
    /// </summary>
    public TrendAnalysisResult? TrendAnalysis { get; init; }

    /// <summary>
    /// Result of image generation phase.
    /// </summary>
    public ImageGenerationResult? ImageGeneration { get; init; }

    /// <summary>
    /// Result of image evaluation phase.
    /// </summary>
    public ImageEvaluationResult? ImageEvaluation { get; init; }

    /// <summary>
    /// Result of posting phase.
    /// </summary>
    public PostingResult? Posting { get; init; }

    /// <summary>
    /// Overall workflow status.
    /// </summary>
    public required WorkflowStatus Status { get; init; }

    /// <summary>
    /// Total time for the entire workflow.
    /// </summary>
    public TimeSpan TotalTime { get; init; }

    /// <summary>
    /// When the workflow started.
    /// </summary>
    public DateTime StartedAt { get; init; }

    /// <summary>
    /// When the workflow completed.
    /// </summary>
    public DateTime? CompletedAt { get; init; }

    /// <summary>
    /// Error message if workflow failed.
    /// </summary>
    public string? ErrorMessage { get; init; }

    /// <summary>
    /// Which phase failed (if any).
    /// </summary>
    public string? FailedPhase { get; init; }
}

/// <summary>
/// Status of the overall workflow.
/// </summary>
public enum WorkflowStatus
{
    /// <summary>
    /// Workflow not started.
    /// </summary>
    NotStarted,

    /// <summary>
    /// Currently analyzing trends.
    /// </summary>
    AnalyzingTrends,

    /// <summary>
    /// Currently generating images.
    /// </summary>
    GeneratingImages,

    /// <summary>
    /// Currently evaluating images.
    /// </summary>
    EvaluatingImages,

    /// <summary>
    /// Currently posting to Instagram.
    /// </summary>
    Posting,

    /// <summary>
    /// Workflow completed successfully.
    /// </summary>
    Completed,

    /// <summary>
    /// Workflow failed.
    /// </summary>
    Failed,

    /// <summary>
    /// Workflow was cancelled.
    /// </summary>
    Cancelled
}
