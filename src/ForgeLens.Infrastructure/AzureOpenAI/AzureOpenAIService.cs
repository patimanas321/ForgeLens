using Azure;
using Azure.AI.OpenAI;
using Azure.Identity;
using ForgeLens.Core.Configuration;
using ForgeLens.Core.Models;
using OpenAI.Chat;
using OpenAI.Images;
using Serilog;
using System.ClientModel;

namespace ForgeLens.Infrastructure.AzureOpenAI;

/// <summary>
/// Service for interacting with Azure OpenAI models.
/// </summary>
public class AzureOpenAIService
{
    private readonly AzureOpenAIConfiguration _config;
    private readonly ILogger _logger;
    private readonly AzureOpenAIClient _client;

    public AzureOpenAIService(AzureOpenAIConfiguration config, ILogger logger)
    {
        _config = config;
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

        _logger.Information("Azure OpenAI Service initialized with endpoint: {Endpoint}", config.Endpoint);
    }

    /// <summary>
    /// Gets a completion from GPT-4o.
    /// </summary>
    public async Task<string> GetCompletionAsync(
        string systemPrompt,
        string userMessage,
        CancellationToken cancellationToken = default)
    {
        var chatClient = _client.GetChatClient(_config.DeploymentGPT4o);

        var messages = new List<ChatMessage>
        {
            new SystemChatMessage(systemPrompt),
            new UserChatMessage(userMessage)
        };

        var response = await chatClient.CompleteChatAsync(messages, cancellationToken: cancellationToken);
        return response.Value.Content[0].Text;
    }

    /// <summary>
    /// Gets a streaming completion from GPT-4o.
    /// </summary>
    public async IAsyncEnumerable<string> GetStreamingCompletionAsync(
        string systemPrompt,
        string userMessage,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        var chatClient = _client.GetChatClient(_config.DeploymentGPT4o);

        var messages = new List<ChatMessage>
        {
            new SystemChatMessage(systemPrompt),
            new UserChatMessage(userMessage)
        };

        await foreach (var update in chatClient.CompleteChatStreamingAsync(messages, cancellationToken: cancellationToken))
        {
            foreach (var part in update.ContentUpdate)
            {
                if (!string.IsNullOrEmpty(part.Text))
                {
                    yield return part.Text;
                }
            }
        }
    }

    /// <summary>
    /// Analyzes an image using GPT-4o Vision.
    /// </summary>
    public async Task<string> AnalyzeImageAsync(
        string imagePath,
        string analysisPrompt,
        CancellationToken cancellationToken = default)
    {
        var imageBytes = await File.ReadAllBytesAsync(imagePath, cancellationToken);
        var mimeType = GetMimeType(imagePath);
        return await AnalyzeImageFromBytesAsync(imageBytes, mimeType, analysisPrompt, cancellationToken);
    }

    /// <summary>
    /// Analyzes an image from base64 string using GPT-4o Vision.
    /// </summary>
    public async Task<string> AnalyzeImageFromBase64Async(
        string base64Image,
        string mimeType,
        string analysisPrompt,
        CancellationToken cancellationToken = default)
    {
        // Remove data URI prefix if present
        if (base64Image.Contains(","))
        {
            base64Image = base64Image.Substring(base64Image.IndexOf(',') + 1);
        }
        var imageBytes = Convert.FromBase64String(base64Image);
        return await AnalyzeImageFromBytesAsync(imageBytes, mimeType, analysisPrompt, cancellationToken);
    }

    /// <summary>
    /// Analyzes an image from bytes using GPT-4o Vision.
    /// </summary>
    public async Task<string> AnalyzeImageFromBytesAsync(
        byte[] imageBytes,
        string mimeType,
        string analysisPrompt,
        CancellationToken cancellationToken = default)
    {
        var chatClient = _client.GetChatClient(_config.DeploymentGPT4o);

        var imageData = BinaryData.FromBytes(imageBytes);
        var imagePart = ChatMessageContentPart.CreateImagePart(imageData, mimeType);
        var textPart = ChatMessageContentPart.CreateTextPart(analysisPrompt);

        var messages = new List<ChatMessage>
        {
            new SystemChatMessage("You are an expert at analyzing screenshots of websites and extracting structured information. Always respond with valid JSON when requested."),
            new UserChatMessage(textPart, imagePart)
        };

        var response = await chatClient.CompleteChatAsync(messages, cancellationToken: cancellationToken);
        return response.Value.Content[0].Text;
    }

    /// <summary>
    /// Compares multiple images and returns analysis.
    /// </summary>
    public async Task<string> CompareImagesAsync(
        List<string> imagePaths,
        string comparisonPrompt,
        CancellationToken cancellationToken = default)
    {
        var chatClient = _client.GetChatClient(_config.DeploymentGPT4o);

        var contentParts = new List<ChatMessageContentPart>
        {
            ChatMessageContentPart.CreateTextPart(comparisonPrompt)
        };

        foreach (var imagePath in imagePaths)
        {
            var imageBytes = await File.ReadAllBytesAsync(imagePath, cancellationToken);
            var mimeType = GetMimeType(imagePath);
            var imageData = BinaryData.FromBytes(imageBytes);
            contentParts.Add(ChatMessageContentPart.CreateImagePart(imageData, mimeType));
        }

        var messages = new List<ChatMessage>
        {
            new UserChatMessage(contentParts)
        };

        var response = await chatClient.CompleteChatAsync(messages, cancellationToken: cancellationToken);
        return response.Value.Content[0].Text;
    }

    private static string GetMimeType(string filePath)
    {
        var extension = Path.GetExtension(filePath).ToLowerInvariant();
        return extension switch
        {
            ".png" => "image/png",
            ".jpg" or ".jpeg" => "image/jpeg",
            ".gif" => "image/gif",
            ".webp" => "image/webp",
            _ => "image/png"
        };
    }
}
