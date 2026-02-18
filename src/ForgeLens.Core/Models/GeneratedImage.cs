namespace ForgeLens.Core.Models;

/// <summary>
/// Represents a generated image from DALL-E.
/// </summary>
public record GeneratedImage
{
    /// <summary>
    /// Unique identifier for the image.
    /// </summary>
    public required string Id { get; init; }

    /// <summary>
    /// Local file path where the image is stored.
    /// </summary>
    public required string FilePath { get; init; }

    /// <summary>
    /// The prompt used to generate this image.
    /// </summary>
    public required string Prompt { get; init; }

    /// <summary>
    /// Revised prompt returned by DALL-E (if any).
    /// </summary>
    public string? RevisedPrompt { get; init; }

    /// <summary>
    /// Image size (e.g., "1024x1024").
    /// </summary>
    public required string Size { get; init; }

    /// <summary>
    /// Quality setting used (standard or hd).
    /// </summary>
    public required string Quality { get; init; }

    /// <summary>
    /// Style setting used (vivid or natural).
    /// </summary>
    public required string Style { get; init; }

    /// <summary>
    /// When the image was generated.
    /// </summary>
    public DateTime GeneratedAt { get; init; } = DateTime.UtcNow;

    /// <summary>
    /// Additional metadata.
    /// </summary>
    public ImageMetadata? Metadata { get; init; }
}

/// <summary>
/// Additional metadata for a generated image.
/// </summary>
public record ImageMetadata
{
    /// <summary>
    /// File size in bytes.
    /// </summary>
    public long FileSizeBytes { get; init; }

    /// <summary>
    /// Image width in pixels.
    /// </summary>
    public int Width { get; init; }

    /// <summary>
    /// Image height in pixels.
    /// </summary>
    public int Height { get; init; }

    /// <summary>
    /// Image format (e.g., PNG, JPEG).
    /// </summary>
    public string? Format { get; init; }

    /// <summary>
    /// Content hash for deduplication.
    /// </summary>
    public string? ContentHash { get; init; }
}

/// <summary>
/// Result of the image generation phase.
/// </summary>
public record ImageGenerationResult
{
    /// <summary>
    /// All generated images.
    /// </summary>
    public required List<GeneratedImage> Images { get; init; }

    /// <summary>
    /// The topic used for generation.
    /// </summary>
    public required TrendingTopic Topic { get; init; }

    /// <summary>
    /// Time taken to generate all images.
    /// </summary>
    public TimeSpan GenerationTime { get; init; }

    /// <summary>
    /// Number of images successfully generated.
    /// </summary>
    public int SuccessCount => Images.Count;

    /// <summary>
    /// Number of generation failures.
    /// </summary>
    public int FailureCount { get; init; }

    /// <summary>
    /// Any errors encountered during generation.
    /// </summary>
    public List<string> Errors { get; init; } = [];
}
