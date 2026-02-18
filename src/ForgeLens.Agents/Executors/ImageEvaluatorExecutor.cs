using ForgeLens.Core.Models;
using ForgeLens.Infrastructure.AzureOpenAI;
using Serilog;
using System.Diagnostics;
using System.Text.Json;

namespace ForgeLens.Agents.Executors;

/// <summary>
/// Executor that evaluates generated images using GPT-4o Vision and selects the best one.
/// </summary>
public class ImageEvaluatorExecutor : ExecutorBase<ImageGenerationResult, ImageEvaluationResult>
{
    private readonly AzureOpenAIService _aiService;

    public ImageEvaluatorExecutor(AzureOpenAIService aiService, ILogger logger)
        : base("ImageEvaluator", logger)
    {
        _aiService = aiService;
    }

    public override async Task<ImageEvaluationResult> ExecuteAsync(
        ImageGenerationResult input,
        CancellationToken cancellationToken = default)
    {
        var stopwatch = Stopwatch.StartNew();
        Logger.Information("Starting image evaluation for {Count} images", input.Images.Count);
        ReportProgress($"Evaluating {input.Images.Count} images...");

        var allScores = new List<ImageScore>();

        // Evaluate each image individually
        foreach (var image in input.Images)
        {
            try
            {
                Logger.Debug("Evaluating image: {ImageId}", image.Id);
                ReportProgress($"Evaluating: {image.Id}");

                var score = await EvaluateSingleImageAsync(image, input.Topic, cancellationToken);
                allScores.Add(score);

                ReportProgress($"Scored {image.Id}: {score.OverallScore:F1}/10");
            }
            catch (Exception ex)
            {
                Logger.Warning(ex, "Failed to evaluate image: {ImageId}", image.Id);

                // Add a default low score for failed evaluations
                allScores.Add(new ImageScore
                {
                    ImageId = image.Id,
                    AestheticScore = 1,
                    EngagementScore = 1,
                    TechnicalScore = 1,
                    PlatformFitScore = 1,
                    Feedback = $"Evaluation failed: {ex.Message}"
                });
            }
        }

        // Select the best image
        var bestScore = allScores.OrderByDescending(s => s.OverallScore).First();
        var selectedImage = input.Images.First(i => i.Id == bestScore.ImageId);

        // Generate caption and hashtags for the winning image
        ReportProgress("Generating caption and hashtags...");
        var (caption, hashtags) = await GenerateCaptionAndHashtagsAsync(selectedImage, input.Topic, cancellationToken);

        stopwatch.Stop();

        var result = new ImageEvaluationResult
        {
            SelectedImage = selectedImage,
            AllScores = allScores,
            SelectionReasoning = bestScore.Feedback ?? $"Selected for highest overall score: {bestScore.OverallScore:F1}/10",
            SuggestedCaption = caption,
            SuggestedHashtags = hashtags,
            EvaluationTime = stopwatch.Elapsed
        };

        Logger.Information("Image evaluation complete. Selected image: {ImageId} with score {Score}/10",
            selectedImage.Id, bestScore.OverallScore);
        ReportProgress($"Selected: {selectedImage.Id} ({bestScore.OverallScore:F1}/10)");

        return result;
    }

