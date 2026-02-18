using System.ClientModel;
using Azure.Identity;
using Microsoft.Extensions.AI;
using OpenAI;
using OpenAI.Chat;

namespace ForgeLens.Agents;

/// <summary>
/// Factory to create IChatClient for Azure OpenAI using OpenAI SDK directly
/// The OpenAI SDK supports Azure OpenAI endpoints when configured correctly
/// </summary>
public static class AzureOpenAIChatClientFactory
{
    public static IChatClient Create(string endpoint, string deploymentName)
    {
        // Get bearer token from Azure AD
        var credential = new DefaultAzureCredential();
        var tokenRequest = new Azure.Core.TokenRequestContext(new[] { "https://cognitiveservices.azure.com/.default" });
        var token = credential.GetToken(tokenRequest, default);
        
        // Build Azure OpenAI endpoint URL with deployment name
        // Azure OpenAI format: {endpoint}/openai/deployments/{deployment}/
        var azureEndpoint = new Uri($"{endpoint.TrimEnd('/')}/openai/deployments/{deploymentName}/");
        
        var options = new OpenAIClientOptions
        {
            Endpoint = azureEndpoint
        };
        
        // Add api-version query string required by Azure OpenAI
        options.AddPolicy(new AzureApiVersionPolicy("2024-10-21"), System.ClientModel.Primitives.PipelinePosition.PerCall);
        
        // Add bearer token auth - runs before transport to override SDK default auth
        options.AddPolicy(new BearerTokenPolicy(credential), System.ClientModel.Primitives.PipelinePosition.BeforeTransport);
        
        // Use dummy API key since we're using bearer token auth
        var client = new OpenAIClient(new ApiKeyCredential("placeholder"), options);
        
        // Pass deployment name - required by SDK but Azure uses URL path
        var chatClient = client.GetChatClient(deploymentName);
        
        // Use extension from Microsoft.Extensions.AI.OpenAI
        return chatClient.AsIChatClient();
    }
}

/// <summary>
/// Pipeline policy to add api-version query string for Azure OpenAI
/// </summary>
internal class AzureApiVersionPolicy : System.ClientModel.Primitives.PipelinePolicy
{
    private readonly string _apiVersion;
    
    public AzureApiVersionPolicy(string apiVersion)
    {
        _apiVersion = apiVersion;
    }
    
    public override void Process(System.ClientModel.Primitives.PipelineMessage message, IReadOnlyList<System.ClientModel.Primitives.PipelinePolicy> pipeline, int currentIndex)
    {
        AddApiVersion(message);
        ProcessNext(message, pipeline, currentIndex);
    }
    
    public override async ValueTask ProcessAsync(System.ClientModel.Primitives.PipelineMessage message, IReadOnlyList<System.ClientModel.Primitives.PipelinePolicy> pipeline, int currentIndex)
    {
        AddApiVersion(message);
        await ProcessNextAsync(message, pipeline, currentIndex);
    }
    
    private void AddApiVersion(System.ClientModel.Primitives.PipelineMessage message)
    {
        var uri = message.Request.Uri;
        if (uri is not null)
        {
            var uriBuilder = new UriBuilder(uri);
            var query = System.Web.HttpUtility.ParseQueryString(uriBuilder.Query);
            query["api-version"] = _apiVersion;
            uriBuilder.Query = query.ToString();
            message.Request.Uri = uriBuilder.Uri;
        }
    }
}

/// <summary>
/// Pipeline policy to add Azure AD bearer token to requests
/// </summary>
internal class BearerTokenPolicy : System.ClientModel.Primitives.PipelinePolicy
{
    private readonly DefaultAzureCredential _credential;
    private string _cachedToken = "";
    private DateTimeOffset _tokenExpiry = DateTimeOffset.UtcNow; // Initialize to now so first check refreshes
    
    public BearerTokenPolicy(DefaultAzureCredential credential)
    {
        _credential = credential;
    }
    
    public override void Process(System.ClientModel.Primitives.PipelineMessage message, IReadOnlyList<System.ClientModel.Primitives.PipelinePolicy> pipeline, int currentIndex)
    {
        RefreshTokenIfNeeded();
        message.Request.Headers.Set("Authorization", $"Bearer {_cachedToken}");
        ProcessNext(message, pipeline, currentIndex);
    }
    
    public override async ValueTask ProcessAsync(System.ClientModel.Primitives.PipelineMessage message, IReadOnlyList<System.ClientModel.Primitives.PipelinePolicy> pipeline, int currentIndex)
    {
        RefreshTokenIfNeeded();
        message.Request.Headers.Set("Authorization", $"Bearer {_cachedToken}");
        await ProcessNextAsync(message, pipeline, currentIndex);
    }
    
    private void RefreshTokenIfNeeded()
    {
        // Refresh if token is empty or expires within 5 minutes
        if (string.IsNullOrEmpty(_cachedToken) || DateTimeOffset.UtcNow >= _tokenExpiry.AddMinutes(-5))
        {
            var tokenRequest = new Azure.Core.TokenRequestContext(new[] { "https://cognitiveservices.azure.com/.default" });
            var token = _credential.GetToken(tokenRequest, default);
            _cachedToken = token.Token;
            _tokenExpiry = token.ExpiresOn;
        }
    }
}
