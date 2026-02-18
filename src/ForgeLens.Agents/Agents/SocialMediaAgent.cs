using ForgeLens.Tools.Social;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace ForgeLens.Agents;

/// <summary>
/// AI Agent specialized in social media compliance, caption generation, and Instagram posting
/// </summary>
public class SocialMediaAgent : BaseAgent
{
    private readonly SocialMediaTools _socialMediaTools;
    private readonly InstagramPostingTools _instagramPostingTools;

    public override string Name => "SocialMediaAgent";
    public override string Description => "Handles compliance checking, caption generation, and posting to Instagram";

    public SocialMediaAgent(
        IChatClient chatClient,
        SocialMediaTools socialMediaTools,
        InstagramPostingTools instagramPostingTools) : base(chatClient)
    {
        _socialMediaTools = socialMediaTools;
        _instagramPostingTools = instagramPostingTools;
        Initialize();
    }

    protected override void Initialize()
    {
        Agent = ChatClient.AsAIAgent(
            name: Name,
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
            description: Description,
            tools: new[]
            {
                AIFunctionFactory.Create(_socialMediaTools.CheckCompliance),
                AIFunctionFactory.Create(_socialMediaTools.GenerateCaption),
                AIFunctionFactory.Create(_socialMediaTools.GetOptimalPostingTime),
                AIFunctionFactory.Create(_instagramPostingTools.PostToInstagram),
                AIFunctionFactory.Create(_instagramPostingTools.CheckLoginStatus)
            });
    }
}