    private async Task<ImageScore> EvaluateSingleImageAsync(
        GeneratedImage image,
        TrendingTopic topic,
        CancellationToken cancellationToken)
    {
        var evaluationPrompt = $@"Evaluate this AI-generated image for Instagram posting about '{topic.Name}'.

Score each dimension from 1-10:
1. Aesthetic Quality: Composition, color harmony, visual appeal
2. Engagement Potential: Scroll-stopping power, emotional impact
3. Technical Quality: Resolution, clarity, no artifacts
4. Platform Fit: Instagram optimization, square format suitability

Also provide:
- Brief feedback (1-2 sentences)
- 3 strengths
- 3 weaknesses

Return as JSON:
{{
    ""aestheticScore"": 8,
    ""engagementScore"": 7,
    ""technicalScore"": 9,
    ""platformFitScore"": 8,
    ""feedback"": ""feedback text"",
    ""strengths"": [""strength1"", ""strength2"", ""strength3""],
    ""weaknesses"": [""weakness1"", ""weakness2"", ""weakness3""]
}}";

        var response = await _aiService.AnalyzeImageAsync(image.FilePath, evaluationPrompt, cancellationToken);

        try
        {
            var jsonStart = response.IndexOf('{');
            var jsonEnd = response.LastIndexOf('}') + 1;

            if (jsonStart >= 0 && jsonEnd > jsonStart)
            {
                var jsonContent = response.Substring(jsonStart, jsonEnd - jsonStart);
                var scoreData = JsonSerializer.Deserialize<ImageScoreDto>(jsonContent, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });

                if (scoreData != null)
                {
                    return new ImageScore
                    {
                        ImageId = image.Id,
                        AestheticScore = scoreData.AestheticScore,
                        EngagementScore = scoreData.EngagementScore,
                        TechnicalScore = scoreData.TechnicalScore,
                        PlatformFitScore = scoreData.PlatformFitScore,
                        Feedback = scoreData.Feedback,
                        Strengths = scoreData.Strengths ?? new List<string>(),
                        Weaknesses = scoreData.Weaknesses ?? new List<string>()
                    };
                }
            }
        }
        catch (Exception ex)
        {
            Logger.Warning(ex, "Failed to parse evaluation response for image: {ImageId}", image.Id);
        }

        // Return default score if parsing fails
        return new ImageScore
        {
            ImageId = image.Id,
            AestheticScore = 5,
            EngagementScore = 5,
            TechnicalScore = 5,
            PlatformFitScore = 5,
            Feedback = "Default score due to evaluation parsing failure"
        };
    }

    private async Task<(string Caption, List<string> Hashtags)> GenerateCaptionAndHashtagsAsync(
        GeneratedImage image,
        TrendingTopic topic,
        CancellationToken cancellationToken)
    {
        var captionPrompt = $@"Create an engaging Instagram caption and hashtags for this image about '{topic.Name}'.

The caption should be:
- Attention-grabbing
- Include a call to action
- Be 1-3 sentences
- Include 1-2 relevant emojis

Also provide 15-20 relevant hashtags (without the # symbol).

Return as JSON:
{{
    ""caption"": ""Your caption text here"",
    ""hashtags"": [""hashtag1"", ""hashtag2"", ...]
}}";

        var response = await _aiService.AnalyzeImageAsync(image.FilePath, captionPrompt, cancellationToken);

        try
        {
            var jsonStart = response.IndexOf('{');
            var jsonEnd = response.LastIndexOf('}') + 1;

            if (jsonStart >= 0 && jsonEnd > jsonStart)
            {
                var jsonContent = response.Substring(jsonStart, jsonEnd - jsonStart);
                var captionData = JsonSerializer.Deserialize<CaptionDto>(jsonContent, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });

                if (captionData != null)
                {
                    var hashtags = captionData.Hashtags?
                        .Select(h => h.StartsWith("#") ? h : $"#{h}")
                        .ToList() ?? new List<string>();

                    return (captionData.Caption ?? "", hashtags);
                }
            }
        }
        catch (Exception ex)
        {
            Logger.Warning(ex, "Failed to parse caption response");
        }

        // Fallback caption
        return (
            $"✨ {topic.Name} - What do you think? 💭 Drop your thoughts below! 👇",
            new List<string> { "#ai", "#aiart", "#trending", "#viral", "#creative", "#art", "#instagood" }
        );
    }

    private class ImageScoreDto
    {
        public double AestheticScore { get; set; }
        public double EngagementScore { get; set; }
        public double TechnicalScore { get; set; }
        public double PlatformFitScore { get; set; }
        public string? Feedback { get; set; }
        public List<string>? Strengths { get; set; }
        public List<string>? Weaknesses { get; set; }
    }

    private class CaptionDto
    {
        public string? Caption { get; set; }
        public List<string>? Hashtags { get; set; }
    }
}
