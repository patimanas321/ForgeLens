using ForgeLens.Core.Models;
using ForgeLens.Infrastructure.AzureOpenAI;
using Serilog;
using System.Text.Json;

namespace ForgeLens.Infrastructure.News;

/// <summary>
/// Uses AI to select the best news topics for meme generation.
/// </summary>
public class MemeTopicSelector
{
    private readonly AzureOpenAIService _aiService;
    private readonly ILogger _logger;

    public MemeTopicSelector(AzureOpenAIService aiService, ILogger logger)
    {
        _aiService = aiService;
        _logger = logger;
    }

    /// <summary>
    /// Analyzes news articles and selects the best topics for meme creation.
    /// </summary>
    public async Task<List<MemeTopicSelection>> SelectMemeTopicsAsync(
        List<NewsArticle> articles,
        int topicCount = 3,
        CancellationToken cancellationToken = default)
    {
        if (articles.Count == 0)
        {
            _logger.Warning("No articles provided for topic selection");
            return GetFallbackTopics();
        }

        var articleSummaries = articles
            .Take(20) // Limit to avoid token overflow
            .Select((a, i) => $"{i + 1}. [{a.Source}] {a.Title}")
            .ToList();

        var prompt = $@"You are a viral meme creator for Instagram. Analyze these news headlines and select the {topicCount} BEST topics for creating funny, sarcastic, meme-style images.

Headlines:
{string.Join("\n", articleSummaries)}

For each selected topic, provide:
1. The main topic (simplified headline)
2. A sarcastic/funny angle for a meme
3. A witty one-liner or caption
4. Suggested hashtags (5-7)
5. Virality score (0-100)

IMPORTANT: Choose topics that are:
- Universally relatable
- Safe for humor (avoid tragedies, deaths, violence)
- Good for visual representation
- Trending and timely

Return as JSON array:
[
  {{
    ""topic"": ""Short topic title"",
    ""memeAngle"": ""The sarcastic/ironic angle"",
    ""sarcasticTake"": ""A funny one-liner for the meme"",
    ""hashtags"": [""#hashtag1"", ""#hashtag2""],
    ""viralityScore"": 85,
    ""relatedIndices"": [1, 5]
  }}
]";

        try
        {
            var response = await _aiService.GetCompletionAsync(
                "You are a professional meme creator and social media strategist with expertise in viral content. Always respond with valid JSON.",
                prompt,
                cancellationToken);

            var topics = ParseTopicSelections(response, articles);
            
            if (topics.Count > 0)
            {
                _logger.Information("Selected {Count} meme topics from news", topics.Count);
                return topics;
            }
        }
        catch (Exception ex)
        {
            _logger.Warning(ex, "Failed to select meme topics via AI");
        }

        return GetFallbackTopics();
    }

    /// <summary>
    /// Generates DALL-E prompts for meme-style images.
    /// </summary>
    public async Task<List<string>> GenerateMemePromptsAsync(
        MemeTopicSelection topic,
        int promptCount = 4,
        CancellationToken cancellationToken = default)
    {
        var prompt = $@"Create {promptCount} DALL-E 3 image prompts for a funny, sarcastic meme about:

Topic: {topic.Topic}
Angle: {topic.MemeAngle}
Caption idea: {topic.SarcasticTake}

Requirements for each prompt:
- Cartoon/illustration style (NOT photorealistic)
- Exaggerated, satirical visual metaphor
- Bold, vibrant colors suitable for Instagram
- No text in the image (caption will be added separately)
- Safe for all audiences
- Meme-worthy and shareable

Styles to vary across prompts:
1. Modern flat illustration style
2. Retro comic book style
3. Cute cartoon characters style
4. Editorial cartoon/caricature style

Return ONLY a JSON array of prompt strings:
[""prompt1"", ""prompt2"", ""prompt3"", ""prompt4""]";

        try
        {
            var response = await _aiService.GetCompletionAsync(
                "You are an expert at creating DALL-E prompts for viral social media meme images. Create visually striking, shareable content.",
                prompt,
                cancellationToken);

            var prompts = ParsePrompts(response);
            
            if (prompts.Count > 0)
            {
                _logger.Information("Generated {Count} meme prompts for topic: {Topic}", prompts.Count, topic.Topic);
                return prompts;
            }
        }
        catch (Exception ex)
        {
            _logger.Warning(ex, "Failed to generate meme prompts");
        }

        // Fallback prompts
        return GenerateFallbackPrompts(topic);
    }

    private List<MemeTopicSelection> ParseTopicSelections(string json, List<NewsArticle> articles)
    {
        var topics = new List<MemeTopicSelection>();

        try
        {
            var jsonStart = json.IndexOf('[');
            var jsonEnd = json.LastIndexOf(']') + 1;

            if (jsonStart >= 0 && jsonEnd > jsonStart)
            {
                var jsonContent = json.Substring(jsonStart, jsonEnd - jsonStart);
                var parsed = JsonSerializer.Deserialize<List<TopicSelectionDto>>(jsonContent, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });

                if (parsed != null)
                {
                    foreach (var dto in parsed)
                    {
                        var relatedArticles = dto.RelatedIndices?
                            .Where(i => i > 0 && i <= articles.Count)
                            .Select(i => articles[i - 1])
                            .ToList() ?? [];

                        topics.Add(new MemeTopicSelection
                        {
                            Topic = dto.Topic ?? "Trending News",
                            MemeAngle = dto.MemeAngle ?? "The irony of it all",
                            SarcasticTake = dto.SarcasticTake ?? "When reality is stranger than fiction",
                            Hashtags = dto.Hashtags ?? ["#meme", "#trending", "#viral"],
                            ViralityScore = dto.ViralityScore,
                            RelatedArticles = relatedArticles
                        });
                    }
                }
            }
        }
        catch (Exception ex)
        {
            _logger.Warning(ex, "Failed to parse topic selections");
        }

        return topics;
    }

