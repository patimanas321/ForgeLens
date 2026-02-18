using System.ComponentModel;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace ForgeLens.Tools.News;

/// <summary>
/// Tools for fetching news from various sources
/// </summary>
public class NewsTools
{
    private readonly HttpClient _httpClient;
    private readonly string? _newsApiKey;
    private readonly string? _gnewsApiKey;
    private readonly string? _newsDataApiKey;

    public NewsTools(HttpClient httpClient, string? newsApiKey = null, string? gnewsApiKey = null, string? newsDataApiKey = null)
    {
        _httpClient = httpClient;
        _newsApiKey = newsApiKey;
        _gnewsApiKey = gnewsApiKey;
        _newsDataApiKey = newsDataApiKey;
    }

    [Description("Fetch trending news articles from multiple sources. Returns a list of news headlines with summaries for meme topic analysis.")]
    public async Task<string> FetchTrendingNews(
        [Description("Category of news to fetch (e.g., technology, business, entertainment, general)")] string category = "technology",
        [Description("Maximum number of articles to fetch")] int maxArticles = 15)
    {
        var allArticles = new List<NewsArticle>();

        // Try NewsAPI.org
        if (!string.IsNullOrEmpty(_newsApiKey))
        {
            try
            {
                var newsApiArticles = await FetchFromNewsApi(category, maxArticles);
                allArticles.AddRange(newsApiArticles);
            }
            catch { /* Continue to next source */ }
        }

        // Try GNews.io
        if (!string.IsNullOrEmpty(_gnewsApiKey) && allArticles.Count < maxArticles)
        {
            try
            {
                var gnewsArticles = await FetchFromGNews(category, maxArticles - allArticles.Count);
                allArticles.AddRange(gnewsArticles);
            }
            catch { /* Continue to next source */ }
        }

        // Try NewsData.io
        if (!string.IsNullOrEmpty(_newsDataApiKey) && allArticles.Count < maxArticles)
        {
            try
            {
                var newsDataArticles = await FetchFromNewsData(category, maxArticles - allArticles.Count);
                allArticles.AddRange(newsDataArticles);
            }
            catch { /* Continue to next source */ }
        }

        // Fallback to Hacker News (free, no API key)
        if (allArticles.Count < maxArticles)
        {
            try
            {
                var hackerNewsArticles = await FetchFromHackerNews(maxArticles - allArticles.Count);
                allArticles.AddRange(hackerNewsArticles);
            }
            catch { /* Ignore */ }
        }

        if (allArticles.Count == 0)
        {
            return "No news articles could be fetched. Please check API keys or try again later.";
        }

        // Format as readable text for the agent
        var result = $"Found {allArticles.Count} trending articles:\n\n";
        for (int i = 0; i < allArticles.Count; i++)
        {
            var article = allArticles[i];
            result += $"{i + 1}. [{article.Source}] {article.Title}\n";
            if (!string.IsNullOrEmpty(article.Description))
            {
                result += $"   Summary: {article.Description}\n";
            }
            result += $"   Published: {article.PublishedAt:g}\n\n";
        }

        return result;
    }

    private async Task<List<NewsArticle>> FetchFromNewsApi(string category, int count)
    {
        var url = $"https://newsapi.org/v2/top-headlines?category={category}&language=en&pageSize={count}&apiKey={_newsApiKey}";
        var response = await _httpClient.GetFromJsonAsync<NewsApiResponse>(url);
        
        return response?.Articles?.Select(a => new NewsArticle
        {
            Title = a.Title ?? "",
            Description = a.Description,
            Source = a.Source?.Name ?? "NewsAPI",
            PublishedAt = a.PublishedAt ?? DateTime.UtcNow,
            Url = a.Url
        }).ToList() ?? new List<NewsArticle>();
    }

    private async Task<List<NewsArticle>> FetchFromGNews(string category, int count)
    {
        var url = $"https://gnews.io/api/v4/top-headlines?category={category}&lang=en&max={count}&apikey={_gnewsApiKey}";
        var response = await _httpClient.GetFromJsonAsync<GNewsResponse>(url);
        
        return response?.Articles?.Select(a => new NewsArticle
        {
            Title = a.Title ?? "",
            Description = a.Description,
            Source = a.Source?.Name ?? "GNews",
            PublishedAt = a.PublishedAt ?? DateTime.UtcNow,
            Url = a.Url
        }).ToList() ?? new List<NewsArticle>();
    }

