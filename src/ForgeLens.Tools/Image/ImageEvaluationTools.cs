using System.ComponentModel;
using System.Text.Json;
using Azure.AI.OpenAI;
using OpenAI.Chat;

namespace ForgeLens.Tools.Image;

/// <summary>
/// Tools for evaluating image quality using GPT-4 Vision
/// </summary>
public class ImageEvaluationTools
{
    private readonly ChatClient _chatClient;

    public ImageEvaluationTools(AzureOpenAIClient openAIClient, string gptDeployment)
    {
        _chatClient = openAIClient.GetChatClient(gptDeployment);
    }

    [Description("Evaluate a generated meme image for quality, engagement potential, and social media suitability. Returns scores and analysis.")]
    public async Task<string> EvaluateImage(
        [Description("The file path to the image to evaluate")] string imagePath,
        [Description("The original prompt/concept used to generate this image")] string concept)
    {
        if (!File.Exists(imagePath))
        {
            return $"Error: Image file not found at {imagePath}";
        }

        var imageBytes = await File.ReadAllBytesAsync(imagePath);
        var base64Image = Convert.ToBase64String(imageBytes);

        var messages = new List<ChatMessage>
        {
            new SystemChatMessage(@"You are an expert social media content evaluator specializing in meme and viral content analysis.
Evaluate images for their potential to perform well on Instagram and other social platforms.

For each image, provide:
1. Overall Score (1-10)
2. Aesthetic Score (1-10) - visual appeal, composition, colors
3. Engagement Score (1-10) - likelihood to get likes/shares/comments
4. Technical Score (1-10) - image quality, clarity, no artifacts
5. Platform Fit Score (1-10) - appropriateness for Instagram/social media
6. Brief analysis (2-3 sentences)
7. Suggested improvements (if any)

Respond in JSON format:
{
    ""overallScore"": 8.5,
    ""aestheticScore"": 9,
    ""engagementScore"": 8,
    ""technicalScore"": 9,
    ""platformFitScore"": 8,
    ""analysis"": ""..."",
    ""improvements"": ""..."",
    ""recommended"": true
}"),
            new UserChatMessage(
                ChatMessageContentPart.CreateTextPart($"Evaluate this meme image. The original concept was: \"{concept}\""),
                ChatMessageContentPart.CreateImagePart(BinaryData.FromBytes(imageBytes), "image/png"))
        };

        var response = await _chatClient.CompleteChatAsync(messages);
        var responseText = response.Value.Content[0].Text;

        // Parse and format the response
        try
        {
            var evaluation = JsonSerializer.Deserialize<ImageEvaluation>(responseText, new JsonSerializerOptions 
            { 
                PropertyNameCaseInsensitive = true 
            });

            if (evaluation != null)
            {
                return $@"Image Evaluation Results for {Path.GetFileName(imagePath)}:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall Score: {evaluation.OverallScore}/10
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Aesthetic:    {evaluation.AestheticScore}/10
• Engagement:   {evaluation.EngagementScore}/10
• Technical:    {evaluation.TechnicalScore}/10
• Platform Fit: {evaluation.PlatformFitScore}/10
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Analysis: {evaluation.Analysis}

Improvements: {evaluation.Improvements}

Recommended for posting: {(evaluation.Recommended ? "YES ✓" : "NO ✗")}";
            }
        }
        catch
        {
            // If JSON parsing fails, return raw response
        }

        return responseText;
    }

    [Description("Evaluate multiple images and select the best one for posting.")]
    public async Task<string> SelectBestImage(
        [Description("Comma-separated list of image file paths to evaluate")] string imagePaths,
        [Description("The original concept these images were based on")] string concept)
    {
        var paths = imagePaths.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        
        if (paths.Length == 0)
        {
            return "Error: No image paths provided.";
        }

        var evaluations = new List<(string Path, double Score, string Evaluation)>();

        foreach (var path in paths)
        {
            var evaluation = await EvaluateImage(path, concept);
            
            // Extract overall score from evaluation
            var score = ExtractScore(evaluation);
            evaluations.Add((path, score, evaluation));
            
            // Small delay between evaluations
            await Task.Delay(500);
        }

        // Sort by score and get best
        var sorted = evaluations.OrderByDescending(e => e.Score).ToList();
        var best = sorted.First();

        var result = $@"Image Selection Results
═══════════════════════════════════════════════════

Evaluated {paths.Length} images. Rankings:

";
        for (int i = 0; i < sorted.Count; i++)
        {
            var (path, score, _) = sorted[i];
            var marker = i == 0 ? "🏆 WINNER" : $"   #{i + 1}";
            result += $"{marker}: {Path.GetFileName(path)} - Score: {score:F1}/10\n";
        }

        result += $@"
═══════════════════════════════════════════════════
Selected Image: {best.Path}
Score: {best.Score:F1}/10

{best.Evaluation}";

        return result;
    }

    private double ExtractScore(string evaluation)
    {
        // Try to extract "Overall Score: X/10" from evaluation text
        var lines = evaluation.Split('\n');
        foreach (var line in lines)
        {
            if (line.Contains("Overall Score:"))
            {
                var parts = line.Split(':');
                if (parts.Length >= 2)
                {
                    var scorePart = parts[1].Trim().Split('/')[0];
                    if (double.TryParse(scorePart, out var score))
                    {
                        return score;
                    }
                }
            }
        }
        return 5.0; // Default middle score if parsing fails
    }
}

internal class ImageEvaluation
{
    public double OverallScore { get; set; }
    public double AestheticScore { get; set; }
    public double EngagementScore { get; set; }
    public double TechnicalScore { get; set; }
    public double PlatformFitScore { get; set; }
    public string Analysis { get; set; } = "";
    public string Improvements { get; set; } = "";
    public bool Recommended { get; set; }
}
