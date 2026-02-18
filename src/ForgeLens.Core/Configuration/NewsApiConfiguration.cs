namespace ForgeLens.Core.Configuration;

/// <summary>
/// Configuration for news API services.
/// </summary>
public class NewsApiConfiguration
{
    /// <summary>
    /// NewsAPI.org API key (free tier: 100 requests/day).
    /// </summary>
    public string? NewsApiKey { get; set; }

    /// <summary>
    /// GNews.io API key (free tier: 100 requests/day).
    /// </summary>
    public string? GNewsApiKey { get; set; }

    /// <summary>
    /// NewsData.io API key (free tier: 200 requests/day).
    /// </summary>
    public string? NewsDataApiKey { get; set; }

    /// <summary>
    /// Categories to fetch news from.
    /// </summary>
    public string[] Categories { get; set; } = ["technology", "business", "entertainment", "science"];

    /// <summary>
    /// Country code for localized news (e.g., "us", "gb", "in").
    /// </summary>
    public string Country { get; set; } = "us";

    /// <summary>
    /// Maximum number of articles to fetch per source.
    /// </summary>
    public int MaxArticlesPerSource { get; set; } = 10;
}
