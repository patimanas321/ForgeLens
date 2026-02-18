using System.ComponentModel;
using System.Net.Http.Json;
using System.ServiceModel.Syndication;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Xml;

namespace ForgeLens.Tools.News;

/// <summary>
/// Tools for fetching news from various sources (India-focused)
/// </summary>
public class NewsTools
{
    private readonly HttpClient _httpClient;
    private readonly string? _newsApiKey;
    private readonly string? _gnewsApiKey;
    private readonly string? _newsDataApiKey;
    private readonly string? _mediaStackApiKey;
    private readonly string? _currentsApiKey;
    private readonly string? _theNewsApiKey;
    private readonly string _country;

    public NewsTools(
        HttpClient httpClient,
        string? newsApiKey = null,
        string? gnewsApiKey = null,
        string? newsDataApiKey = null,
        string? mediaStackApiKey = null,
        string? currentsApiKey = null,
        string? theNewsApiKey = null,
        string country = "in")
    {
        _httpClient = httpClient;
        _newsApiKey = newsApiKey;
        _gnewsApiKey = gnewsApiKey;
        _newsDataApiKey = newsDataApiKey;
        _mediaStackApiKey = mediaStackApiKey;
        _currentsApiKey = currentsApiKey;
        _theNewsApiKey = theNewsApiKey;
        _country = country;
    }

    [Description("Fetch trending news articles from multiple sources (India-focused). Returns a list of news headlines with summaries for meme topic analysis.")]
    public async Task<string> FetchTrendingNews(
        [Description("Category of news to fetch (e.g., technology, business, entertainment, general, sports, science, health, politics)")] string category = "technology",
        [Description("Maximum number of articles to fetch")] int maxArticles = 15)
    {
        var allArticles = new List<NewsArticle>();

        // 1. NewsAPI.org (100 req/day free) — supports country=in
        if (!string.IsNullOrEmpty(_newsApiKey))
        {
            try
            {
                var articles = await FetchFromNewsApi(category, maxArticles);
                allArticles.AddRange(articles);
            }
            catch { /* Continue to next source */ }
        }

        // 2. GNews.io (100 req/day free) — supports country=in
        if (!string.IsNullOrEmpty(_gnewsApiKey) && allArticles.Count < maxArticles)
        {
            try
            {
                var articles = await FetchFromGNews(category, maxArticles - allArticles.Count);
                allArticles.AddRange(articles);
            }
            catch { /* Continue to next source */ }
        }

        // 3. NewsData.io (200 req/day free) — supports country=in
        if (!string.IsNullOrEmpty(_newsDataApiKey) && allArticles.Count < maxArticles)
        {
            try
            {
                var articles = await FetchFromNewsData(category, maxArticles - allArticles.Count);
                allArticles.AddRange(articles);
            }
            catch { /* Continue to next source */ }
        }

        // 4. MediaStack (100 req/month free) — supports countries=in
        if (!string.IsNullOrEmpty(_mediaStackApiKey) && allArticles.Count < maxArticles)
        {
            try
            {
                var articles = await FetchFromMediaStack(category, maxArticles - allArticles.Count);
                allArticles.AddRange(articles);
            }
            catch { /* Continue to next source */ }
        }

        // 5. Currents API (600 req/day free) — supports country=IN
        if (!string.IsNullOrEmpty(_currentsApiKey) && allArticles.Count < maxArticles)
        {
            try
            {
                var articles = await FetchFromCurrentsApi(category, maxArticles - allArticles.Count);
                allArticles.AddRange(articles);
            }
            catch { /* Continue to next source */ }
        }

        // 6. TheNewsAPI (3 req/day free) — supports locale=in
        if (!string.IsNullOrEmpty(_theNewsApiKey) && allArticles.Count < maxArticles)
        {
            try
            {
                var articles = await FetchFromTheNewsApi(category, maxArticles - allArticles.Count);
                allArticles.AddRange(articles);
            }
            catch { /* Continue to next source */ }
        }

        // 7. Google News RSS (FREE, no key, India edition)
        if (allArticles.Count < maxArticles)
        {
            try
            {
                var articles = await FetchFromGoogleNewsRss(category, maxArticles - allArticles.Count);
                allArticles.AddRange(articles);
            }
            catch { /* Continue to next source */ }
        }

        // 8. Hacker News (FREE, no key — tech fallback)
        if (allArticles.Count < maxArticles)
        {
            try
            {
                var articles = await FetchFromHackerNews(maxArticles - allArticles.Count);
                allArticles.AddRange(articles);
            }
            catch { /* Ignore */ }
        }

        if (allArticles.Count == 0)
        {
            return "No news articles could be fetched. Please check API keys or try again later.";
        }

        // Deduplicate by title similarity
        var deduplicated = allArticles
            .GroupBy(a => a.Title.ToLowerInvariant().Trim())
            .Select(g => g.First())
            .Take(maxArticles)
            .ToList();

        // Format as readable text for the agent
        var result = $"Found {deduplicated.Count} trending articles (country: {_country.ToUpperInvariant()}):\n\n";
        for (int i = 0; i < deduplicated.Count; i++)
        {
            var article = deduplicated[i];
            result += $"{i + 1}. [{article.Source}] {article.Title}\n";
            if (!string.IsNullOrEmpty(article.Description))
            {
                result += $"   Summary: {article.Description}\n";
            }
            result += $"   Published: {article.PublishedAt:g}\n\n";
        }

        return result;
    }

