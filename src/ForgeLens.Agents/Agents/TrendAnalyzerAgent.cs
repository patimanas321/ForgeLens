using ForgeLens.Tools.News;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace ForgeLens.Agents;

/// <summary>
/// AI Agent specialized in analyzing news and trends to find viral-worthy topics
/// </summary>
public class TrendAnalyzerAgent : BaseAgent
{
    private readonly NewsTools _newsTools;

    public override string Name => "TrendAnalyzer";
    public override string Description => "Analyzes news and trends to find the best topics for meme content";

    public TrendAnalyzerAgent(IChatClient chatClient, NewsTools newsTools) : base(chatClient)
    {
        _newsTools = newsTools;
        Initialize();
    }

    protected override void Initialize()
    {
        Agent = ChatClient.AsAIAgent(
            name: Name,
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
            description: Description,
            tools: new[]
            {
                AIFunctionFactory.Create(_newsTools.FetchTrendingNews)
            });
    }
}
