namespace ForgeLens.Core.Models;

/// <summary>
/// Represents a news article from any source.
/// </summary>
public class NewsArticle
{
    /// <summary>
    /// Article headline/title.
    /// </summary>
    public string Title { get; set; } = string.Empty;

    /// <summary>
    /// Short description or summary.
    /// </summary>
    public string? Description { get; set; }

    /// <summary>
    /// Full article content (if available).
    /// </summary>
    public string? Content { get; set; }

    /// <summary>
    /// Source name (e.g., "CNN", "BBC").
    /// </summary>
    public string Source { get; set; } = string.Empty;

    /// <summary>
    /// Original article URL.
    /// </summary>
    public string? Url { get; set; }

    /// <summary>
    /// Article image URL.
    /// </summary>
    public string? ImageUrl { get; set; }

    /// <summary>
    /// Publication date.
    /// </summary>
    public DateTime PublishedAt { get; set; }

    /// <summary>
    /// Category (technology, business, entertainment, etc.).
    /// </summary>
    public string Category { get; set; } = "general";

    /// <summary>
    /// API source (NewsAPI, GNews, etc.).
    /// </summary>
    public string ApiSource { get; set; } = string.Empty;
}

/// <summary>
/// Represents a selected topic for meme generation.
/// </summary>
public class MemeTopicSelection
{
    /// <summary>
    /// The main topic/headline.
    /// </summary>
    public string Topic { get; set; } = string.Empty;

    /// <summary>
    /// Why this topic is good for a meme.
    /// </summary>
    public string MemeAngle { get; set; } = string.Empty;

    /// <summary>
    /// The sarcastic/funny take on this topic.
    /// </summary>
    public string SarcasticTake { get; set; } = string.Empty;

    /// <summary>
    /// Related news articles.
    /// </summary>
    public List<NewsArticle> RelatedArticles { get; set; } = [];

    /// <summary>
    /// Suggested hashtags.
    /// </summary>
    public List<string> Hashtags { get; set; } = [];

    /// <summary>
    /// Virality score (0-100).
    /// </summary>
    public int ViralityScore { get; set; }
}
