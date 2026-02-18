namespace ForgeLens.Core.Models;

/// <summary>
/// Represents a trending topic discovered during trend analysis.
/// </summary>
public record TrendingTopic
{
    /// <summary>
    /// The name or title of the trending topic.
    /// </summary>
    public required string Name { get; init; }

    /// <summary>
    /// Category of the trend (e.g., Technology, Entertainment, Sports).
    /// </summary>
    public required string Category { get; init; }

    /// <summary>
    /// Source platform where the trend was discovered.
    /// </summary>
    public required string Source { get; init; }

    /// <summary>
    /// URL where the trend was found.
    /// </summary>
    public string? SourceUrl { get; init; }

    /// <summary>
    /// Engagement metrics (likes, shares, comments combined).
    /// </summary>
    public int EngagementScore { get; init; }

    /// <summary>
    /// Predicted viral potential score from 0.0 to 1.0.
    /// </summary>
    public double ViralityPotential { get; init; }

    /// <summary>
    /// Related keywords and hashtags.
    /// </summary>
    public string[] RelatedKeywords { get; init; } = [];

    /// <summary>
    /// Brief description of the trend.
    /// </summary>
    public string? Description { get; init; }

    /// <summary>
    /// When the trend was discovered.
    /// </summary>
    public DateTime DiscoveredAt { get; init; } = DateTime.UtcNow;
}

/// <summary>
/// Result of the trend analysis phase.
/// </summary>
public record TrendAnalysisResult
{
    /// <summary>
    /// All discovered trending topics.
    /// </summary>
    public required List<TrendingTopic> DiscoveredTrends { get; init; }

    /// <summary>
    /// The selected topic for content creation.
    /// </summary>
    public required TrendingTopic SelectedTopic { get; init; }

    /// <summary>
    /// Generated content brief based on the selected topic.
    /// </summary>
    public required string ContentBrief { get; init; }

    /// <summary>
    /// Suggested image prompts for DALL-E.
    /// </summary>
    public required List<string> SuggestedPrompts { get; init; }

    /// <summary>
    /// Time taken to analyze trends.
    /// </summary>
    public TimeSpan AnalysisTime { get; init; }

    /// <summary>
    /// Reasoning for topic selection.
    /// </summary>
    public string? SelectionReasoning { get; init; }
}
