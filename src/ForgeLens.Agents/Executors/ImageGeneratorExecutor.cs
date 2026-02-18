using ForgeLens.Core.Configuration;
using ForgeLens.Core.Models;
using ForgeLens.Infrastructure.AzureOpenAI;
using Serilog;
using System.Diagnostics;

namespace ForgeLens.Agents.Executors;

/// <summary>
/// Executor that generates images using Azure OpenAI DALL-E 3.
/// </summary>
public class ImageGeneratorExecutor : ExecutorBase<TrendAnalysisResult, ImageGenerationResult>
{
    private readonly DalleImageService _dalleService;
    private readonly ImageGenerationConfiguration _config;

    public ImageGeneratorExecutor(
        DalleImageService dalleService,
        ImageGenerationConfiguration config,
        ILogger logger)
        : base("ImageGenerator", logger)
    {
        _dalleService = dalleService;
        _config = config;
    }

    public override async Task<ImageGenerationResult> ExecuteAsync(
        TrendAnalysisResult input,
        CancellationToken cancellationToken = default)
    {
        var stopwatch = Stopwatch.StartNew();
        Logger.Information("Starting image generation for topic: {Topic}", input.SelectedTopic.Name);
        ReportProgress($"Starting image generation for: {input.SelectedTopic.Name}");

        var images = new List<GeneratedImage>();
        var errors = new List<string>();
        var failureCount = 0;

        // Generate images from the suggested prompts
        var promptsToUse = input.SuggestedPrompts.Take(_config.Variations).ToList();

        // If we don't have enough prompts, generate additional ones
        while (promptsToUse.Count < _config.Variations)
        {
            promptsToUse.Add($"Creative artistic visualization of {input.SelectedTopic.Name}, trending aesthetic, Instagram-worthy, {_config.Style} style, high quality");
        }

        foreach (var prompt in promptsToUse)
        {
            try
            {
                ReportProgress($"Generating image {images.Count + 1}/{_config.Variations}...");

                var image = await _dalleService.GenerateImageAsync(prompt, cancellationToken);
                images.Add(image);

                Logger.Information("Image generated successfully: {ImageId}", image.Id);
                ReportProgress($"Generated: {Path.GetFileName(image.FilePath)}");

                // Small delay between generations
                await Task.Delay(500, cancellationToken);
            }
            catch (Exception ex)
            {
                failureCount++;
                var errorMessage = $"Failed to generate image: {ex.Message}";
                errors.Add(errorMessage);
                Logger.Warning(ex, "Image generation failed for prompt: {Prompt}", prompt.Substring(0, Math.Min(50, prompt.Length)));
            }
        }

        stopwatch.Stop();

        if (!images.Any())
        {
            Logger.Error("No images were generated successfully");
            throw new InvalidOperationException("Failed to generate any images");
        }

        var result = new ImageGenerationResult
        {
            Images = images,
            Topic = input.SelectedTopic,
            GenerationTime = stopwatch.Elapsed,
            FailureCount = failureCount,
            Errors = errors
        };

        Logger.Information("Image generation complete. Generated {Count} images in {Time}",
            images.Count, stopwatch.Elapsed);
        ReportProgress($"Completed: {images.Count} images generated");

        return result;
    }
}
