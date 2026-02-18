using System.ComponentModel;
using System.Text.Json;
using Azure.AI.OpenAI;
using OpenAI.Chat;

namespace ForgeLens.Tools.Social;

/// <summary>
/// Tools for social media content compliance checking and caption generation
/// </summary>
public class SocialMediaTools
{
    private readonly ChatClient _chatClient;

    public SocialMediaTools(AzureOpenAIClient openAIClient, string gptDeployment)
    {
        _chatClient = openAIClient.GetChatClient(gptDeployment);
    }

    [Description("Check if content (image + caption) is compliant with Instagram community guidelines and brand safety standards.")]
    public async Task<string> CheckCompliance(
        [Description("Path to the image file to check")] string imagePath,
        [Description("The proposed caption text")] string caption,
        [Description("The meme topic/concept")] string concept)
    {
        if (!File.Exists(imagePath))
        {
            return $"Error: Image file not found at {imagePath}";
        }

        var imageBytes = await File.ReadAllBytesAsync(imagePath);

        var messages = new List<ChatMessage>
        {
            new SystemChatMessage(@"You are a social media compliance expert. Review content for:

1. Instagram Community Guidelines compliance
2. Brand safety (no controversial political content, hate speech, etc.)
3. Copyright concerns (no recognizable logos, celebrities, etc.)
4. Appropriateness for general audiences
5. Potential for misinterpretation

Respond in JSON format:
{
    ""isCompliant"": true,
    ""overallRisk"": ""low"",
    ""issues"": [],
    ""warnings"": [],
    ""recommendations"": [],
    ""approvedForPosting"": true
}

Risk levels: low, medium, high, critical
If any critical issues, set approvedForPosting to false."),
            new UserChatMessage(
                ChatMessageContentPart.CreateTextPart($@"Review this content for social media compliance:

Concept: {concept}
Caption: {caption}

Image attached below:"),
                ChatMessageContentPart.CreateImagePart(BinaryData.FromBytes(imageBytes), "image/png"))
        };

        var response = await _chatClient.CompleteChatAsync(messages);
        var responseText = response.Value.Content[0].Text;

        try
        {
            var compliance = JsonSerializer.Deserialize<ComplianceResult>(responseText, new JsonSerializerOptions 
            { 
                PropertyNameCaseInsensitive = true 
            });

            if (compliance != null)
            {
                var statusIcon = compliance.ApprovedForPosting ? "✅" : "❌";
                var riskIcon = compliance.OverallRisk?.ToLower() switch
                {
                    "low" => "🟢",
                    "medium" => "🟡",
                    "high" => "🟠",
                    "critical" => "🔴",
                    _ => "⚪"
                };

                var result = $@"Compliance Check Results
═══════════════════════════════════════════════════
{statusIcon} Status: {(compliance.ApprovedForPosting ? "APPROVED" : "NOT APPROVED")}
{riskIcon} Risk Level: {compliance.OverallRisk?.ToUpper() ?? "UNKNOWN"}
═══════════════════════════════════════════════════";

                if (compliance.Issues?.Count > 0)
                {
                    result += "\n\n⚠️ Issues Found:\n" + string.Join("\n", compliance.Issues.Select(i => $"  • {i}"));
                }

                if (compliance.Warnings?.Count > 0)
                {
                    result += "\n\n⚡ Warnings:\n" + string.Join("\n", compliance.Warnings.Select(w => $"  • {w}"));
                }

                if (compliance.Recommendations?.Count > 0)
                {
                    result += "\n\n💡 Recommendations:\n" + string.Join("\n", compliance.Recommendations.Select(r => $"  • {r}"));
                }

                return result;
            }
        }
        catch
        {
            // Return raw response if parsing fails
        }

        return responseText;
    }

    [Description("Generate an engaging Instagram caption with hashtags for a meme post.")]
    public async Task<string> GenerateCaption(
        [Description("The meme topic/concept")] string concept,
        [Description("The sarcastic/funny take on the topic")] string sarcasticTake,
        [Description("Target audience (e.g., tech professionals, general, millennials)")] string audience = "general")
    {
        var messages = new List<ChatMessage>
        {
            new SystemChatMessage(@"You are a social media content strategist specializing in viral meme content.
Create engaging Instagram captions that:
1. Hook the reader in the first line
2. Include relevant emojis (but not excessive)
3. Have a conversational, relatable tone
4. Include a call-to-action (tag a friend, comment, etc.)
5. Include 5-10 relevant hashtags at the end

Respond in JSON format:
{
    ""caption"": ""The main caption text with emojis..."",
    ""hashtags"": [""#hashtag1"", ""#hashtag2"", ...],
    ""callToAction"": ""Tag someone who..."",
    ""alternativeCaption"": ""A backup option...""
}"),
            new UserChatMessage($@"Create an Instagram caption for this meme:

Topic: {concept}
Sarcastic Take: {sarcasticTake}
Target Audience: {audience}

The post should feel authentic and shareable.")
        };

        var response = await _chatClient.CompleteChatAsync(messages);
        var responseText = response.Value.Content[0].Text;

        try
        {
            var captionResult = JsonSerializer.Deserialize<CaptionResult>(responseText, new JsonSerializerOptions 
            { 
                PropertyNameCaseInsensitive = true 
            });

            if (captionResult != null)
            {
                var hashtagString = string.Join(" ", captionResult.Hashtags ?? new List<string>());
                
                return $@"Generated Caption
═══════════════════════════════════════════════════

{captionResult.Caption}

{captionResult.CallToAction}

{hashtagString}

═══════════════════════════════════════════════════
Alternative Option:
{captionResult.AlternativeCaption}";
            }
        }
        catch
        {
            // Return raw response if parsing fails
        }

        return responseText;
    }

    [Description("Determine the optimal posting time based on the content type and target audience.")]
    public Task<string> GetOptimalPostingTime(
        [Description("Target audience timezone (e.g., US-East, US-West, Europe, Asia)")] string timezone = "US-East",
        [Description("Content type (meme, educational, promotional)")] string contentType = "meme")
    {
        // Best posting times based on research
        var postingTimes = new Dictionary<string, Dictionary<string, string>>
        {
            ["US-East"] = new()
            {
                ["meme"] = "11:00 AM - 1:00 PM EST (lunch hours) or 7:00 PM - 9:00 PM EST (evening)",
                ["educational"] = "9:00 AM - 10:00 AM EST (morning commute)",
                ["promotional"] = "12:00 PM - 2:00 PM EST (lunch break)"
            },
            ["US-West"] = new()
            {
                ["meme"] = "11:00 AM - 1:00 PM PST or 7:00 PM - 9:00 PM PST",
                ["educational"] = "8:00 AM - 9:00 AM PST",
                ["promotional"] = "11:00 AM - 1:00 PM PST"
            },
            ["Europe"] = new()
            {
                ["meme"] = "12:00 PM - 2:00 PM CET or 8:00 PM - 10:00 PM CET",
                ["educational"] = "8:00 AM - 9:00 AM CET",
                ["promotional"] = "1:00 PM - 3:00 PM CET"
            },
            ["Asia"] = new()
            {
                ["meme"] = "12:00 PM - 2:00 PM or 8:00 PM - 10:00 PM local",
                ["educational"] = "7:00 AM - 8:00 AM local",
                ["promotional"] = "12:00 PM - 2:00 PM local"
            }
        };

        var tz = postingTimes.ContainsKey(timezone) ? timezone : "US-East";
        var ct = postingTimes[tz].ContainsKey(contentType) ? contentType : "meme";

        var optimalTime = postingTimes[tz][ct];

        return Task.FromResult($@"Optimal Posting Time Analysis
═══════════════════════════════════════════════════
Timezone: {tz}
Content Type: {ct}
═══════════════════════════════════════════════════

Recommended Posting Windows:
{optimalTime}

Best Days: Tuesday, Wednesday, Thursday
Avoid: Sunday mornings, Monday mornings

Pro Tips:
• Post when your audience is most active
• Engage with comments within the first hour
• Use Instagram Stories to boost visibility");
    }
}

internal class ComplianceResult
{
    public bool IsCompliant { get; set; }
    public string? OverallRisk { get; set; }
    public List<string>? Issues { get; set; }
    public List<string>? Warnings { get; set; }
    public List<string>? Recommendations { get; set; }
    public bool ApprovedForPosting { get; set; }
}

internal class CaptionResult
{
    public string? Caption { get; set; }
    public List<string>? Hashtags { get; set; }
    public string? CallToAction { get; set; }
    public string? AlternativeCaption { get; set; }
}
