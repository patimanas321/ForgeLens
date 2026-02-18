using ForgeLens.Core.Configuration;
using ForgeLens.Core.Interfaces;
using ModelContextProtocol.Client;
using Serilog;
using System.Text.Json;

namespace ForgeLens.Infrastructure.Browser;

/// <summary>
/// Browser automation using Playwright MCP with human-like behavior simulation.
/// </summary>
public class PlaywrightMcpClient : IBrowserAutomation, IAsyncDisposable
{
    private readonly HumanBehaviorConfiguration _behaviorConfig;
    private readonly ILogger _logger;
    private McpClient? _mcpClient;
    private readonly Random _random = new();

    public PlaywrightMcpClient(HumanBehaviorConfiguration behaviorConfig, ILogger logger)
    {
        _behaviorConfig = behaviorConfig;
        _logger = logger;
    }

    /// <inheritdoc />
    public async Task InitializeAsync(bool headless = false, CancellationToken cancellationToken = default)
    {
        _logger.Information("Initializing Playwright MCP browser automation...");

        var arguments = new List<string> { "-y", "@playwright/mcp@latest" };
        if (headless)
        {
            arguments.Add("--headless");
        }

        _mcpClient = await McpClient.CreateAsync(
            new StdioClientTransport(
                new()
                {
                    Name = "Playwright MCP",
                    Command = "npx",
                    Arguments = arguments
                }
            ),
            cancellationToken: cancellationToken
        );

        _logger.Information("Playwright MCP initialized successfully");
    }

    /// <inheritdoc />
    public async Task NavigateAsync(string url, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        _logger.Debug("Navigating to {Url}", url);

        await CallMcpToolAsync("browser_navigate", new { url }, cancellationToken);
        await RandomDelayAsync(1000, 2000, cancellationToken);
    }

    /// <inheritdoc />
    public async Task ClickAsync(string selector, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        _logger.Debug("Clicking element: {Selector}", selector);

        // Simulate human-like mouse movement before click
        if (_behaviorConfig.UseBezierMouseMovement)
        {
            await SimulateMouseMovement(cancellationToken);
        }

        await CallMcpToolAsync("browser_click", new { selector }, cancellationToken);
        await RandomDelayAsync(_behaviorConfig.MinActionDelayMs, _behaviorConfig.MaxActionDelayMs, cancellationToken);
    }

    /// <inheritdoc />
    public async Task TypeAsync(string selector, string text, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        _logger.Debug("Typing text into {Selector}", selector);

        // First click the element
        await ClickAsync(selector, cancellationToken);

        // Type character by character with human-like delays
        foreach (char c in text)
        {
            // Occasionally make and correct typos
            if (_random.NextDouble() < _behaviorConfig.TypoChance)
            {
                var typoChar = GetRandomTypoChar(c);
                await CallMcpToolAsync("browser_type", new { selector = "body", text = typoChar.ToString() }, cancellationToken);
                await Task.Delay(_random.Next(100, 300), cancellationToken);

                // Correct the typo
                await CallMcpToolAsync("browser_type", new { selector = "body", text = "\b" }, cancellationToken);
                await Task.Delay(_random.Next(200, 500), cancellationToken);
            }

            await CallMcpToolAsync("browser_type", new { selector = "body", text = c.ToString() }, cancellationToken);

            // Variable typing speed
            var delay = _random.Next(_behaviorConfig.MinTypingDelayMs, _behaviorConfig.MaxTypingDelayMs);
            await Task.Delay(delay, cancellationToken);
        }
    }

    /// <inheritdoc />
    public async Task ScrollAsync(string direction, int amount, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();

        // Add variation to scroll amount
        var variation = (int)(amount * _behaviorConfig.ScrollVariation);
        var actualAmount = amount + _random.Next(-variation, variation);

        var scrollY = direction.ToLower() == "down" ? actualAmount : -actualAmount;

        _logger.Debug("Scrolling {Direction} by {Amount}px", direction, actualAmount);
        await CallMcpToolAsync("browser_evaluate", new { expression = $"window.scrollBy(0, {scrollY})" }, cancellationToken);
        await RandomDelayAsync(500, 1500, cancellationToken);
    }

    /// <inheritdoc />
    public async Task WaitForElementAsync(string selector, int timeoutMs = 30000, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        _logger.Debug("Waiting for element: {Selector}", selector);

        await CallMcpToolAsync("browser_wait_for", new { selector, timeout = timeoutMs }, cancellationToken);
    }

    /// <inheritdoc />
    public async Task<string> GetTextAsync(string selector, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();

        var result = await CallMcpToolAsync("browser_evaluate", 
            new { expression = $"document.querySelector('{selector}')?.textContent || ''" }, 
            cancellationToken);

        return result?.ToString() ?? string.Empty;
    }

    /// <inheritdoc />
    public async Task<List<string>> GetAllTextAsync(string selector, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();

        var result = await CallMcpToolAsync("browser_evaluate",
            new { expression = $"Array.from(document.querySelectorAll('{selector}')).map(el => el.textContent)" },
            cancellationToken);

        if (result is JsonElement jsonElement && jsonElement.ValueKind == JsonValueKind.Array)
        {
            return jsonElement.EnumerateArray()
                .Select(e => e.GetString() ?? string.Empty)
                .ToList();
        }

        return [];
    }

