using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace ForgeLens.Agents;

/// <summary>
/// Main orchestrator AI Agent that coordinates all other ForgeLens agents
/// </summary>
public class ForgeLensOrchestratorAgent : BaseAgent
{
    private readonly TrendAnalyzerAgent _trendAgent;
    private readonly ImageGeneratorAgent _imageAgent;
    private readonly SocialMediaAgent _socialAgent;

    public override string Name => "ForgeLens";
    public override string Description => "Main orchestrator that coordinates all ForgeLens agents";

    public ForgeLensOrchestratorAgent(
        IChatClient chatClient,
        TrendAnalyzerAgent trendAgent,
        ImageGeneratorAgent imageAgent,
        SocialMediaAgent socialAgent) : base(chatClient)
    {
        _trendAgent = trendAgent;
        _imageAgent = imageAgent;
        _socialAgent = socialAgent;
        Initialize();
    }

    protected override void Initialize()
    {
        Agent = ChatClient.AsAIAgent(
            name: Name,
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
            description: Description,
            tools: new[]
            {
                _trendAgent.AsAIFunction(),
                _imageAgent.AsAIFunction(),
                _socialAgent.AsAIFunction()
            });
    }
}
