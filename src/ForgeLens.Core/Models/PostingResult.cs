namespace ForgeLens.Core.Models;

/// <summary>
/// Status of a posting operation.
/// </summary>
public enum PostingStatus
{
    /// <summary>
    /// Posting is pending.
    /// </summary>
    Pending,

    /// <summary>
    /// Currently in progress.
    /// </summary>
    InProgress,

    /// <summary>
    /// Successfully posted.
    /// </summary>
    Success,

    /// <summary>
    /// Posting failed.
    /// </summary>
    Failed,

    /// <summary>
    /// Posting was cancelled.
    /// </summary>
    Cancelled
}

/// <summary>
/// Result of the Instagram posting phase.
/// </summary>
public record PostingResult
{
    /// <summary>
    /// Status of the posting operation.
    /// </summary>
    public required PostingStatus Status { get; init; }

    /// <summary>
    /// The image that was posted.
    /// </summary>
    public required GeneratedImage PostedImage { get; init; }

    /// <summary>
    /// The caption that was used.
    /// </summary>
    public required string Caption { get; init; }

    /// <summary>
    /// Hashtags that were used.
    /// </summary>
    public required List<string> Hashtags { get; init; }

    /// <summary>
    /// URL of the posted content (if available).
    /// </summary>
    public string? PostUrl { get; init; }

    /// <summary>
    /// Post ID from Instagram (if available).
    /// </summary>
    public string? PostId { get; init; }

    /// <summary>
    /// Time taken to complete the posting.
    /// </summary>
    public TimeSpan PostingTime { get; init; }

    /// <summary>
    /// When the post was published.
    /// </summary>
    public DateTime? PostedAt { get; init; }

    /// <summary>
    /// Error message if posting failed.
    /// </summary>
    public string? ErrorMessage { get; init; }

    /// <summary>
    /// Screenshot path of the posted content.
    /// </summary>
    public string? ScreenshotPath { get; init; }

    /// <summary>
    /// Additional engagement actions performed.
    /// </summary>
    public List<EngagementAction> EngagementActions { get; init; } = [];
}

/// <summary>
/// Represents an engagement action taken during posting.
/// </summary>
public record EngagementAction
{
    /// <summary>
    /// Type of action (like, comment, view story, etc.).
    /// </summary>
    public required string ActionType { get; init; }

    /// <summary>
    /// Target of the action (post URL, username, etc.).
    /// </summary>
    public string? Target { get; init; }

    /// <summary>
    /// When the action was performed.
    /// </summary>
    public DateTime PerformedAt { get; init; } = DateTime.UtcNow;

    /// <summary>
    /// Whether the action was successful.
    /// </summary>
    public bool Success { get; init; }
}
