namespace ForgeLens.Core.Configuration;

/// <summary>
/// Configuration for Azure OpenAI services.
/// </summary>
public class AzureOpenAIConfiguration
{
    /// <summary>
    /// Azure OpenAI endpoint URL.
    /// </summary>
    public string Endpoint { get; set; } = string.Empty;

    /// <summary>
    /// API key for Azure OpenAI (use Azure Identity for production).
    /// </summary>
    public string? ApiKey { get; set; }

    /// <summary>
    /// Deployment name for GPT-4o model.
    /// </summary>
    public string DeploymentGPT4o { get; set; } = "gpt-4o";

    /// <summary>
    /// Deployment name for DALL-E 3 model.
    /// </summary>
    public string DeploymentDallE { get; set; } = "dall-e-3";

    /// <summary>
    /// Whether to use Azure Identity for authentication.
    /// </summary>
    public bool UseAzureIdentity { get; set; } = true;
}

/// <summary>
/// Configuration for Azure AI Foundry project.
/// </summary>
public class FoundryConfiguration
{
    /// <summary>
    /// Azure AI Foundry project endpoint.
    /// </summary>
    public string ProjectEndpoint { get; set; } = string.Empty;

    /// <summary>
    /// Model deployment name in Foundry.
    /// </summary>
    public string ModelDeploymentName { get; set; } = string.Empty;
}

/// <summary>
/// Configuration for image generation.
/// </summary>
public class ImageGenerationConfiguration
{
    /// <summary>
    /// Number of image variations to generate.
    /// </summary>
    public int Variations { get; set; } = 4;

    /// <summary>
    /// Image size (e.g., "1024x1024").
    /// </summary>
    public string Size { get; set; } = "1024x1024";

    /// <summary>
    /// Image quality (standard or hd).
    /// </summary>
    public string Quality { get; set; } = "hd";

    /// <summary>
    /// Image style (vivid or natural).
    /// </summary>
    public string Style { get; set; } = "vivid";

    /// <summary>
    /// Output path for generated images.
    /// </summary>
    public string OutputPath { get; set; } = "./artifacts/images";
}

/// <summary>
/// Configuration for human behavior simulation.
/// </summary>
public class HumanBehaviorConfiguration
{
    /// <summary>
    /// Minimum typing delay in milliseconds.
    /// </summary>
    public int MinTypingDelayMs { get; set; } = 50;

    /// <summary>
    /// Maximum typing delay in milliseconds.
    /// </summary>
    public int MaxTypingDelayMs { get; set; } = 150;

    /// <summary>
    /// Minimum delay between actions in milliseconds.
    /// </summary>
    public int MinActionDelayMs { get; set; } = 2000;

    /// <summary>
    /// Maximum delay between actions in milliseconds.
    /// </summary>
    public int MaxActionDelayMs { get; set; } = 8000;

    /// <summary>
    /// Chance of making a typo (0.0 to 1.0).
    /// </summary>
    public double TypoChance { get; set; } = 0.02;

    /// <summary>
    /// Variation in scroll behavior (0.0 to 1.0).
    /// </summary>
    public double ScrollVariation { get; set; } = 0.3;

    /// <summary>
    /// Whether to simulate mouse movement with Bézier curves.
    /// </summary>
    public bool UseBezierMouseMovement { get; set; } = true;
}

/// <summary>
/// Configuration for Instagram posting.
/// </summary>
public class InstagramConfiguration
{
    /// <summary>
    /// Instagram username.
    /// </summary>
    public string Username { get; set; } = string.Empty;

    /// <summary>
    /// Instagram password.
    /// </summary>
    public string Password { get; set; } = string.Empty;

    /// <summary>
    /// Whether to enable filters during posting.
    /// </summary>
    public bool EnableFilters { get; set; } = false;

    /// <summary>
    /// Default hashtags to include.
    /// </summary>
    public List<string> DefaultHashtags { get; set; } = ["#ai", "#aiart", "#trending"];

    /// <summary>
    /// Maximum number of hashtags per post.
    /// </summary>
    public int MaxHashtags { get; set; } = 30;

    /// <summary>
    /// Delay in minutes between posts.
    /// </summary>
    public int PostingDelayMinutes { get; set; } = 30;
}

/// <summary>
/// Configuration for trend sources.
/// </summary>
public class TrendSourcesConfiguration
{
    /// <summary>
    /// List of URLs to scrape for trends.
    /// </summary>
    public List<string> Sources { get; set; } = 
    [
        "https://twitter.com/explore/tabs/trending",
        "https://trends.google.com/trending",
        "https://www.reddit.com/r/popular/"
    ];

    /// <summary>
    /// Maximum trends to fetch per source.
    /// </summary>
    public int MaxTrendsPerSource { get; set; } = 10;
}

/// <summary>
/// Root configuration for ForgeLens application.
/// </summary>
public class ForgeLensConfiguration
{
    /// <summary>
    /// Azure OpenAI configuration.
    /// </summary>
    public AzureOpenAIConfiguration AzureOpenAI { get; set; } = new();

    /// <summary>
    /// Azure AI Foundry configuration.
    /// </summary>
    public FoundryConfiguration Foundry { get; set; } = new();

    /// <summary>
    /// Image generation configuration.
    /// </summary>
    public ImageGenerationConfiguration ImageGeneration { get; set; } = new();

    /// <summary>
    /// Human behavior simulation configuration.
    /// </summary>
    public HumanBehaviorConfiguration HumanBehavior { get; set; } = new();

    /// <summary>
    /// Instagram posting configuration.
    /// </summary>
    public InstagramConfiguration Instagram { get; set; } = new();

    /// <summary>
    /// Trend sources configuration.
    /// </summary>
    public TrendSourcesConfiguration TrendSources { get; set; } = new();

    /// <summary>
    /// News API configuration.
    /// </summary>
    public NewsApiConfiguration NewsApi { get; set; } = new();

    /// <summary>
    /// Whether to run browser in headless mode.
    /// </summary>
    public bool HeadlessMode { get; set; } = false;

    /// <summary>
    /// Enable verbose logging.
    /// </summary>
    public bool VerboseLogging { get; set; } = false;
}
