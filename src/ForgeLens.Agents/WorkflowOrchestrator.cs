using ForgeLens.Agents.Executors;
using ForgeLens.Core.Configuration;
using ForgeLens.Core.Models;
using ForgeLens.Infrastructure.AzureOpenAI;
using ForgeLens.Infrastructure.Browser;
using ForgeLens.Infrastructure.News;
using Serilog;
using System.Diagnostics;

namespace ForgeLens.Agents;

/// <summary>
/// Orchestrates the complete ForgeLens workflow with sequential executor execution.
/// </summary>
public class WorkflowOrchestrator : IAsyncDisposable
{
    private readonly ForgeLensConfiguration _config;
    private readonly ILogger _logger;
    private readonly BrowserSessionManager _browserManager;
    private readonly AzureOpenAIService _aiService;
    private readonly DalleImageService _dalleService;
    private readonly NewsAggregatorService _newsService;
    private readonly MemeTopicSelector _memeSelector;

    /// <summary>
    /// Event raised when any executor reports progress.
    /// </summary>
    public event Action<string, string>? OnProgress;

    public WorkflowOrchestrator(ForgeLensConfiguration config, ILogger logger)
    {
        _config = config;
        _logger = logger;

        // Initialize services
        _browserManager = new BrowserSessionManager(config.HumanBehavior, logger);
        _aiService = new AzureOpenAIService(config.AzureOpenAI, logger);
        _dalleService = new DalleImageService(config.AzureOpenAI, config.ImageGeneration, logger);
        _newsService = new NewsAggregatorService(config.NewsApi, logger);
        _memeSelector = new MemeTopicSelector(_aiService, logger);
    }

    /// <summary>
    /// Executes the complete ForgeLens workflow.
    /// </summary>
    public async Task<WorkflowResult> ExecuteAsync(CancellationToken cancellationToken = default)
    {
        var runId = Guid.NewGuid().ToString("N")[..8];
        var startTime = DateTime.UtcNow;
        var stopwatch = Stopwatch.StartNew();

        _logger.Information("Starting ForgeLens workflow. Run ID: {RunId}", runId);

        TrendAnalysisResult? trendResult = null;
        ImageGenerationResult? imageGenResult = null;
        ImageEvaluationResult? evalResult = null;
        PostingResult? postingResult = null;

        try
        {
            // Phase 1: Trend Analysis
            _logger.Information("Phase 1: Analyzing trends...");
            ReportProgress("Workflow", "Phase 1: Analyzing trends...");

            var trendAnalyzer = CreateTrendAnalyzer();
            trendResult = await trendAnalyzer.ExecuteAsync(new object(), cancellationToken);

            _logger.Information("Trend analysis complete. Selected topic: {Topic}", trendResult.SelectedTopic.Name);
            ReportProgress("Workflow", $"Selected topic: {trendResult.SelectedTopic.Name}");

            // Phase 2: Image Generation
            _logger.Information("Phase 2: Generating images...");
            ReportProgress("Workflow", "Phase 2: Generating images...");

            var imageGenerator = CreateImageGenerator();
            imageGenResult = await imageGenerator.ExecuteAsync(trendResult, cancellationToken);

            _logger.Information("Generated {Count} images", imageGenResult.Images.Count);
            ReportProgress("Workflow", $"Generated {imageGenResult.Images.Count} images");

            // Phase 3: Image Evaluation
            _logger.Information("Phase 3: Evaluating images...");
            ReportProgress("Workflow", "Phase 3: Evaluating images...");

            var imageEvaluator = CreateImageEvaluator();
            evalResult = await imageEvaluator.ExecuteAsync(imageGenResult, cancellationToken);

            _logger.Information("Selected best image: {ImageId}", evalResult.SelectedImage.Id);
            ReportProgress("Workflow", $"Selected: {evalResult.SelectedImage.Id}");

            // Phase 4: Instagram Posting
            _logger.Information("Phase 4: Posting to Instagram...");
            ReportProgress("Workflow", "Phase 4: Posting to Instagram...");

            var instagramPoster = CreateInstagramPoster();
            postingResult = await instagramPoster.ExecuteAsync(evalResult, cancellationToken);

            stopwatch.Stop();

            var status = postingResult.Status == PostingStatus.Success
                ? WorkflowStatus.Completed
                : WorkflowStatus.Failed;

            _logger.Information("Workflow completed with status: {Status}", status);
            ReportProgress("Workflow", $"Completed: {status}");

            return new WorkflowResult
            {
                RunId = runId,
                TrendAnalysis = trendResult,
                ImageGeneration = imageGenResult,
                ImageEvaluation = evalResult,
                Posting = postingResult,
                Status = status,
                TotalTime = stopwatch.Elapsed,
                StartedAt = startTime,
                CompletedAt = DateTime.UtcNow
            };
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.Error(ex, "Workflow failed");
            ReportProgress("Workflow", $"Failed: {ex.Message}");

            return new WorkflowResult
            {
                RunId = runId,
                TrendAnalysis = trendResult,
                ImageGeneration = imageGenResult,
                ImageEvaluation = evalResult,
                Posting = postingResult,
                Status = WorkflowStatus.Failed,
                TotalTime = stopwatch.Elapsed,
                StartedAt = startTime,
                CompletedAt = DateTime.UtcNow,
                ErrorMessage = ex.Message,
                FailedPhase = DetermineFailedPhase(ex)
            };
        }
    }

