using System.ComponentModel;
using Azure.AI.OpenAI;
using OpenAI.Images;

namespace ForgeLens.Tools.Image;

/// <summary>
/// Tools for generating and managing images using DALL-E
/// </summary>
public class ImageTools
{
    private readonly ImageClient _imageClient;
    private readonly string _outputDirectory;

    public ImageTools(AzureOpenAIClient openAIClient, string dalleDeployment, string outputDirectory)
    {
        _imageClient = openAIClient.GetImageClient(dalleDeployment);
        _outputDirectory = outputDirectory;
        Directory.CreateDirectory(_outputDirectory);
    }

    [Description("Generate a meme-style image using DALL-E 3. Returns the file path of the generated image.")]
    public async Task<string> GenerateMemeImage(
        [Description("The detailed prompt for image generation. Should describe the meme scene, style, and mood.")] string prompt,
        [Description("The visual style (e.g., 'cartoon', 'comic', 'minimalist', 'editorial')")] string style = "cartoon")
    {
        // Enhance prompt with meme-appropriate styling
        var enhancedPrompt = $"{prompt}. Style: {style} illustration, suitable for social media, vibrant colors, " +
                            "clean composition, no text overlays, high contrast, visually striking.";

        var options = new ImageGenerationOptions
        {
            Quality = GeneratedImageQuality.High,
            Size = GeneratedImageSize.W1024xH1024,
            Style = GeneratedImageStyle.Vivid
        };

        var result = await _imageClient.GenerateImageAsync(enhancedPrompt, options);
        var imageUri = result.Value.ImageUri;

        // Download and save the image
        var imageId = Guid.NewGuid().ToString("N")[..8];
        var timestamp = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss");
        var fileName = $"meme_{imageId}_{timestamp}.png";
        var filePath = Path.Combine(_outputDirectory, fileName);

        using var httpClient = new HttpClient();
        var imageBytes = await httpClient.GetByteArrayAsync(imageUri);
        await File.WriteAllBytesAsync(filePath, imageBytes);

        return $"Image generated successfully.\nFile: {filePath}\nImage ID: {imageId}\nStyle: {style}";
    }

    [Description("Generate multiple image variations for the same meme concept. Returns paths to all generated images.")]
    public async Task<string> GenerateMemeVariations(
        [Description("The base prompt describing the meme concept")] string prompt,
        [Description("Number of variations to generate (1-4)")] int count = 4)
    {
        count = Math.Clamp(count, 1, 4);
        var styles = new[] { "cartoon", "retro comic book", "modern flat illustration", "editorial cartoon" };
        var results = new List<string>();

        for (int i = 0; i < count; i++)
        {
            var style = styles[i % styles.Length];
            var result = await GenerateMemeImage(prompt, style);
            results.Add(result);
            
            // Small delay to avoid rate limiting
            if (i < count - 1)
            {
                await Task.Delay(1000);
            }
        }

        return $"Generated {count} image variations:\n\n" + string.Join("\n---\n", results);
    }

    [Description("List all generated images in the output directory.")]
    public Task<string> ListGeneratedImages()
    {
        var files = Directory.GetFiles(_outputDirectory, "meme_*.png")
            .OrderByDescending(f => File.GetCreationTime(f))
            .Take(20)
            .ToList();

        if (files.Count == 0)
        {
            return Task.FromResult("No generated images found.");
        }

        var result = $"Found {files.Count} generated images:\n\n";
        foreach (var file in files)
        {
            var info = new FileInfo(file);
            result += $"- {info.Name} ({info.Length / 1024}KB, created {info.CreationTime:g})\n";
        }

        return Task.FromResult(result);
    }

    [Description("Get the file path for a specific image by its ID.")]
    public Task<string> GetImagePath([Description("The image ID (8 character hex string)")] string imageId)
    {
        var files = Directory.GetFiles(_outputDirectory, $"meme_{imageId}*.png");
        
        if (files.Length == 0)
        {
            return Task.FromResult($"No image found with ID: {imageId}");
        }

        return Task.FromResult($"Image path: {files[0]}");
    }
}