    private List<string> ParsePrompts(string json)
    {
        try
        {
            var jsonStart = json.IndexOf('[');
            var jsonEnd = json.LastIndexOf(']') + 1;

            if (jsonStart >= 0 && jsonEnd > jsonStart)
            {
                var jsonContent = json.Substring(jsonStart, jsonEnd - jsonStart);
                return JsonSerializer.Deserialize<List<string>>(jsonContent) ?? [];
            }
        }
        catch (Exception ex)
        {
            _logger.Warning(ex, "Failed to parse prompts");
        }

        return [];
    }

    private List<string> GenerateFallbackPrompts(MemeTopicSelection topic)
    {
        return new List<string>
        {
            $"A colorful flat illustration in modern cartoon style showing a humorous take on {topic.Topic}, with exaggerated expressions, bold colors, Instagram-ready meme format, no text",
            $"Retro comic book style illustration satirizing {topic.Topic}, with vibrant pop art colors, halftone dots, dramatic poses, funny and shareable, no text in image",
            $"Cute cartoon characters in kawaii style reacting to {topic.Topic}, pastel and bright colors, expressive faces, perfect for social media meme, no text",
            $"Editorial cartoon style illustration about {topic.Topic}, clever visual metaphor, bold outlines, satirical and witty, magazine cover quality, no text in the image"
        };
    }

    private List<MemeTopicSelection> GetFallbackTopics()
    {
        return new List<MemeTopicSelection>
        {
            new()
            {
                Topic = "Tech Companies and AI",
                MemeAngle = "Every company is now an 'AI company'",
                SarcasticTake = "When your toaster gets an AI upgrade but still burns toast",
                Hashtags = ["#AI", "#Tech", "#FutureTech", "#Memes", "#Trending"],
                ViralityScore = 75
            },
            new()
            {
                Topic = "Work From Home Life",
                MemeAngle = "The eternal struggle of 'just one more meeting'",
                SarcasticTake = "My commute is now from bed to desk. Peak evolution.",
                Hashtags = ["#WFH", "#RemoteWork", "#WorkLife", "#OfficeHumor", "#Relatable"],
                ViralityScore = 80
            }
        };
    }

    private class TopicSelectionDto
    {
        public string? Topic { get; set; }
        public string? MemeAngle { get; set; }
        public string? SarcasticTake { get; set; }
        public List<string>? Hashtags { get; set; }
        public int ViralityScore { get; set; }
        public List<int>? RelatedIndices { get; set; }
    }
}