    /// <summary>
    /// Executes only the trend analysis phase.
    /// </summary>
    public async Task<TrendAnalysisResult> AnalyzeTrendsOnlyAsync(CancellationToken cancellationToken = default)
    {
        _logger.Information("Running trend analysis only");
        ReportProgress("Workflow", "Running trend analysis only...");

        var trendAnalyzer = CreateTrendAnalyzer();
        return await trendAnalyzer.ExecuteAsync(new object(), cancellationToken);
    }

    /// <summary>
    /// Generates and evaluates images without posting.
    /// </summary>
    public async Task<ImageEvaluationResult> GenerateAndEvaluateAsync(
        TrendAnalysisResult trendResult,
        CancellationToken cancellationToken = default)
    {
        _logger.Information("Running image generation and evaluation");
        ReportProgress("Workflow", "Running image generation and evaluation...");

        var imageGenerator = CreateImageGenerator();
        var imageGenResult = await imageGenerator.ExecuteAsync(trendResult, cancellationToken);

        var imageEvaluator = CreateImageEvaluator();
        return await imageEvaluator.ExecuteAsync(imageGenResult, cancellationToken);
    }

    private TrendAnalyzerExecutor CreateTrendAnalyzer()
    {
        var executor = new TrendAnalyzerExecutor(
            _newsService,
            _memeSelector,
            _aiService,
            _logger);
        executor.OnProgress += ReportProgress;
        return executor;
    }

    private ImageGeneratorExecutor CreateImageGenerator()
    {
        var executor = new ImageGeneratorExecutor(
            _dalleService,
            _config.ImageGeneration,
            _logger);
        executor.OnProgress += ReportProgress;
        return executor;
    }

    private ImageEvaluatorExecutor CreateImageEvaluator()
    {
        var executor = new ImageEvaluatorExecutor(_aiService, _logger);
        executor.OnProgress += ReportProgress;
        return executor;
    }

    private InstagramPosterExecutor CreateInstagramPoster()
    {
        var executor = new InstagramPosterExecutor(
            _browserManager,
            _config.Instagram,
            _config.HumanBehavior,
            _logger);
        executor.OnProgress += ReportProgress;
        return executor;
    }

    private void ReportProgress(string executorId, string message)
    {
        OnProgress?.Invoke(executorId, message);
    }

    private static string DetermineFailedPhase(Exception ex)
    {
        var message = ex.Message.ToLower();

        if (message.Contains("trend") || message.Contains("scrape"))
            return "TrendAnalysis";
        if (message.Contains("generate") || message.Contains("dall"))
            return "ImageGeneration";
        if (message.Contains("evaluat") || message.Contains("vision"))
            return "ImageEvaluation";
        if (message.Contains("instagram") || message.Contains("post"))
            return "Posting";

        return "Unknown";
    }

    public async ValueTask DisposeAsync()
    {
        await _browserManager.DisposeAsync();
        GC.SuppressFinalize(this);
    }
}
