using ForgeLens.Tools.Image;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace ForgeLens.Agents;

/// <summary>
/// AI Agent specialized in generating and evaluating meme images using DALL-E
/// </summary>
public class ImageGeneratorAgent : BaseAgent
{
    private readonly ImageTools _imageTools;
    private readonly ImageEvaluationTools _imageEvaluationTools;

    public override string Name => "ImageGenerator";
    public override string Description => "Generates and evaluates meme images using DALL-E";

    public ImageGeneratorAgent(
        IChatClient chatClient, 
        ImageTools imageTools,
        ImageEvaluationTools imageEvaluationTools) : base(chatClient)
    {
        _imageTools = imageTools;
        _imageEvaluationTools = imageEvaluationTools;
        Initialize();
    }

    protected override void Initialize()
    {
        Agent = ChatClient.AsAIAgent(
            name: Name,
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
            description: Description,
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
}