    private async Task<List<NewsArticle>> FetchFromNewsData(string category, int count)
    {
        var url = $"https://newsdata.io/api/1/news?category={category}&language=en&apikey={_newsDataApiKey}";
        var response = await _httpClient.GetFromJsonAsync<NewsDataResponse>(url);
        
        return response?.Results?.Take(count).Select(a => new NewsArticle
        {
            Title = a.Title ?? "",
            Description = a.Description,
            Source = a.SourceId ?? "NewsData",
            PublishedAt = a.PubDate ?? DateTime.UtcNow,
            Url = a.Link
        }).ToList() ?? new List<NewsArticle>();
    }

    private async Task<List<NewsArticle>> FetchFromHackerNews(int count)
    {
        var topStoriesUrl = "https://hacker-news.firebaseio.com/v0/topstories.json";
        var storyIds = await _httpClient.GetFromJsonAsync<int[]>(topStoriesUrl);
        
        var articles = new List<NewsArticle>();
        if (storyIds == null) return articles;

        foreach (var id in storyIds.Take(count))
        {
            try
            {
                var storyUrl = $"https://hacker-news.firebaseio.com/v0/item/{id}.json";
                var story = await _httpClient.GetFromJsonAsync<HackerNewsStory>(storyUrl);
                if (story != null && !string.IsNullOrEmpty(story.Title))
                {
                    articles.Add(new NewsArticle
                    {
                        Title = story.Title,
                        Description = story.Text,
                        Source = "Hacker News",
                        PublishedAt = DateTimeOffset.FromUnixTimeSeconds(story.Time).DateTime,
                        Url = story.Url
                    });
                }
            }
            catch { /* Skip failed items */ }
        }

        return articles;
    }
}

// Internal models for API responses
public class NewsArticle
{
    public string Title { get; set; } = "";
    public string? Description { get; set; }
    public string Source { get; set; } = "";
    public DateTime PublishedAt { get; set; }
    public string? Url { get; set; }
}

internal class NewsApiResponse
{
    [JsonPropertyName("articles")]
    public List<NewsApiArticle>? Articles { get; set; }
}

internal class NewsApiArticle
{
    [JsonPropertyName("title")]
    public string? Title { get; set; }
    [JsonPropertyName("description")]
    public string? Description { get; set; }
    [JsonPropertyName("source")]
    public NewsApiSource? Source { get; set; }
    [JsonPropertyName("publishedAt")]
    public DateTime? PublishedAt { get; set; }
    [JsonPropertyName("url")]
    public string? Url { get; set; }
}

internal class NewsApiSource
{
    [JsonPropertyName("name")]
    public string? Name { get; set; }
}

internal class GNewsResponse
{
    [JsonPropertyName("articles")]
    public List<GNewsArticle>? Articles { get; set; }
}

internal class GNewsArticle
{
    [JsonPropertyName("title")]
    public string? Title { get; set; }
    [JsonPropertyName("description")]
    public string? Description { get; set; }
    [JsonPropertyName("source")]
    public GNewsSource? Source { get; set; }
    [JsonPropertyName("publishedAt")]
    public DateTime? PublishedAt { get; set; }
    [JsonPropertyName("url")]
    public string? Url { get; set; }
}

internal class GNewsSource
{
    [JsonPropertyName("name")]
    public string? Name { get; set; }
}

internal class NewsDataResponse
{
    [JsonPropertyName("results")]
    public List<NewsDataArticle>? Results { get; set; }
}

internal class NewsDataArticle
{
    [JsonPropertyName("title")]
    public string? Title { get; set; }
    [JsonPropertyName("description")]
    public string? Description { get; set; }
    [JsonPropertyName("source_id")]
    public string? SourceId { get; set; }
    [JsonPropertyName("pubDate")]
    public DateTime? PubDate { get; set; }
    [JsonPropertyName("link")]
    public string? Link { get; set; }
}

internal class HackerNewsStory
{
    [JsonPropertyName("title")]
    public string? Title { get; set; }
    [JsonPropertyName("text")]
    public string? Text { get; set; }
    [JsonPropertyName("url")]
    public string? Url { get; set; }
    [JsonPropertyName("time")]
    public long Time { get; set; }
}