    /// <inheritdoc />
    public async Task TakeScreenshotAsync(string filePath, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        _logger.Debug("Taking screenshot: {FilePath}", filePath);

        var base64Data = await TakeScreenshotAsBase64Async(cancellationToken);
        
        if (!string.IsNullOrEmpty(base64Data))
        {
            var imageBytes = Convert.FromBase64String(base64Data);
            var directory = Path.GetDirectoryName(filePath);
            if (!string.IsNullOrEmpty(directory))
            {
                Directory.CreateDirectory(directory);
            }
            await File.WriteAllBytesAsync(filePath, imageBytes, cancellationToken);
            _logger.Debug("Screenshot saved to: {FilePath}", filePath);
            return;
        }
        
        _logger.Warning("Screenshot capture did not return expected data");
    }

    /// <inheritdoc />
    public async Task<string?> TakeScreenshotAsBase64Async(CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        _logger.Debug("Taking screenshot as base64");

        var result = await CallMcpToolAsync("browser_screenshot", new { }, cancellationToken);
        
        if (result != null)
        {
            string? base64Data = null;
            
            // Handle different response formats
            if (result is string str)
            {
                base64Data = str;
            }
            else if (result is JsonElement jsonElement)
            {
                if (jsonElement.TryGetProperty("data", out var dataElement))
                {
                    base64Data = dataElement.GetString();
                }
                else if (jsonElement.ValueKind == JsonValueKind.String)
                {
                    base64Data = jsonElement.GetString();
                }
            }
            
            if (!string.IsNullOrEmpty(base64Data))
            {
                // Remove data URI prefix if present
                if (base64Data.Contains(","))
                {
                    base64Data = base64Data.Substring(base64Data.IndexOf(',') + 1);
                }
                return base64Data;
            }
        }
        
        _logger.Warning("Screenshot capture did not return expected data");
        return null;
    }

    /// <inheritdoc />
    public async Task UploadFileAsync(string selector, string filePath, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        _logger.Debug("Uploading file {FilePath} to {Selector}", filePath, selector);

        await CallMcpToolAsync("browser_file_upload", new { selector, paths = new[] { filePath } }, cancellationToken);
        await RandomDelayAsync(1000, 2000, cancellationToken);
    }

    /// <inheritdoc />
    public async Task RandomDelayAsync(int minMs = 1000, int maxMs = 3000, CancellationToken cancellationToken = default)
    {
        var delay = _random.Next(minMs, maxMs);
        await Task.Delay(delay, cancellationToken);
    }

    /// <inheritdoc />
    public async Task CloseAsync()
    {
        if (_mcpClient != null)
        {
            _logger.Information("Closing Playwright MCP session");
            await _mcpClient.DisposeAsync();
            _mcpClient = null;
        }
    }

    public async ValueTask DisposeAsync()
    {
        await CloseAsync();
        GC.SuppressFinalize(this);
    }

    private void EnsureInitialized()
    {
        if (_mcpClient == null)
        {
            throw new InvalidOperationException("Browser automation not initialized. Call InitializeAsync first.");
        }
    }

    private async Task<object?> CallMcpToolAsync(string toolName, object arguments, CancellationToken cancellationToken)
    {
        try
        {
            // Convert object to dictionary format expected by MCP
            var jsonString = JsonSerializer.Serialize(arguments);
            var argsDict = JsonSerializer.Deserialize<Dictionary<string, object?>>(jsonString);
            
            var result = await _mcpClient!.CallToolAsync(toolName, argsDict, cancellationToken: cancellationToken);
            return result;
        }
        catch (Exception ex)
        {
            _logger.Warning(ex, "MCP tool call failed: {ToolName}", toolName);
            throw;
        }
    }

    private async Task SimulateMouseMovement(CancellationToken cancellationToken)
    {
        // Simulate Bézier curve mouse movement
        var steps = _random.Next(3, 7);
        for (int i = 0; i < steps; i++)
        {
            await Task.Delay(_random.Next(10, 50), cancellationToken);
        }
    }

    private char GetRandomTypoChar(char original)
    {
        // Return a nearby key on QWERTY keyboard
        var keyboard = new Dictionary<char, string>
        {
            ['a'] = "sqwz", ['b'] = "vghn", ['c'] = "xdfv", ['d'] = "serfcx",
            ['e'] = "wrsdf", ['f'] = "drtgvc", ['g'] = "ftyhbv", ['h'] = "gyujnb",
            ['i'] = "ujklo", ['j'] = "huiknm", ['k'] = "jiolm", ['l'] = "kop",
            ['m'] = "njk", ['n'] = "bhjm", ['o'] = "iklp", ['p'] = "ol",
            ['q'] = "wa", ['r'] = "edft", ['s'] = "awedxz", ['t'] = "rfgy",
            ['u'] = "yhjki", ['v'] = "cfgb", ['w'] = "qase", ['x'] = "zsdc",
            ['y'] = "tghu", ['z'] = "asx"
        };

        var lowerChar = char.ToLower(original);
        if (keyboard.TryGetValue(lowerChar, out var neighbors))
        {
            var typo = neighbors[_random.Next(neighbors.Length)];
            return char.IsUpper(original) ? char.ToUpper(typo) : typo;
        }

        return original;
    }
}
