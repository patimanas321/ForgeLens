using ForgeLens.Core.Configuration;
using ForgeLens.Core.Models;
using Serilog;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace ForgeLens.Infrastructure.News;

/// <summary>
/// Aggregates news from multiple free APIs.
/// </summary>
public class NewsAggregatorService
{
    private readonly NewsApiConfiguration _config;
    private readonly ILogger _logger;
    private readonly HttpClient _httpClient;

    public NewsAggregatorService(NewsApiConfiguration config, ILogger logger)
    {
        _config = config;
        _logger = logger;
        _httpClient = new HttpClient();
        _httpClient.DefaultRequestHeaders.Add("User-Agent", "ForgeLens/1.0");
    }

    /// <summary>
    /// Fetches news from all configured sources.
    /// </summary>
    public async Task<List<NewsArticle>> FetchAllNewsAsync(CancellationToken cancellationToken = default)
    {
        var allArticles = new List<NewsArticle>();

        // Fetch from NewsAPI.org
        if (!string.IsNullOrEmpty(_config.NewsApiKey))
        {
            var newsApiArticles = await FetchFromNewsApiAsync(cancellationToken);
            allArticles.AddRange(newsApiArticles);
        }

        // Fetch from GNews
        if (!string.IsNullOrEmpty(_config.GNewsApiKey))
        {
            var gnewsArticles = await FetchFromGNewsAsync(cancellationToken);
            allArticles.AddRange(gnewsArticles);
        }

        // Fetch from NewsData.io
        if (!string.IsNullOrEmpty(_config.NewsDataApiKey))
        {
            var newsDataArticles = await FetchFromNewsDataAsync(cancellationToken);
            allArticles.AddRange(newsDataArticles);
        }

        // If no API keys configured, use free RSS-like sources
        if (allArticles.Count == 0)
        {
            _logger.Warning("No news API keys configured. Using fallback sources...");
            var fallbackArticles = await FetchFromFallbackSourcesAsync(cancellationToken);
            allArticles.AddRange(fallbackArticles);
        }

        _logger.Information("Fetched {Count} total articles from all sources", allArticles.Count);

        // Remove duplicates based on title similarity
        return DeduplicateArticles(allArticles);
    }

