using Azure.AI.OpenAI;
using Azure.Identity;
using ForgeLens.Tools.Image;
using ForgeLens.Tools.News;
using ForgeLens.Tools.Social;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace ForgeLens.Agents.Definitions;

/// <summary>
/// Factory for creating ForgeLens AI agents with their tools
/// </summary>
public class AgentFactory
{
    private readonly AzureOpenAIClient _openAIClient;
    private readonly IChatClient _chatClient;
    private readonly string _gptDeployment;
    private readonly string _dalleDeployment;
    private readonly string _outputDirectory;
    private readonly NewsTools _newsTools;
    private readonly ImageTools _imageTools;
    private readonly ImageEvaluationTools _imageEvaluationTools;
    private readonly SocialMediaTools _socialMediaTools;
    private readonly InstagramPostingTools _instagramPostingTools;
    private readonly string _openAIEndpoint;

    public AgentFactory(
        string openAIEndpoint,
        string gptDeployment,
        string dalleDeployment,
        string outputDirectory,
        string? newsApiKey = null,
        string? gnewsApiKey = null,
        string? newsDataApiKey = null,
        string? instagramUsername = null,
        string? instagramPassword = null)
    {
        _openAIEndpoint = openAIEndpoint;
        _openAIClient = new AzureOpenAIClient(
            new Uri(openAIEndpoint),
            new DefaultAzureCredential());
        
        _gptDeployment = gptDeployment;
        _dalleDeployment = dalleDeployment;
        _outputDirectory = outputDirectory;

        // Create IChatClient using new factory that avoids Azure.AI.OpenAI version conflicts
        _chatClient = AzureOpenAIChatClientFactory.Create(openAIEndpoint, gptDeployment);

        // Initialize tools
        _newsTools = new NewsTools(new HttpClient(), newsApiKey, gnewsApiKey, newsDataApiKey);
        _imageTools = new ImageTools(_openAIClient, dalleDeployment, outputDirectory);
        _imageEvaluationTools = new ImageEvaluationTools(_openAIClient, gptDeployment);
        _socialMediaTools = new SocialMediaTools(_openAIClient, gptDeployment);
        _instagramPostingTools = new InstagramPostingTools(
            instagramUsername ?? "", 
            instagramPassword ?? "");
    }

    /// <summary>
    /// Create the Trend Analyzer Agent
    /// </summary>
    public AIAgent CreateTrendAnalyzerAgent()
    {
        return _chatClient
            .AsAIAgent(
                name: "TrendAnalyzer",
                instructions: @"You are ForgeLens Trend Analyzer - an expert at discovering viral-worthy topics from news.

Your responsibilities:
1. Fetch trending news from multiple sources
2. Analyze stories for meme potential
3. Select the best topic for viral content
4. Create a sarcastic/funny take on the topic
5. Rate virality potential

When asked to find trends:
1. Use FetchTrendingNews to get recent articles
2. Analyze them for humor/meme potential
3. Pick the best one and create a sarcastic take

Always be creative, edgy (but not offensive), and think about what would make people laugh and share.",
                description: "Analyzes news and trends to find the best topics for meme content",
                tools: new[]
                {
                    AIFunctionFactory.Create(_newsTools.FetchTrendingNews)
                });
    }

