namespace ForgeLens.Core.Interfaces;

/// <summary>
/// Interface for browser automation operations.
/// </summary>
public interface IBrowserAutomation
{
    /// <summary>
    /// Navigates to a URL with human-like behavior.
    /// </summary>
    /// <param name="url">The URL to navigate to.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task NavigateAsync(string url, CancellationToken cancellationToken = default);

    /// <summary>
    /// Clicks an element with human-like mouse movement.
    /// </summary>
    /// <param name="selector">CSS selector for the element.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task ClickAsync(string selector, CancellationToken cancellationToken = default);

    /// <summary>
    /// Types text with human-like speed and occasional typos.
    /// </summary>
    /// <param name="selector">CSS selector for the input element.</param>
    /// <param name="text">Text to type.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task TypeAsync(string selector, string text, CancellationToken cancellationToken = default);

    /// <summary>
    /// Scrolls the page with human-like behavior.
    /// </summary>
    /// <param name="direction">Scroll direction (up/down).</param>
    /// <param name="amount">Approximate scroll amount.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task ScrollAsync(string direction, int amount, CancellationToken cancellationToken = default);

    /// <summary>
    /// Waits for an element to be visible.
    /// </summary>
    /// <param name="selector">CSS selector for the element.</param>
    /// <param name="timeoutMs">Timeout in milliseconds.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task WaitForElementAsync(string selector, int timeoutMs = 30000, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets text content from an element.
    /// </summary>
    /// <param name="selector">CSS selector for the element.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Text content.</returns>
    Task<string> GetTextAsync(string selector, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets all text content from multiple elements.
    /// </summary>
    /// <param name="selector">CSS selector for the elements.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>List of text content.</returns>
    Task<List<string>> GetAllTextAsync(string selector, CancellationToken cancellationToken = default);

    /// <summary>
    /// Takes a screenshot.
    /// </summary>
    /// <param name="filePath">Path to save the screenshot.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task TakeScreenshotAsync(string filePath, CancellationToken cancellationToken = default);

    /// <summary>
    /// Takes a screenshot and returns it as base64 string.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Base64 encoded screenshot image.</returns>
    Task<string?> TakeScreenshotAsBase64Async(CancellationToken cancellationToken = default);

    /// <summary>
    /// Uploads a file to an input element.
    /// </summary>
    /// <param name="selector">CSS selector for the file input.</param>
    /// <param name="filePath">Path to the file to upload.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task UploadFileAsync(string selector, string filePath, CancellationToken cancellationToken = default);

    /// <summary>
    /// Adds a random delay to simulate human thinking time.
    /// </summary>
    /// <param name="minMs">Minimum delay in milliseconds.</param>
    /// <param name="maxMs">Maximum delay in milliseconds.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task RandomDelayAsync(int minMs = 1000, int maxMs = 3000, CancellationToken cancellationToken = default);

    /// <summary>
    /// Initializes the browser session.
    /// </summary>
    /// <param name="headless">Whether to run in headless mode.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task InitializeAsync(bool headless = false, CancellationToken cancellationToken = default);

    /// <summary>
    /// Closes the browser session.
    /// </summary>
    Task CloseAsync();
}
