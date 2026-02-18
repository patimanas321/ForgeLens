using DotNetEnv;
using ForgeLens.Agents.Definitions;
using ForgeLens.Workflows;
using Microsoft.OpenApi.Models;

// Load environment variables - check multiple possible locations
var envPath = Path.Combine(AppContext.BaseDirectory, "../../../..", ".env");
if (File.Exists(envPath))
    Env.Load(envPath);
else if (File.Exists(".env"))
    Env.Load();
else if (File.Exists("../../.env"))
    Env.Load("../../.env");

var builder = WebApplication.CreateBuilder(args);

// Add services to the container
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new OpenApiInfo
    {
        Title = "ForgeLens API",
        Version = "v1",
        Description = "AI-powered viral meme content generator for Instagram"
    });
});

// Register configuration
var config = new ForgeLensApiConfig
{
    AzureOpenAIEndpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT") 
        ?? throw new InvalidOperationException("AZURE_OPENAI_ENDPOINT not configured"),
    GptDeployment = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT") ?? "gpt-4o",
    DalleDeployment = Environment.GetEnvironmentVariable("AZURE_OPENAI_DALLE_DEPLOYMENT") ?? "dall-e-3",
    OutputDirectory = Environment.GetEnvironmentVariable("OUTPUT_DIRECTORY") ?? "./artifacts/images",
    NewsApiKey = Environment.GetEnvironmentVariable("NEWS_API_KEY"),
    GNewsApiKey = Environment.GetEnvironmentVariable("GNEWS_API_KEY"),
    NewsDataApiKey = Environment.GetEnvironmentVariable("NEWSDATA_API_KEY"),
    InstagramUsername = Environment.GetEnvironmentVariable("INSTAGRAM_USERNAME"),
    InstagramPassword = Environment.GetEnvironmentVariable("INSTAGRAM_PASSWORD")
};

builder.Services.AddSingleton(config);

// Register agent factory
builder.Services.AddSingleton<AgentFactory>(sp =>
{
    var cfg = sp.GetRequiredService<ForgeLensApiConfig>();
    return new AgentFactory(
        cfg.AzureOpenAIEndpoint,
        cfg.GptDeployment,
        cfg.DalleDeployment,
        cfg.OutputDirectory,
        cfg.NewsApiKey,
        cfg.GNewsApiKey,
        cfg.NewsDataApiKey,
        cfg.InstagramUsername,
        cfg.InstagramPassword);
});

// Register workflow
builder.Services.AddScoped<ForgeLensWorkflow>();

// Add logging
builder.Services.AddLogging(logging =>
{
    logging.AddConsole();
    logging.SetMinimumLevel(LogLevel.Information);
});

// Add CORS for potential web clients
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

var app = builder.Build();

// Configure the HTTP request pipeline
app.UseSwagger();
app.UseSwaggerUI(c =>
{
    c.SwaggerEndpoint("/swagger/v1/swagger.json", "ForgeLens API v1");
    c.RoutePrefix = string.Empty; // Swagger UI at root
});

app.UseCors();

// Health check endpoint
app.MapGet("/health", () => Results.Ok(new { status = "healthy", timestamp = DateTime.UtcNow }))
   .WithName("HealthCheck")
   .WithOpenApi();

// ============================================
// AGENT CHAT ENDPOINTS
// ============================================

// Main ForgeLens Agent Chat
app.MapPost("/api/agents/forgelens/chat", async (ChatRequest request, AgentFactory factory) =>
{
    var agent = factory.CreateForgeLensAgent();
    var response = await agent.RunAsync(request.Message);
    var responseText = response.Messages?.LastOrDefault()?.Text ?? response.ToString() ?? "";
    return Results.Ok(new ChatResponse { Response = responseText, Agent = "ForgeLens" });
})
.WithName("ChatWithForgeLens")
.WithOpenApi(operation =>
{
    operation.Summary = "Chat with the main ForgeLens orchestrator agent";
    operation.Description = "The main agent that coordinates all other agents to create and post viral meme content";
    return operation;
});

// Trend Analyzer Agent Chat
app.MapPost("/api/agents/trend/chat", async (ChatRequest request, AgentFactory factory) =>
{
    var agent = factory.CreateTrendAnalyzerAgent();
    var response = await agent.RunAsync(request.Message);
    var responseText = response.Messages?.LastOrDefault()?.Text ?? response.ToString() ?? "";
    return Results.Ok(new ChatResponse { Response = responseText, Agent = "TrendAnalyzer" });
})
.WithName("ChatWithTrendAnalyzer")
.WithOpenApi(operation =>
{
    operation.Summary = "Chat with the Trend Analyzer agent";
    operation.Description = "Analyzes news and trends to find viral-worthy meme topics";
    return operation;
});

