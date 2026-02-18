using DotNetEnv;
using ForgeLens.Agents;
using ForgeLens.Core.Configuration;
using ForgeLens.Core.Models;
using Microsoft.Extensions.Configuration;
using Serilog;
using Serilog.Events;

namespace ForgeLens.App;

/// <summary>
/// Main entry point for the ForgeLens AI Agent application.
/// </summary>
public class Program
{
    public static async Task<int> Main(string[] args)
    {
        // Load environment variables from .env file
        Env.Load();

        // Configure Serilog
        Log.Logger = new LoggerConfiguration()
            .MinimumLevel.Information()
            .MinimumLevel.Override("Microsoft", LogEventLevel.Warning)
            .Enrich.FromLogContext()
            .WriteTo.Console(
                outputTemplate: "[{Timestamp:HH:mm:ss} {Level:u3}] {Message:lj}{NewLine}{Exception}")
            .WriteTo.File(
                path: "logs/forgelens-.log",
                rollingInterval: RollingInterval.Day,
                outputTemplate: "{Timestamp:yyyy-MM-dd HH:mm:ss.fff zzz} [{Level:u3}] {Message:lj}{NewLine}{Exception}")
            .CreateLogger();

        try
        {
            Log.Information("╔═══════════════════════════════════════════════════════════════╗");
            Log.Information("║                     ForgeLens AI Agent                        ║");
            Log.Information("║      Autonomous Social Media Content Creator & Poster         ║");
            Log.Information("╚═══════════════════════════════════════════════════════════════╝");
            Log.Information("");

            // Load configuration
            var configuration = new ConfigurationBuilder()
                .SetBasePath(Directory.GetCurrentDirectory())
                .AddJsonFile("appsettings.json", optional: true, reloadOnChange: true)
                .AddJsonFile($"appsettings.{Environment.GetEnvironmentVariable("DOTNET_ENVIRONMENT") ?? "Production"}.json", optional: true)
                .AddEnvironmentVariables()
                .Build();

            var config = BuildConfiguration(configuration);

            // Validate configuration
            if (!ValidateConfiguration(config))
            {
                Log.Error("Configuration validation failed. Please check your settings.");
                return 1;
            }

            // Parse command line arguments
            var mode = ParseMode(args);

            Log.Information("Running in mode: {Mode}", mode);
            Log.Information("");

            // Create and run the workflow orchestrator
            await using var orchestrator = new WorkflowOrchestrator(config, Log.Logger);

            WorkflowResult? result = null;

            switch (mode)
            {
                case ExecutionMode.Full:
                    result = await orchestrator.ExecuteAsync();
                    break;

                case ExecutionMode.TrendsOnly:
                    var trendResult = await orchestrator.AnalyzeTrendsOnlyAsync();
                    PrintTrendResults(trendResult);
                    return 0;

                case ExecutionMode.DryRun:
                    var trends = await orchestrator.AnalyzeTrendsOnlyAsync();
                    PrintTrendResults(trends);
                    var evalResult = await orchestrator.GenerateAndEvaluateAsync(trends);
                    PrintEvaluationResults(evalResult);
                    Log.Information("Dry run complete. Images generated but NOT posted.");
                    return 0;
            }

            if (result != null)
            {
                PrintWorkflowResults(result);
                return result.Status == WorkflowStatus.Completed ? 0 : 1;
            }

            return 0;
        }
        catch (Exception ex)
        {
            Log.Fatal(ex, "Application terminated unexpectedly");
            return 1;
        }
        finally
        {
            Log.Information("ForgeLens shutting down...");
            await Log.CloseAndFlushAsync();
        }
    }

