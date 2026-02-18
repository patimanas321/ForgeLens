using ForgeLens.Agents.Definitions;
using ForgeLens.Workflows.Models;
using Microsoft.Agents.AI;
using Microsoft.Extensions.Logging;

namespace ForgeLens.Workflows;

/// <summary>
/// Orchestrates the ForgeLens workflow using AI agents
/// </summary>
public class ForgeLensWorkflow
{
    private readonly AgentFactory _agentFactory;
    private readonly ILogger<ForgeLensWorkflow> _logger;
    private readonly AIAgent _trendAgent;
    private readonly AIAgent _imageAgent;
    private readonly AIAgent _socialAgent;

    public ForgeLensWorkflow(AgentFactory agentFactory, ILogger<ForgeLensWorkflow> logger)
    {
        _agentFactory = agentFactory;
        _logger = logger;
        
        // Create agents
        _trendAgent = _agentFactory.CreateTrendAnalyzerAgent();
        _imageAgent = _agentFactory.CreateImageGeneratorAgent();
        _socialAgent = _agentFactory.CreateSocialMediaAgent();
    }

    /// <summary>
    /// Extract text content from AgentResponse
    /// </summary>
    private static string GetResponseText(AgentResponse response)
    {
        // AgentResponse may have different content - try to extract text
        // Check if it has a Text property or convert to string
        return response?.ToString() ?? "";
    }

    /// <summary>
    /// Execute the full ForgeLens workflow
    /// </summary>
    public async Task<ForgeLensWorkflowState> ExecuteAsync(
        string category = "technology",
        bool dryRun = true,
        CancellationToken cancellationToken = default)
    {
        var state = new ForgeLensWorkflowState
        {
            NewsCategory = category,
            DryRun = dryRun,
            Status = WorkflowStatus.AnalyzingTrends
        };

        try
        {
            // Step 1: Analyze Trends
            _logger.LogInformation("Step 1: Analyzing trends...");
            state = await AnalyzeTrendsAsync(state, cancellationToken);
            if (state.Status == WorkflowStatus.Failed) return state;

            // Step 2: Generate Images
            _logger.LogInformation("Step 2: Generating images...");
            state.Status = WorkflowStatus.GeneratingImages;
            state = await GenerateImagesAsync(state, cancellationToken);
            if (state.Status == WorkflowStatus.Failed) return state;

            // Step 3: Evaluate and Select Best Image
            _logger.LogInformation("Step 3: Evaluating images...");
            state.Status = WorkflowStatus.EvaluatingImages;
            state = await EvaluateImagesAsync(state, cancellationToken);
            if (state.Status == WorkflowStatus.Failed) return state;

            // Step 4: Check Compliance
            _logger.LogInformation("Step 4: Checking compliance...");
            state.Status = WorkflowStatus.CheckingCompliance;
            state = await CheckComplianceAsync(state, cancellationToken);
            if (state.Status == WorkflowStatus.Failed) return state;

            // Step 5: Generate Caption
            _logger.LogInformation("Step 5: Generating caption...");
            state.Status = WorkflowStatus.GeneratingCaption;
            state = await GenerateCaptionAsync(state, cancellationToken);
            if (state.Status == WorkflowStatus.Failed) return state;

            // Step 6: Post (if not dry run and compliant)
            if (!dryRun && state.IsCompliant)
            {
                _logger.LogInformation("Step 6: Posting to Instagram...");
                state.Status = WorkflowStatus.Posting;
                state = await PostAsync(state, cancellationToken);
            }
            else
            {
                state.PostingResult = dryRun 
                    ? "Dry run - posting skipped" 
                    : "Content not compliant - posting skipped";
            }

            state.Status = WorkflowStatus.Completed;
            state.CompletedAt = DateTime.UtcNow;
            _logger.LogInformation("Workflow completed successfully!");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Workflow failed");
            state.Status = WorkflowStatus.Failed;
            state.Errors.Add(ex.Message);
        }

        return state;
    }