    // ─── Source 1: NewsAPI.org ─────────────────────────────────────────────────
    private async Task<List<NewsArticle>> FetchFromNewsApi(string category, int count)
    {
        var url = $"https://newsapi.org/v2/top-headlines?category={category}&country={_country}&pageSize={count}&apiKey={_newsApiKey}";
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

    // ─── Source 2: GNews.io ───────────────────────────────────────────────────
    private async Task<List<NewsArticle>> FetchFromGNews(string category, int count)
    {
        var url = $"https://gnews.io/api/v4/top-headlines?category={category}&lang=en&country={_country}&max={count}&apikey={_gnewsApiKey}";
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

    // ─── Source 3: NewsData.io ────────────────────────────────────────────────
    private async Task<List<NewsArticle>> FetchFromNewsData(string category, int count)
    {
        var url = $"https://newsdata.io/api/1/news?category={category}&country={_country}&language=en&apikey={_newsDataApiKey}";
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

    // ─── Source 4: MediaStack (100 req/month free) ────────────────────────────
    // Docs: https://mediastack.com/documentation
    // Note: Free plan uses HTTP only (no HTTPS)
    private async Task<List<NewsArticle>> FetchFromMediaStack(string category, int count)
    {
        var mappedCategory = MapCategoryForMediaStack(category);
        var url = $"http://api.mediastack.com/v1/news?access_key={_mediaStackApiKey}&countries={_country}&categories={mappedCategory}&languages=en&limit={count}";
        var response = await _httpClient.GetFromJsonAsync<MediaStackResponse>(url);

        return response?.Data?.Select(a => new NewsArticle
        {
            Title = a.Title ?? "",
            Description = a.Description,
            Source = a.Source ?? "MediaStack",
            PublishedAt = a.PublishedAt ?? DateTime.UtcNow,
            Url = a.Url
        }).ToList() ?? new List<NewsArticle>();
    }

    // ─── Source 5: Currents API (600 req/day free) ────────────────────────────
    // Docs: https://currentsapi.services/en/docs/
    private async Task<List<NewsArticle>> FetchFromCurrentsApi(string category, int count)
    {
        var mappedCategory = MapCategoryForCurrents(category);
        var url = $"https://api.currentsapi.services/v1/latest-news?country={_country.ToUpperInvariant()}&category={mappedCategory}&language=en&page_size={count}";
        
        using var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.Add("Authorization", _currentsApiKey);
        
        var httpResponse = await _httpClient.SendAsync(request);
        httpResponse.EnsureSuccessStatusCode();
        
        var response = await httpResponse.Content.ReadFromJsonAsync<CurrentsApiResponse>();

        return response?.News?.Select(a => new NewsArticle
        {
            Title = a.Title ?? "",
            Description = a.Description,
            Source = a.Author?.Any() == true ? string.Join(", ", a.Author) : "Currents",
            PublishedAt = a.Published != null ? DateTime.Parse(a.Published) : DateTime.UtcNow,
            Url = a.Url
        }).Take(count).ToList() ?? new List<NewsArticle>();
    }

    // ─── Source 6: TheNewsAPI (3 req/day free) ────────────────────────────────
    // Docs: https://www.thenewsapi.com/documentation
    private async Task<List<NewsArticle>> FetchFromTheNewsApi(string category, int count)
    {
        var mappedCategory = MapCategoryForTheNewsApi(category);
        var url = $"https://api.thenewsapi.com/v1/news/top?api_token={_theNewsApiKey}&locale={_country}&language=en&categories={mappedCategory}&limit={count}";
        var response = await _httpClient.GetFromJsonAsync<TheNewsApiResponse>(url);

        return response?.Data?.Select(a => new NewsArticle
        {
            Title = a.Title ?? "",
            Description = a.Description ?? a.Snippet,
            Source = a.Source ?? "TheNewsAPI",
            PublishedAt = a.PublishedAt != null ? DateTime.Parse(a.PublishedAt) : DateTime.UtcNow,
            Url = a.Url
        }).ToList() ?? new List<NewsArticle>();
    }

    // ─── Source 7: Google News RSS (FREE, no key) ─────────────────────────────
    private async Task<List<NewsArticle>> FetchFromGoogleNewsRss(string category, int count)
    {
        // Google News RSS topic IDs for major categories
        var topicId = category.ToLowerInvariant() switch
        {
            "technology" => "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pKVGlnQVAB",
            "business" => "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pKVGlnQVAB",
            "entertainment" => "CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pKVGlnQVAB",
            "sports" => "CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pKVGlnQVAB",
            "science" => "CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pKVGlnQVAB",
            "health" => "CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ",
            _ => "" // general/top stories — use main feed
        };

        var hl = _country == "in" ? "en-IN" : "en-US";
        var gl = _country.ToUpperInvariant();
        var ceid = $"{gl}:en";

        string rssUrl;
        if (string.IsNullOrEmpty(topicId))
            rssUrl = $"https://news.google.com/rss?hl={hl}&gl={gl}&ceid={ceid}";
        else
            rssUrl = $"https://news.google.com/rss/topics/{topicId}?hl={hl}&gl={gl}&ceid={ceid}";

        var rssContent = await _httpClient.GetStringAsync(rssUrl);

        using var reader = XmlReader.Create(new StringReader(rssContent));
        var feed = SyndicationFeed.Load(reader);

        return feed.Items.Take(count).Select(item => new NewsArticle
        {
            Title = item.Title?.Text ?? "",
            Description = item.Summary?.Text,
            Source = "Google News",
            PublishedAt = item.PublishDate.DateTime,
            Url = item.Links.FirstOrDefault()?.Uri?.ToString()
        }).ToList();
    }

    // ─── Source 8: Hacker News (FREE, no key) ─────────────────────────────────
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

    // ─── Category Mapping Helpers ─────────────────────────────────────────────
    private static string MapCategoryForMediaStack(string category)
    {
        // MediaStack categories: general, business, entertainment, health, science, sports, technology
        return category.ToLowerInvariant() switch
        {
            "politics" => "general",
            "tech" => "technology",
            _ => category.ToLowerInvariant()
        };
    }

    private static string MapCategoryForCurrents(string category)
    {
        // Currents categories: regional, technology, lifestyle, business, general, programming, science, entertainment, world, sports, finance, academia, politics, health, opinion, food, game
        return category.ToLowerInvariant() switch
        {
            "tech" => "technology",
            _ => category.ToLowerInvariant()
        };
    }

    private static string MapCategoryForTheNewsApi(string category)
    {
        // TheNewsAPI categories: general, science, sports, business, health, entertainment, tech, politics, food, travel
        return category.ToLowerInvariant() switch
        {
            "technology" => "tech",
            _ => category.ToLowerInvariant()
        };
    }
}

// ─── Shared Models ────────────────────────────────────────────────────────────

public class NewsArticle
{
    public string Title { get; set; } = "";
    public string? Description { get; set; }
    public string Source { get; set; } = "";
    public DateTime PublishedAt { get; set; }
    public string? Url { get; set; }
}

// ─── NewsAPI.org ──────────────────────────────────────────────────────────────

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

// ─── GNews.io ─────────────────────────────────────────────────────────────────

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

// ─── NewsData.io ──────────────────────────────────────────────────────────────

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

// ─── MediaStack ───────────────────────────────────────────────────────────────

internal class MediaStackResponse
{
    [JsonPropertyName("data")]
    public List<MediaStackArticle>? Data { get; set; }
}

internal class MediaStackArticle
{
    [JsonPropertyName("title")]
    public string? Title { get; set; }
    [JsonPropertyName("description")]
    public string? Description { get; set; }
    [JsonPropertyName("source")]
    public string? Source { get; set; }
    [JsonPropertyName("published_at")]
    public DateTime? PublishedAt { get; set; }
    [JsonPropertyName("url")]
    public string? Url { get; set; }
    [JsonPropertyName("category")]
    public string? Category { get; set; }
    [JsonPropertyName("country")]
    public string? Country { get; set; }
}

// ─── Currents API ─────────────────────────────────────────────────────────────

internal class CurrentsApiResponse
{
    [JsonPropertyName("news")]
    public List<CurrentsApiArticle>? News { get; set; }
}

internal class CurrentsApiArticle
{
    [JsonPropertyName("title")]
    public string? Title { get; set; }
    [JsonPropertyName("description")]
    public string? Description { get; set; }
    [JsonPropertyName("author")]
    public string[]? Author { get; set; }
    [JsonPropertyName("published")]
    public string? Published { get; set; }
    [JsonPropertyName("url")]
    public string? Url { get; set; }
    [JsonPropertyName("category")]
    public string[]? Category { get; set; }
}

// ─── TheNewsAPI ───────────────────────────────────────────────────────────────

internal class TheNewsApiResponse
{
    [JsonPropertyName("data")]
    public List<TheNewsApiArticle>? Data { get; set; }
}

internal class TheNewsApiArticle
{
    [JsonPropertyName("title")]
    public string? Title { get; set; }
    [JsonPropertyName("description")]
    public string? Description { get; set; }
    [JsonPropertyName("snippet")]
    public string? Snippet { get; set; }
    [JsonPropertyName("source")]
    public string? Source { get; set; }
    [JsonPropertyName("published_at")]
    public string? PublishedAt { get; set; }
    [JsonPropertyName("url")]
    public string? Url { get; set; }
    [JsonPropertyName("categories")]
    public string[]? Categories { get; set; }
    [JsonPropertyName("locale")]
    public string? Locale { get; set; }
}

// ─── Hacker News ──────────────────────────────────────────────────────────────

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
