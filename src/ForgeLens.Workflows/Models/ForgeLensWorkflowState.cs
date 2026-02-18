namespace ForgeLens.Workflows.Models;

/// <summary>
/// State that flows through the ForgeLens workflow
/// </summary>
public class ForgeLensWorkflowState
{
    public string? NewsCategory { get; set; } = "technology";
    public bool DryRun { get; set; } = true;
    
    // Trend Analysis Results
    public string? SelectedTopic { get; set; }
    public string? SarcasticTake { get; set; }
    public int ViralityScore { get; set; }
    public string? TrendAnalysisRaw { get; set; }
    
    // Image Generation Results
    public List<string> GeneratedImagePaths { get; set; } = new();
    public string? BestImagePath { get; set; }
    public double BestImageScore { get; set; }
    public string? ImageEvaluationRaw { get; set; }
    
    // Social Media Results
    public string? Caption { get; set; }
    public List<string> Hashtags { get; set; } = new();
    public bool IsCompliant { get; set; }
    public string? ComplianceCheckRaw { get; set; }
    public string? PostingResult { get; set; }
    
    // Workflow Metadata
    public DateTime StartedAt { get; set; } = DateTime.UtcNow;
    public DateTime? CompletedAt { get; set; }
    public WorkflowStatus Status { get; set; } = WorkflowStatus.NotStarted;
    public List<string> Errors { get; set; } = new();
    public List<WorkflowStep> CompletedSteps { get; set; } = new();
}

public enum WorkflowStatus
{
    NotStarted,
    AnalyzingTrends,
    GeneratingImages,
    EvaluatingImages,
    CheckingCompliance,
    GeneratingCaption,
    Posting,
    Completed,
    Failed
}

public class WorkflowStep
{
    public string Name { get; set; } = "";
    public DateTime StartedAt { get; set; }
    public DateTime CompletedAt { get; set; }
    public bool Success { get; set; }
    public string? Error { get; set; }
}