    private async Task<ForgeLensWorkflowState> AnalyzeTrendsAsync(
        ForgeLensWorkflowState state,
        CancellationToken cancellationToken)
    {
        var step = new WorkflowStep { Name = "AnalyzeTrends", StartedAt = DateTime.UtcNow };

        try
        {
            var prompt = $@"Find trending {state.NewsCategory} news and select the best topic for a viral meme.

1. Fetch trending news
2. Analyze for meme potential
3. Pick the BEST single topic
4. Create a sarcastic/funny take on it

Respond with:
- Selected Topic: [the topic]
- Sarcastic Take: [your funny angle]
- Virality Potential: [1-100]%
- Why this topic: [brief explanation]";

            var result = await _trendAgent.RunAsync(prompt, cancellationToken: cancellationToken);
            var resultText = GetResponseText(result);
            state.TrendAnalysisRaw = resultText;

            // Parse the response (simple parsing)
            var lines = resultText.Split('\n');
            foreach (var line in lines)
            {
                if (line.Contains("Selected Topic:"))
                    state.SelectedTopic = line.Split(':', 2).LastOrDefault()?.Trim();
                else if (line.Contains("Sarcastic Take:"))
                    state.SarcasticTake = line.Split(':', 2).LastOrDefault()?.Trim();
                else if (line.Contains("Virality Potential:"))
                {
                    var scorePart = line.Split(':').LastOrDefault()?.Trim().Replace("%", "");
                    if (int.TryParse(scorePart, out var score))
                        state.ViralityScore = score;
                }
            }

            step.Success = !string.IsNullOrEmpty(state.SelectedTopic);
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);

            if (!step.Success)
            {
                state.Status = WorkflowStatus.Failed;
                state.Errors.Add("Failed to extract topic from trend analysis");
            }
        }
        catch (Exception ex)
        {
            step.Success = false;
            step.Error = ex.Message;
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);
            state.Status = WorkflowStatus.Failed;
            state.Errors.Add($"Trend analysis failed: {ex.Message}");
        }

        return state;
    }

    private async Task<ForgeLensWorkflowState> GenerateImagesAsync(
        ForgeLensWorkflowState state,
        CancellationToken cancellationToken)
    {
        var step = new WorkflowStep { Name = "GenerateImages", StartedAt = DateTime.UtcNow };

        try
        {
            var prompt = $@"Create meme images for this topic:

Topic: {state.SelectedTopic}
Sarcastic Take: {state.SarcasticTake}

Generate 4 different style variations using GenerateMemeVariations. Design visuals that capture the humor and would work well on Instagram.";

            var result = await _imageAgent.RunAsync(prompt, cancellationToken: cancellationToken);
            var resultText = GetResponseText(result);

            // Extract image paths from result
            var lines = resultText.Split('\n');
            foreach (var line in lines)
            {
                if (line.Contains("File:") || line.Contains(".png"))
                {
                    var pathMatch = ExtractPath(line);
                    if (!string.IsNullOrEmpty(pathMatch) && File.Exists(pathMatch))
                    {
                        state.GeneratedImagePaths.Add(pathMatch);
                    }
                }
            }

            step.Success = state.GeneratedImagePaths.Count > 0;
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);

            if (!step.Success)
            {
                state.Status = WorkflowStatus.Failed;
                state.Errors.Add("Failed to generate any images");
            }
        }
        catch (Exception ex)
        {
            step.Success = false;
            step.Error = ex.Message;
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);
            state.Status = WorkflowStatus.Failed;
            state.Errors.Add($"Image generation failed: {ex.Message}");
        }

        return state;
    }

    private async Task<ForgeLensWorkflowState> EvaluateImagesAsync(
        ForgeLensWorkflowState state,
        CancellationToken cancellationToken)
    {
        var step = new WorkflowStep { Name = "EvaluateImages", StartedAt = DateTime.UtcNow };

        try
        {
            var imagePathsList = string.Join(",", state.GeneratedImagePaths);
            var prompt = $@"Evaluate and select the best image from these:

Images: {imagePathsList}

Concept: {state.SelectedTopic} - {state.SarcasticTake}

Use SelectBestImage to evaluate all images and pick the winner.";

            var result = await _imageAgent.RunAsync(prompt, cancellationToken: cancellationToken);
            var resultText = GetResponseText(result);
            state.ImageEvaluationRaw = resultText;

            // Extract best image path and score
            var lines = resultText.Split('\n');
            foreach (var line in lines)
            {
                if (line.Contains("Selected Image:") || line.Contains("WINNER"))
                {
                    var pathMatch = ExtractPath(line);
                    if (!string.IsNullOrEmpty(pathMatch))
                    {
                        state.BestImagePath = pathMatch;
                    }
                }
                if (line.Contains("Score:"))
                {
                    var scorePart = line.Split(':').LastOrDefault()?.Trim().Split('/')[0];
                    if (double.TryParse(scorePart, out var score))
                    {
                        state.BestImageScore = score;
                    }
                }
            }

            // Fallback: use first image if extraction failed
            if (string.IsNullOrEmpty(state.BestImagePath) && state.GeneratedImagePaths.Count > 0)
            {
                state.BestImagePath = state.GeneratedImagePaths[0];
                state.BestImageScore = 7.0;
            }

            step.Success = !string.IsNullOrEmpty(state.BestImagePath);
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);
        }
        catch (Exception ex)
        {
            step.Success = false;
            step.Error = ex.Message;
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);
            
            // Don't fail workflow, use first image as fallback
            if (state.GeneratedImagePaths.Count > 0)
            {
                state.BestImagePath = state.GeneratedImagePaths[0];
                state.BestImageScore = 7.0;
            }
        }

        return state;
    }

    private async Task<ForgeLensWorkflowState> CheckComplianceAsync(
        ForgeLensWorkflowState state,
        CancellationToken cancellationToken)
    {
        var step = new WorkflowStep { Name = "CheckCompliance", StartedAt = DateTime.UtcNow };

        try
        {
            var prompt = $@"Check this content for Instagram compliance:

Image: {state.BestImagePath}
Topic: {state.SelectedTopic}
Sarcastic Take: {state.SarcasticTake}

Use CheckCompliance to verify the content is safe to post.";

            var result = await _socialAgent.RunAsync(prompt, cancellationToken: cancellationToken);
            var resultText = GetResponseText(result);
            state.ComplianceCheckRaw = resultText;

            // Check if approved
            state.IsCompliant = resultText.Contains("APPROVED") || 
                               resultText.Contains("low") && resultText.Contains("Risk") ||
                               !resultText.Contains("NOT APPROVED");

            step.Success = true;
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);
        }
        catch (Exception ex)
        {
            step.Success = false;
            step.Error = ex.Message;
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);
            state.IsCompliant = false; // Fail safe
        }

        return state;
    }

    private async Task<ForgeLensWorkflowState> GenerateCaptionAsync(
        ForgeLensWorkflowState state,
        CancellationToken cancellationToken)
    {
        var step = new WorkflowStep { Name = "GenerateCaption", StartedAt = DateTime.UtcNow };

        try
        {
            var prompt = $@"Generate an engaging Instagram caption:

Topic: {state.SelectedTopic}
Sarcastic Take: {state.SarcasticTake}
Target: Tech-savvy millennials and Gen Z

Use GenerateCaption to create the perfect caption with hashtags.";

            var result = await _socialAgent.RunAsync(prompt, cancellationToken: cancellationToken);
            var resultText = GetResponseText(result);

            // Extract caption and hashtags
            state.Caption = ExtractCaption(resultText);
            state.Hashtags = ExtractHashtags(resultText);

            step.Success = !string.IsNullOrEmpty(state.Caption);
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);
        }
        catch (Exception ex)
        {
            step.Success = false;
            step.Error = ex.Message;
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);
            
            // Fallback caption
            state.Caption = $"😂 {state.SarcasticTake}\n\n{state.SelectedTopic}";
            state.Hashtags = new List<string> { "#meme", "#tech", "#funny", "#viral" };
        }

        return state;
    }

    private async Task<ForgeLensWorkflowState> PostAsync(
        ForgeLensWorkflowState state,
        CancellationToken cancellationToken)
    {
        var step = new WorkflowStep { Name = "Post", StartedAt = DateTime.UtcNow };

        try
        {
            var fullCaption = state.Caption + "\n\n" + string.Join(" ", state.Hashtags);
            
            var prompt = $@"Post to Instagram:

Image: {state.BestImagePath}
Caption: {fullCaption}

Use PostToInstagram with dryRun=false to actually post.";

            var result = await _socialAgent.RunAsync(prompt, cancellationToken: cancellationToken);
            var resultText = GetResponseText(result);
            state.PostingResult = resultText;

            step.Success = resultText.Contains("Successfully") || resultText.Contains("posted");
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);
        }
        catch (Exception ex)
        {
            step.Success = false;
            step.Error = ex.Message;
            step.CompletedAt = DateTime.UtcNow;
            state.CompletedSteps.Add(step);
            state.PostingResult = $"Posting failed: {ex.Message}";
        }

        return state;
    }

    private string? ExtractPath(string line)
    {
        // Try to find a file path in the line
        var parts = line.Split(new[] { ' ', ':', '\t' }, StringSplitOptions.RemoveEmptyEntries);
        foreach (var part in parts)
        {
            if (part.Contains(".png") || part.Contains("/meme_") || part.Contains("\\meme_"))
            {
                var cleaned = part.Trim('`', '"', '\'', ',');
                if (File.Exists(cleaned))
                    return cleaned;
            }
        }
        return null;
    }

    private string ExtractCaption(string result)
    {
        var lines = result.Split('\n');
        var inCaption = false;
        var caption = new List<string>();

        foreach (var line in lines)
        {
            if (line.Contains("Generated Caption") || line.Contains("Caption:"))
            {
                inCaption = true;
                continue;
            }
            if (inCaption && (line.Contains("═") || line.Contains("Alternative") || line.StartsWith("#")))
            {
                break;
            }
            if (inCaption && !string.IsNullOrWhiteSpace(line))
            {
                caption.Add(line.Trim());
            }
        }

        return string.Join("\n", caption);
    }

    private List<string> ExtractHashtags(string result)
    {
        var hashtags = new List<string>();
        var words = result.Split(new[] { ' ', '\n', '\t' }, StringSplitOptions.RemoveEmptyEntries);
        foreach (var word in words)
        {
            if (word.StartsWith("#") && word.Length > 1)
            {
                hashtags.Add(word.Trim(',', '.', '!', '"'));
            }
        }
        return hashtags.Distinct().Take(10).ToList();
    }
}
