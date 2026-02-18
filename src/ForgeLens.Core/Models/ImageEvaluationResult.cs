namespace ForgeLens.Core.Models;

/// <summary>
/// Evaluation scores for a single image.
/// </summary>
public record ImageScore
{
    /// <summary>
    /// Reference to the evaluated image.
    /// </summary>
    public required string ImageId { get; init; }

    /// <summary>
    /// Aesthetic quality score (1-10).
    /// </summary>
    public double AestheticScore { get; init; }

    /// <summary>
    /// Engagement potential score (1-10).
    /// </summary>
    public double EngagementScore { get; init; }

    /// <summary>
    /// Technical quality score (1-10).
    /// </summary>
    public double TechnicalScore { get; init; }

    /// <summary>
    /// Platform fit score for Instagram (1-10).
    /// </summary>
    public double PlatformFitScore { get; init; }

    /// <summary>
    /// Overall composite score (1-10).
    /// </summary>
    public double OverallScore => (AestheticScore + EngagementScore + TechnicalScore + PlatformFitScore) / 4;

    /// <summary>
    /// Detailed feedback from the evaluator.
    /// </summary>
    public string? Feedback { get; init; }

    /// <summary>
    /// Strengths identified in the image.
    /// </summary>
    public List<string> Strengths { get; init; } = [];

    /// <summary>
    /// Weaknesses identified in the image.
    /// </summary>
    public List<string> Weaknesses { get; init; } = [];
}

/// <summary>
/// Result of the image evaluation phase.
/// </summary>
public record ImageEvaluationResult
{
    /// <summary>
    /// The image selected as the best.
    /// </summary>
    public required GeneratedImage SelectedImage { get; init; }

    /// <summary>
    /// Scores for all evaluated images.
    /// </summary>
    public required List<ImageScore> AllScores { get; init; }

    /// <summary>
    /// Reasoning for the selection.
    /// </summary>
    public required string SelectionReasoning { get; init; }

    /// <summary>
    /// Suggested caption for the selected image.
    /// </summary>
    public required string SuggestedCaption { get; init; }

    /// <summary>
    /// Suggested hashtags for the post.
    /// </summary>
    public required List<string> SuggestedHashtags { get; init; }

    /// <summary>
    /// Time taken to evaluate all images.
    /// </summary>
    public TimeSpan EvaluationTime { get; init; }

    /// <summary>
    /// The winning image's score.
    /// </summary>
    public ImageScore WinnerScore => AllScores.First(s => s.ImageId == SelectedImage.Id);
}