    /// <summary>
    /// Create the Image Generator Agent
    /// </summary>
    public AIAgent CreateImageGeneratorAgent()
    {
        return _chatClient
            .AsAIAgent(
                name: "ImageGenerator",
                instructions: @"You are ForgeLens Image Generator - an expert at creating viral meme images.

Your responsibilities:
1. Take a meme topic and sarcastic take
2. Design visual concepts that would work well as memes
3. Generate multiple image variations
4. Evaluate which images are best

When creating images:
1. Think about what visual would best convey the humor
2. Use GenerateMemeVariations to create 4 different styles
3. Use EvaluateImage or SelectBestImage to pick the winner

Design principles:
- Clean, striking visuals
- Colors that pop
- No text in images (captions are separate)
- Social media friendly compositions
- Think 'shareable' and 'screenshot-worthy'",
                description: "Generates and evaluates meme images using DALL-E",
                tools: new[]
                {
                    AIFunctionFactory.Create(_imageTools.GenerateMemeImage),
                    AIFunctionFactory.Create(_imageTools.GenerateMemeVariations),
                    AIFunctionFactory.Create(_imageTools.ListGeneratedImages),
                    AIFunctionFactory.Create(_imageTools.GetImagePath),
                    AIFunctionFactory.Create(_imageEvaluationTools.EvaluateImage),
                    AIFunctionFactory.Create(_imageEvaluationTools.SelectBestImage)
                });
    }

    /// <summary>
    /// Create the Social Media Agent
    /// </summary>
    public AIAgent CreateSocialMediaAgent()
    {
        return _chatClient
            .AsAIAgent(
                name: "SocialMediaAgent",
                instructions: @"You are ForgeLens Social Media Agent - an expert at social media compliance and posting.

Your responsibilities:
1. Check content for compliance with Instagram guidelines
2. Generate engaging captions with hashtags
3. Determine optimal posting times
4. Post content to Instagram

When preparing content for posting:
1. Use CheckCompliance to ensure content is safe
2. Use GenerateCaption to create an engaging caption
3. Use GetOptimalPostingTime if timing matters
4. Use PostToInstagram to publish (or dry run to preview)

Always prioritize:
- Brand safety
- Community guidelines compliance
- Engagement optimization
- Authentic, relatable tone",
                description: "Handles compliance checking, caption generation, and posting to Instagram",
                tools: new[]
                {
                    AIFunctionFactory.Create(_socialMediaTools.CheckCompliance),
                    AIFunctionFactory.Create(_socialMediaTools.GenerateCaption),
                    AIFunctionFactory.Create(_socialMediaTools.GetOptimalPostingTime),
                    AIFunctionFactory.Create(_instagramPostingTools.PostToInstagram),
                    AIFunctionFactory.Create(_instagramPostingTools.CheckLoginStatus)
                });
    }

    /// <summary>
    /// Create the main ForgeLens Orchestrator Agent
    /// </summary>
    public AIAgent CreateForgeLensAgent()
    {
        var trendAgent = CreateTrendAnalyzerAgent();
        var imageAgent = CreateImageGeneratorAgent();
        var socialAgent = CreateSocialMediaAgent();

        return _chatClient
            .AsAIAgent(
                name: "ForgeLens",
                instructions: @"You are ForgeLens - the main AI agent that orchestrates viral meme content creation for Instagram.

You coordinate three specialized agents:
1. TrendAnalyzer - finds viral-worthy news topics
2. ImageGenerator - creates meme images
3. SocialMediaAgent - handles compliance and posting

When asked to create and post content:
1. Call TrendAnalyzer to find the best topic
2. Extract the topic and sarcastic take
3. Call ImageGenerator to create images for that topic
4. Get the best image path
5. Call SocialMediaAgent to check compliance and generate caption
6. If approved, call SocialMediaAgent to post

You are the orchestrator - delegate work to your sub-agents but make the final decisions.
Keep the user informed of progress.
If any step fails, explain what went wrong and suggest alternatives.",
                description: "Main orchestrator that coordinates all ForgeLens agents",
                tools: new[]
                {
                    trendAgent.AsAIFunction(),
                    imageAgent.AsAIFunction(),
                    socialAgent.AsAIFunction()
                });
    }

    /// <summary>
    /// Get individual tools for direct access (useful for workflows)
    /// </summary>
    public NewsTools NewsTools => _newsTools;
    public ImageTools ImageTools => _imageTools;
    public ImageEvaluationTools ImageEvaluationTools => _imageEvaluationTools;
    public SocialMediaTools SocialMediaTools => _socialMediaTools;
    public InstagramPostingTools InstagramPostingTools => _instagramPostingTools;
}
