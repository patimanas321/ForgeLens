using ForgeLens.Core.Configuration;
using ForgeLens.Core.Models;
using ForgeLens.Infrastructure.AzureOpenAI;
using ForgeLens.Infrastructure.News;
using Serilog;
using System.Diagnostics;

namespace ForgeLens.Agents.Executors;

/// <summary>
/// Executor that analyzes news from multiple APIs and selects topics for meme generation.
/// </summary>
public class TrendAnalyzerExecutor : ExecutorBase<object, TrendAnalysisResult>
{
    private readonly NewsAggregatorService _newsService;
    private readonly MemeTopicSelector _topicSelector;
    private readonly AzureOpenAIService _aiService;

    public TrendAnalyzerExecutor(
        NewsAggregatorService newsService,
        MemeTopicSelector topicSelector,
        AzureOpenAIService aiService,
        ILogger logger)
        : base("TrendAnalyzer", logger)
    {
        _newsService = newsService;
        _topicSelector = topicSelector;
        _aiService = aiService;
    }

    public override async Task<TrendAnalysisResult> ExecuteAsync(
        object input,
        CancellationToken cancellationToken = default)
    {
        var stopwatch = Stopwatch.StartNew();
        Logger.Information("Starting news-based trend analysis...");
        ReportProgress("Fetching news from APIs...");

        // Step 1: Fetch news from multiple APIs
        var articles = await _newsService.FetchAllNewsAsync(cancellationToken);
        Logger.Information("Fetched {Count} news articles", articles.Count);

        // Step 2: Use AI to select the best topics for meme creation
        ReportProgress("Selecting meme-worthy topics...");
        var memeTopics = await _topicSelector.SelectMemeTopicsAsync(articles, topicCount: 3, cancellationToken);
        Logger.Information("Selected {Count} meme topics", memeTopics.Count);

        // Step 3: Select the best topic (highest virality score)
        var selectedMemeTopic = memeTopics.OrderByDescending(t => t.ViralityScore).FirstOrDefault();

        if (selectedMemeTopic == null)
        {
            Logger.Warning("No meme topics selected, using fallback");
            selectedMemeTopic = GetFallbackMemeTopic();
        }

        // Step 4: Generate meme-style DALL-E prompts
        ReportProgress($"Generating meme prompts for: {selectedMemeTopic.Topic}");
        var memePrompts = await _topicSelector.GenerateMemePromptsAsync(selectedMemeTopic, promptCount: 4, cancellationToken);

        stopwatch.Stop();

        // Convert to TrendAnalysisResult format
        var selectedTopic = ConvertToTrendingTopic(selectedMemeTopic);
        var allTrends = memeTopics.Select(ConvertToTrendingTopic).ToList();

        var result = new TrendAnalysisResult
        {
            DiscoveredTrends = allTrends,
            SelectedTopic = selectedTopic,
            ContentBrief = $"🎭 MEME: {selectedMemeTopic.Topic}\n💡 Angle: {selectedMemeTopic.MemeAngle}\n😏 Take: {selectedMemeTopic.SarcasticTake}",
            SuggestedPrompts = memePrompts,
            AnalysisTime = stopwatch.Elapsed,
            SelectionReasoning = $"Selected '{selectedMemeTopic.Topic}' for meme potential (Virality: {selectedMemeTopic.ViralityScore}%)"
        };

        Logger.Information("Trend analysis complete. Selected topic: {Topic}", selectedMemeTopic.Topic);
        Logger.Information("Sarcastic take: {Take}", selectedMemeTopic.SarcasticTake);
        ReportProgress($"Selected: {selectedMemeTopic.Topic}");

        return result;
    }

    private static TrendingTopic ConvertToTrendingTopic(MemeTopicSelection memeTopic)
    {
        return new TrendingTopic
        {
            Name = memeTopic.Topic,
            Category = "Meme",
            Source = "News APIs",
            Description = memeTopic.SarcasticTake,
            EngagementScore = memeTopic.ViralityScore * 100,
            ViralityPotential = memeTopic.ViralityScore / 100.0,
            RelatedKeywords = memeTopic.Hashtags.ToArray()
        };
    }

    private static MemeTopicSelection GetFallbackMemeTopic()
    {
        return new MemeTopicSelection
        {
            Topic = "Monday Motivation",
            MemeAngle = "The eternal struggle of starting a new week",
            SarcasticTake = "Me pretending to be productive while my coffee kicks in",
            Hashtags = ["#MondayMood", "#OfficeLife", "#Relatable", "#WorkHumor", "#MemeMonday"],
            ViralityScore = 70
        };
    }
}
