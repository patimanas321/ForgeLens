using ForgeLens.Core.Models;

namespace ForgeLens.Core.Interfaces;

/// <summary>
/// Interface for image evaluation operations.
/// </summary>
public interface IImageEvaluator
{
    /// <summary>
    /// Evaluates a set of images and selects the best one.
    /// </summary>
    /// <param name="images">Images to evaluate.</param>
    /// <param name="topic">The topic for context.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Evaluation result with selected image.</returns>
    Task<ImageEvaluationResult> EvaluateImagesAsync(
        List<GeneratedImage> images,
        TrendingTopic topic,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Scores a single image.
    /// </summary>
    /// <param name="image">The image to score.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Scores for the image.</returns>
    Task<ImageScore> ScoreImageAsync(GeneratedImage image, CancellationToken cancellationToken = default);
}
