using Azure;
using Azure.AI.OpenAI;
using Azure.Identity;
using ForgeLens.Core.Configuration;
using ForgeLens.Core.Models;
using OpenAI.Images;
using Serilog;
using CoreGeneratedImage = ForgeLens.Core.Models.GeneratedImage;

namespace ForgeLens.Infrastructure.AzureOpenAI;

/// <summary>
/// Service for generating images using Azure OpenAI DALL-E 3.
/// </summary>
public class DalleImageService
{
    private readonly AzureOpenAIConfiguration _config;
    private readonly ImageGenerationConfiguration _imageConfig;
    private readonly ILogger _logger;
    private readonly AzureOpenAIClient _client;

    public DalleImageService(
        AzureOpenAIConfiguration config,
        ImageGenerationConfiguration imageConfig,
        ILogger logger)
    {
        _config = config;
        _imageConfig = imageConfig;
        _logger = logger;

        if (config.UseAzureIdentity)
        {
            _client = new AzureOpenAIClient(new Uri(config.Endpoint), new DefaultAzureCredential());
        }
        else if (!string.IsNullOrEmpty(config.ApiKey))
        {
            _client = new AzureOpenAIClient(new Uri(config.Endpoint), new AzureKeyCredential(config.ApiKey));
        }
        else
        {
            throw new InvalidOperationException("Either UseAzureIdentity must be true or ApiKey must be provided.");
        }

        // Ensure output directory exists
        Directory.CreateDirectory(_imageConfig.OutputPath);

        _logger.Information("DALL-E Image Service initialized");
    }

    /// <summary>
    /// Generates an image from a prompt.
    /// </summary>
    public async Task<CoreGeneratedImage> GenerateImageAsync(
        string prompt,
        CancellationToken cancellationToken = default)
    {
        _logger.Information("Generating image for prompt: {Prompt}", prompt.Substring(0, Math.Min(50, prompt.Length)) + "...");

        var imageClient = _client.GetImageClient(_config.DeploymentDallE);

        var options = new ImageGenerationOptions
        {
            Quality = _imageConfig.Quality == "hd" ? GeneratedImageQuality.High : GeneratedImageQuality.Standard,
            Size = ParseSize(_imageConfig.Size),
            Style = _imageConfig.Style == "vivid" ? GeneratedImageStyle.Vivid : GeneratedImageStyle.Natural,
            ResponseFormat = GeneratedImageFormat.Bytes
        };

        var response = await imageClient.GenerateImageAsync(prompt, options, cancellationToken);
        var generatedImage = response.Value;

        // Save image to file
        var imageId = Guid.NewGuid().ToString("N")[..8];
        var fileName = $"image_{imageId}_{DateTime.UtcNow:yyyyMMdd_HHmmss}.png";
        var filePath = Path.Combine(_imageConfig.OutputPath, fileName);

        await File.WriteAllBytesAsync(filePath, generatedImage.ImageBytes.ToArray(), cancellationToken);

        var fileInfo = new FileInfo(filePath);

        _logger.Information("Image saved to {FilePath}", filePath);

        return new CoreGeneratedImage
        {
            Id = imageId,
            FilePath = filePath,
            Prompt = prompt,
            RevisedPrompt = generatedImage.RevisedPrompt,
            Size = _imageConfig.Size,
            Quality = _imageConfig.Quality,
            Style = _imageConfig.Style,
            GeneratedAt = DateTime.UtcNow,
            Metadata = new ImageMetadata
            {
                FileSizeBytes = fileInfo.Length,
                Width = ParseWidth(_imageConfig.Size),
                Height = ParseHeight(_imageConfig.Size),
                Format = "PNG"
            }
        };
    }

    /// <summary>
    /// Generates multiple images from different prompts.
    /// </summary>
    public async Task<List<CoreGeneratedImage>> GenerateMultipleImagesAsync(
        List<string> prompts,
        CancellationToken cancellationToken = default)
    {
        var images = new List<CoreGeneratedImage>();

        foreach (var prompt in prompts)
        {
            try
            {
                var image = await GenerateImageAsync(prompt, cancellationToken);
                images.Add(image);

                // Add delay between requests to avoid rate limiting
                await Task.Delay(1000, cancellationToken);
            }
            catch (Exception ex)
            {
                _logger.Warning(ex, "Failed to generate image for prompt: {Prompt}", prompt);
            }
        }

        return images;
    }

    private static GeneratedImageSize ParseSize(string size)
    {
        return size switch
        {
            "1024x1024" => GeneratedImageSize.W1024xH1024,
            "1024x1792" => GeneratedImageSize.W1024xH1792,
            "1792x1024" => GeneratedImageSize.W1792xH1024,
            _ => GeneratedImageSize.W1024xH1024
        };
    }

    private static int ParseWidth(string size) => int.Parse(size.Split('x')[0]);
    private static int ParseHeight(string size) => int.Parse(size.Split('x')[1]);
}
