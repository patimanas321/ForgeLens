using ForgeLens.Core.Configuration;
using ForgeLens.Core.Interfaces;
using Serilog;

namespace ForgeLens.Infrastructure.Browser;

/// <summary>
/// Manages browser sessions with human-like behavior simulation.
/// </summary>
public class BrowserSessionManager : IAsyncDisposable
{
    private readonly HumanBehaviorConfiguration _behaviorConfig;
    private readonly ILogger _logger;
    private PlaywrightMcpClient? _browserClient;
    private bool _isInitialized;

    public BrowserSessionManager(HumanBehaviorConfiguration behaviorConfig, ILogger logger)
    {
        _behaviorConfig = behaviorConfig;
        _logger = logger;
    }

    /// <summary>
    /// Gets or creates a browser automation instance.
    /// </summary>
    /// <param name="headless">Whether to run in headless mode.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    public async Task<IBrowserAutomation> GetBrowserAsync(bool headless = false, CancellationToken cancellationToken = default)
    {
        if (_browserClient == null || !_isInitialized)
        {
            _browserClient = new PlaywrightMcpClient(_behaviorConfig, _logger);
            await _browserClient.InitializeAsync(headless, cancellationToken);
            _isInitialized = true;
        }

        return _browserClient;
    }

    /// <summary>
    /// Closes the current browser session and creates a new one.
    /// </summary>
    public async Task ResetSessionAsync(bool headless = false, CancellationToken cancellationToken = default)
    {
        if (_browserClient != null)
        {
            await _browserClient.DisposeAsync();
        }

        _browserClient = new PlaywrightMcpClient(_behaviorConfig, _logger);
        await _browserClient.InitializeAsync(headless, cancellationToken);
        _isInitialized = true;
    }

    public async ValueTask DisposeAsync()
    {
        if (_browserClient != null)
        {
            await _browserClient.DisposeAsync();
            _browserClient = null;
            _isInitialized = false;
        }

        GC.SuppressFinalize(this);
    }
}
