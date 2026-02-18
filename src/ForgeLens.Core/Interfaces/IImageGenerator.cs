using ForgeLens.Core.Models;

namespace ForgeLens.Core.Interfaces;

/// <summary>
/// Interface for image generation operations.
/// </summary>
public interface IImageGenerator
{
    /// <summary>
    /// Generates images based on a topic.
    /// </summary>
    /// <param name="topic">The trending topic to generate images for.</param>
    /// <param name="prompts">Specific prompts to use.</param>
    /// <param name="count">Number of images to generate.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Generation result with images.</returns>
    Task<ImageGenerationResult> GenerateImagesAsync(
        TrendingTopic topic,
        List<string> prompts,
        int count = 4,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Generates a single image from a prompt.
    /// </summary>
    /// <param name="prompt">The prompt for image generation.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The generated image.</returns>
    Task<GeneratedImage> GenerateSingleImageAsync(string prompt, CancellationToken cancellationToken = default);
}