    /// <summary>
    /// Fetches top headlines from NewsAPI.org.
    /// </summary>
    private async Task<List<NewsArticle>> FetchFromNewsApiAsync(CancellationToken cancellationToken)
    {
        var articles = new List<NewsArticle>();

        try
        {
            var url = $"https://newsapi.org/v2/top-headlines?country={_config.Country}&pageSize={_config.MaxArticlesPerSource}&apiKey={_config.NewsApiKey}";
            
            var response = await _httpClient.GetAsync(url, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                _logger.Warning("NewsAPI returned {StatusCode}", response.StatusCode);
                return articles;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            var result = JsonSerializer.Deserialize<NewsApiResponse>(json, new JsonSerializerOptions 
            { 
                PropertyNameCaseInsensitive = true 
            });

            if (result?.Articles != null)
            {
                foreach (var article in result.Articles)
                {
                    if (!string.IsNullOrEmpty(article.Title) && article.Title != "[Removed]")
                    {
                        articles.Add(new NewsArticle
                        {
                            Title = article.Title,
                            Description = article.Description,
                            Content = article.Content,
                            Source = article.Source?.Name ?? "Unknown",
                            Url = article.Url,
                            ImageUrl = article.UrlToImage,
                            PublishedAt = article.PublishedAt,
                            Category = "general",
                            ApiSource = "NewsAPI"
                        });
                    }
                }
            }

            _logger.Information("Fetched {Count} articles from NewsAPI", articles.Count);
        }
        catch (Exception ex)
        {
            _logger.Warning(ex, "Failed to fetch from NewsAPI");
        }

        return articles;
    }

    /// <summary>
    /// Fetches news from GNews.io.
    /// </summary>
    private async Task<List<NewsArticle>> FetchFromGNewsAsync(CancellationToken cancellationToken)
    {
        var articles = new List<NewsArticle>();

        try
        {
            var url = $"https://gnews.io/api/v4/top-headlines?country={_config.Country}&max={_config.MaxArticlesPerSource}&apikey={_config.GNewsApiKey}";
            
            var response = await _httpClient.GetAsync(url, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                _logger.Warning("GNews returned {StatusCode}", response.StatusCode);
                return articles;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            var result = JsonSerializer.Deserialize<GNewsResponse>(json, new JsonSerializerOptions 
            { 
                PropertyNameCaseInsensitive = true 
            });

            if (result?.Articles != null)
            {
                foreach (var article in result.Articles)
                {
                    articles.Add(new NewsArticle
                    {
                        Title = article.Title ?? "",
                        Description = article.Description,
                        Content = article.Content,
                        Source = article.Source?.Name ?? "Unknown",
                        Url = article.Url,
                        ImageUrl = article.Image,
                        PublishedAt = article.PublishedAt,
                        Category = "general",
                        ApiSource = "GNews"
                    });
                }
            }

            _logger.Information("Fetched {Count} articles from GNews", articles.Count);
        }
        catch (Exception ex)
        {
            _logger.Warning(ex, "Failed to fetch from GNews");
        }

        return articles;
    }

    /// <summary>
    /// Fetches news from NewsData.io.
    /// </summary>
    private async Task<List<NewsArticle>> FetchFromNewsDataAsync(CancellationToken cancellationToken)
    {
        var articles = new List<NewsArticle>();

        try
        {
            var url = $"https://newsdata.io/api/1/news?apikey={_config.NewsDataApiKey}&country={_config.Country}&language=en";
            
            var response = await _httpClient.GetAsync(url, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                _logger.Warning("NewsData.io returned {StatusCode}", response.StatusCode);
                return articles;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            var result = JsonSerializer.Deserialize<NewsDataResponse>(json, new JsonSerializerOptions 
            { 
                PropertyNameCaseInsensitive = true 
            });

            if (result?.Results != null)
            {
                foreach (var article in result.Results.Take(_config.MaxArticlesPerSource))
                {
                    articles.Add(new NewsArticle
                    {
                        Title = article.Title ?? "",
                        Description = article.Description,
                        Content = article.Content,
                        Source = article.SourceId ?? "Unknown",
                        Url = article.Link,
                        ImageUrl = article.ImageUrl,
                        PublishedAt = DateTime.TryParse(article.PubDate, out var dt) ? dt : DateTime.UtcNow,
                        Category = article.Category?.FirstOrDefault() ?? "general",
                        ApiSource = "NewsData"
                    });
                }
            }

            _logger.Information("Fetched {Count} articles from NewsData.io", articles.Count);
        }
        catch (Exception ex)
        {
            _logger.Warning(ex, "Failed to fetch from NewsData.io");
        }

        return articles;
    }

    /// <summary>
    /// Fetches from free fallback sources when no API keys are available.
    /// Uses Hacker News API (no key required).
    /// </summary>
    private async Task<List<NewsArticle>> FetchFromFallbackSourcesAsync(CancellationToken cancellationToken)
    {
        var articles = new List<NewsArticle>();

        try
        {
            // Hacker News top stories (free, no API key needed)
            var topStoriesUrl = "https://hacker-news.firebaseio.com/v0/topstories.json";
            var topStoryIds = await _httpClient.GetFromJsonAsync<int[]>(topStoriesUrl, cancellationToken);

            if (topStoryIds != null)
            {
                foreach (var storyId in topStoryIds.Take(_config.MaxArticlesPerSource))
                {
                    try
                    {
                        var storyUrl = $"https://hacker-news.firebaseio.com/v0/item/{storyId}.json";
                        var story = await _httpClient.GetFromJsonAsync<HackerNewsItem>(storyUrl, cancellationToken);

                        if (story != null && !string.IsNullOrEmpty(story.Title))
                        {
                            articles.Add(new NewsArticle
                            {
                                Title = story.Title,
                                Description = story.Text,
                                Url = story.Url ?? $"https://news.ycombinator.com/item?id={storyId}",
                                Source = "Hacker News",
                                PublishedAt = DateTimeOffset.FromUnixTimeSeconds(story.Time).DateTime,
                                Category = "technology",
                                ApiSource = "HackerNews"
                            });
                        }
                    }
                    catch
                    {
                        // Skip failed stories
                    }
                }
            }

            _logger.Information("Fetched {Count} articles from Hacker News (fallback)", articles.Count);
        }
        catch (Exception ex)
        {
            _logger.Warning(ex, "Failed to fetch from fallback sources");
        }

        return articles;
    }

    private List<NewsArticle> DeduplicateArticles(List<NewsArticle> articles)
    {
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var unique = new List<NewsArticle>();

        foreach (var article in articles)
        {
            // Create a simple key from the first few words of the title
            var titleKey = string.Join(" ", article.Title.Split(' ').Take(5));
            if (seen.Add(titleKey))
            {
                unique.Add(article);
            }
        }

        return unique;
    }

    #region API Response Models

    private class NewsApiResponse
    {
        public string? Status { get; set; }
        public int TotalResults { get; set; }
        public List<NewsApiArticle>? Articles { get; set; }
    }

    private class NewsApiArticle
    {
        public NewsApiSource? Source { get; set; }
        public string? Title { get; set; }
        public string? Description { get; set; }
        public string? Url { get; set; }
        public string? UrlToImage { get; set; }
        public DateTime PublishedAt { get; set; }
        public string? Content { get; set; }
    }

    private class NewsApiSource
    {
        public string? Id { get; set; }
        public string? Name { get; set; }
    }

    private class GNewsResponse
    {
        public int TotalArticles { get; set; }
        public List<GNewsArticle>? Articles { get; set; }
    }

    private class GNewsArticle
    {
        public string? Title { get; set; }
        public string? Description { get; set; }
        public string? Content { get; set; }
        public string? Url { get; set; }
        public string? Image { get; set; }
        public DateTime PublishedAt { get; set; }
        public GNewsSource? Source { get; set; }
    }

    private class GNewsSource
    {
        public string? Name { get; set; }
        public string? Url { get; set; }
    }

    private class NewsDataResponse
    {
        public string? Status { get; set; }
        public int TotalResults { get; set; }
        public List<NewsDataArticle>? Results { get; set; }
    }

    private class NewsDataArticle
    {
        public string? Title { get; set; }
        public string? Link { get; set; }
        public string? Description { get; set; }
        public string? Content { get; set; }
        public string? PubDate { get; set; }
        [JsonPropertyName("image_url")]
        public string? ImageUrl { get; set; }
        [JsonPropertyName("source_id")]
        public string? SourceId { get; set; }
        public List<string>? Category { get; set; }
    }

    private class HackerNewsItem
    {
        public string? Title { get; set; }
        public string? Url { get; set; }
        public string? Text { get; set; }
        public int Score { get; set; }
        public long Time { get; set; }
    }

    #endregion
}