    private static ForgeLensConfiguration BuildConfiguration(IConfiguration configuration)
    {
        var config = new ForgeLensConfiguration();

        // Bind from appsettings
        configuration.Bind(config);

        // Override with environment variables (higher priority)
        config.AzureOpenAI.Endpoint = GetEnvOrDefault("AZURE_OPENAI_ENDPOINT", config.AzureOpenAI.Endpoint);
        config.AzureOpenAI.ApiKey = Environment.GetEnvironmentVariable("AZURE_OPENAI_API_KEY");
        config.AzureOpenAI.DeploymentGPT4o = GetEnvOrDefault("AZURE_OPENAI_DEPLOYMENT_GPT4O", 
            GetEnvOrDefault("AZURE_OPENAI_DEPLOYMENT", config.AzureOpenAI.DeploymentGPT4o));
        config.AzureOpenAI.DeploymentDallE = GetEnvOrDefault("AZURE_OPENAI_DEPLOYMENT_DALLE", 
            GetEnvOrDefault("AZURE_OPENAI_DALLE_DEPLOYMENT", config.AzureOpenAI.DeploymentDallE));
        
        // Azure Identity configuration
        if (bool.TryParse(Environment.GetEnvironmentVariable("USE_AZURE_IDENTITY"), out var useIdentity))
        {
            config.AzureOpenAI.UseAzureIdentity = useIdentity;
        }

        // Foundry configuration
        config.Foundry.ProjectEndpoint = GetEnvOrDefault("FOUNDRY_PROJECT_ENDPOINT", config.Foundry.ProjectEndpoint);
        config.Foundry.ModelDeploymentName = GetEnvOrDefault("FOUNDRY_MODEL_DEPLOYMENT_NAME", config.Foundry.ModelDeploymentName);

        // Use Foundry endpoint if Azure OpenAI endpoint is not set
        if (string.IsNullOrEmpty(config.AzureOpenAI.Endpoint) && !string.IsNullOrEmpty(config.Foundry.ProjectEndpoint))
        {
            config.AzureOpenAI.Endpoint = config.Foundry.ProjectEndpoint;
        }

        // Instagram configuration
        config.Instagram.Username = GetEnvOrDefault("INSTAGRAM_USERNAME", config.Instagram.Username);
        config.Instagram.Password = GetEnvOrDefault("INSTAGRAM_PASSWORD", config.Instagram.Password);

        // Image output path
        config.ImageGeneration.OutputPath = GetEnvOrDefault("IMAGE_OUTPUT_PATH", config.ImageGeneration.OutputPath);

        // News API configuration
        config.NewsApi.NewsApiKey = Environment.GetEnvironmentVariable("NEWS_API_KEY");
        config.NewsApi.GNewsApiKey = Environment.GetEnvironmentVariable("GNEWS_API_KEY");
        config.NewsApi.NewsDataApiKey = Environment.GetEnvironmentVariable("NEWSDATA_API_KEY");
        config.NewsApi.Country = GetEnvOrDefault("NEWS_COUNTRY", config.NewsApi.Country);
        if (int.TryParse(Environment.GetEnvironmentVariable("NEWS_MAX_ARTICLES"), out var maxArticles))
        {
            config.NewsApi.MaxArticlesPerSource = maxArticles;
        }

        // Headless mode
        if (bool.TryParse(Environment.GetEnvironmentVariable("HEADLESS_MODE"), out var headless))
        {
            config.HeadlessMode = headless;
        }

        return config;
    }

    private static string GetEnvOrDefault(string key, string defaultValue)
    {
        var value = Environment.GetEnvironmentVariable(key);
        return string.IsNullOrEmpty(value) ? defaultValue : value;
    }

    private static bool ValidateConfiguration(ForgeLensConfiguration config)
    {
        var isValid = true;

        if (string.IsNullOrEmpty(config.AzureOpenAI.Endpoint))
        {
            Log.Error("Azure OpenAI endpoint is not configured. Set AZURE_OPENAI_ENDPOINT or FOUNDRY_PROJECT_ENDPOINT.");
            isValid = false;
        }

        if (string.IsNullOrEmpty(config.Instagram.Username) || string.IsNullOrEmpty(config.Instagram.Password))
        {
            Log.Warning("Instagram credentials not configured. Posting will fail.");
        }

        // Ensure output directory exists
        try
        {
            Directory.CreateDirectory(config.ImageGeneration.OutputPath);
            Directory.CreateDirectory("logs");
        }
        catch (Exception ex)
        {
            Log.Error(ex, "Failed to create output directories");
            isValid = false;
        }

        return isValid;
    }