// Image Generator Agent Chat
app.MapPost("/api/agents/image/chat", async (ChatRequest request, AgentFactory factory) =>
{
    var agent = factory.CreateImageGeneratorAgent();
    var response = await agent.RunAsync(request.Message);
    var responseText = response.Messages?.LastOrDefault()?.Text ?? response.ToString() ?? "";
    return Results.Ok(new ChatResponse { Response = responseText, Agent = "ImageGenerator" });
})
.WithName("ChatWithImageGenerator")
.WithOpenApi(operation =>
{
    operation.Summary = "Chat with the Image Generator agent";
    operation.Description = "Generates and evaluates meme images using DALL-E";
    return operation;
});

// Social Media Agent Chat
app.MapPost("/api/agents/social/chat", async (ChatRequest request, AgentFactory factory) =>
{
    var agent = factory.CreateSocialMediaAgent();
    var response = await agent.RunAsync(request.Message);
    var responseText = response.Messages?.LastOrDefault()?.Text ?? response.ToString() ?? "";
    return Results.Ok(new ChatResponse { Response = responseText, Agent = "SocialMediaAgent" });
})
.WithName("ChatWithSocialMedia")
.WithOpenApi(operation =>
{
    operation.Summary = "Chat with the Social Media agent";
    operation.Description = "Handles compliance checking, caption generation, and Instagram posting";
    return operation;
});

// ============================================
// WORKFLOW ENDPOINTS
// ============================================

// Run full workflow
app.MapPost("/api/workflow/run", async (WorkflowRequest request, AgentFactory factory, ILoggerFactory loggerFactory) =>
{
    var logger = loggerFactory.CreateLogger<ForgeLensWorkflow>();
    var workflow = new ForgeLensWorkflow(factory, logger);
    
    var result = await workflow.ExecuteAsync(
        category: request.Category ?? "technology",
        dryRun: request.DryRun ?? true);
    
    return Results.Ok(result);
})
.WithName("RunWorkflow")
.WithOpenApi(operation =>
{
    operation.Summary = "Run the full ForgeLens workflow";
    operation.Description = "Executes the complete pipeline: trend analysis → image generation → compliance check → caption → post";
    return operation;
});

// Get workflow status (for future async support)
app.MapGet("/api/workflow/status/{workflowId}", (string workflowId) =>
{
    // TODO: Implement workflow status tracking with persistence
    return Results.Ok(new { workflowId, status = "not_implemented", message = "Workflow status tracking coming soon" });
})
.WithName("GetWorkflowStatus")
.WithOpenApi();

// ============================================
// UTILITY ENDPOINTS
// ============================================

// List available agents
app.MapGet("/api/agents", () =>
{
    return Results.Ok(new
    {
        agents = new[]
        {
            new { name = "ForgeLens", endpoint = "/api/agents/forgelens/chat", description = "Main orchestrator agent" },
            new { name = "TrendAnalyzer", endpoint = "/api/agents/trend/chat", description = "News and trend analysis" },
            new { name = "ImageGenerator", endpoint = "/api/agents/image/chat", description = "DALL-E image generation" },
            new { name = "SocialMediaAgent", endpoint = "/api/agents/social/chat", description = "Compliance and posting" }
        }
    });
})
.WithName("ListAgents")
.WithOpenApi();

// List generated images
app.MapGet("/api/images", (ForgeLensApiConfig config) =>
{
    if (!Directory.Exists(config.OutputDirectory))
    {
        return Results.Ok(new { images = Array.Empty<object>() });
    }

    var images = Directory.GetFiles(config.OutputDirectory, "*.png")
        .OrderByDescending(f => File.GetCreationTime(f))
        .Take(20)
        .Select(f => new
        {
            name = Path.GetFileName(f),
            path = f,
            created = File.GetCreationTime(f),
            size = new FileInfo(f).Length
        });

    return Results.Ok(new { images });
})
.WithName("ListImages")
.WithOpenApi();

app.Run();

// ============================================
// REQUEST/RESPONSE MODELS
// ============================================

public record ChatRequest(string Message);
public record ChatResponse
{
    public string Response { get; init; } = "";
    public string Agent { get; init; } = "";
    public DateTime Timestamp { get; init; } = DateTime.UtcNow;
}

public record WorkflowRequest(string? Category, bool? DryRun);

public class ForgeLensApiConfig
{
    public string AzureOpenAIEndpoint { get; set; } = "";
    public string GptDeployment { get; set; } = "gpt-4o";
    public string DalleDeployment { get; set; } = "dall-e-3";
    public string OutputDirectory { get; set; } = "./artifacts/images";
    public string? NewsApiKey { get; set; }
    public string? GNewsApiKey { get; set; }
    public string? NewsDataApiKey { get; set; }
    public string? InstagramUsername { get; set; }
    public string? InstagramPassword { get; set; }
}