    private static ExecutionMode ParseMode(string[] args)
    {
        if (args.Contains("--trends-only") || args.Contains("-t"))
            return ExecutionMode.TrendsOnly;

        if (args.Contains("--dry-run") || args.Contains("-d"))
            return ExecutionMode.DryRun;

        return ExecutionMode.Full;
    }

    private static void PrintTrendResults(TrendAnalysisResult result)
    {
        Log.Information("");
        Log.Information("═══════════════════════════════════════════════════════════════");
        Log.Information("                    TREND ANALYSIS RESULTS                      ");
        Log.Information("═══════════════════════════════════════════════════════════════");
        Log.Information("");
        Log.Information("Discovered {Count} trending topics", result.DiscoveredTrends.Count);
        Log.Information("");
        Log.Information("Selected Topic: {TopicName}", result.SelectedTopic.Name);
        Log.Information("Category: {Category}", result.SelectedTopic.Category);
        Log.Information("Virality Potential: {Potential:P0}", result.SelectedTopic.ViralityPotential);
        Log.Information("");
        Log.Information("Content Brief: {Brief}", result.ContentBrief);
        Log.Information("");
        Log.Information("Suggested Prompts:");
        for (int i = 0; i < result.SuggestedPrompts.Count; i++)
        {
            Log.Information("  {Index}. {Prompt}", i + 1, result.SuggestedPrompts[i].Substring(0, Math.Min(80, result.SuggestedPrompts[i].Length)) + "...");
        }
        Log.Information("");
        Log.Information("Analysis Time: {Time}", result.AnalysisTime);
    }

    private static void PrintEvaluationResults(ImageEvaluationResult result)
    {
        Log.Information("");
        Log.Information("═══════════════════════════════════════════════════════════════");
        Log.Information("                   IMAGE EVALUATION RESULTS                     ");
        Log.Information("═══════════════════════════════════════════════════════════════");
        Log.Information("");
        Log.Information("Selected Image: {ImageId}", result.SelectedImage.Id);
        Log.Information("File: {FilePath}", result.SelectedImage.FilePath);
        Log.Information("Overall Score: {Score:F1}/10", result.WinnerScore.OverallScore);
        Log.Information("");
        Log.Information("Scores:");
        Log.Information("  Aesthetic: {Score:F1}/10", result.WinnerScore.AestheticScore);
        Log.Information("  Engagement: {Score:F1}/10", result.WinnerScore.EngagementScore);
        Log.Information("  Technical: {Score:F1}/10", result.WinnerScore.TechnicalScore);
        Log.Information("  Platform Fit: {Score:F1}/10", result.WinnerScore.PlatformFitScore);
        Log.Information("");
        Log.Information("Suggested Caption: {Caption}", result.SuggestedCaption);
        Log.Information("Hashtags: {Hashtags}", string.Join(" ", result.SuggestedHashtags.Take(10)));
    }

    private static void PrintWorkflowResults(WorkflowResult result)
    {
        Log.Information("");
        Log.Information("═══════════════════════════════════════════════════════════════");
        Log.Information("                      WORKFLOW RESULTS                          ");
        Log.Information("═══════════════════════════════════════════════════════════════");
        Log.Information("");
        Log.Information("Run ID: {RunId}", result.RunId);
        Log.Information("Status: {Status}", result.Status);
        Log.Information("Total Time: {Time}", result.TotalTime);
        Log.Information("");

        if (result.Status == WorkflowStatus.Completed)
        {
            Log.Information("✅ Workflow completed successfully!");

            if (result.Posting != null)
            {
                Log.Information("Posted image: {FilePath}", result.Posting.PostedImage.FilePath);
                if (!string.IsNullOrEmpty(result.Posting.PostUrl))
                {
                    Log.Information("Post URL: {Url}", result.Posting.PostUrl);
                }
            }
        }
        else
        {
            Log.Error("❌ Workflow failed");
            if (!string.IsNullOrEmpty(result.ErrorMessage))
            {
                Log.Error("Error: {Error}", result.ErrorMessage);
            }
            if (!string.IsNullOrEmpty(result.FailedPhase))
            {
                Log.Error("Failed at phase: {Phase}", result.FailedPhase);
            }
        }
    }

    private enum ExecutionMode
    {
        Full,
        TrendsOnly,
        DryRun
    }
}
