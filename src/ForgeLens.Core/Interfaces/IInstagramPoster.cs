using ForgeLens.Core.Models;

namespace ForgeLens.Core.Interfaces;

/// <summary>
/// Interface for Instagram posting operations.
/// </summary>
public interface IInstagramPoster
{
    /// <summary>
    /// Posts an image to Instagram with human-like behavior.
    /// </summary>
    /// <param name="image">The image to post.</param>
    /// <param name="caption">Caption for the post.</param>
    /// <param name="hashtags">Hashtags to include.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Posting result.</returns>
    Task<PostingResult> PostImageAsync(
        GeneratedImage image,
        string caption,
        List<string> hashtags,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Performs engagement actions to appear more human.
    /// </summary>
    /// <param name="actionCount">Number of actions to perform.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>List of performed actions.</returns>
    Task<List<EngagementAction>> PerformEngagementActionsAsync(
        int actionCount = 3,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Logs into Instagram.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>True if login successful.</returns>
    Task<bool> LoginAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Checks if currently logged in.
    /// </summary>
    /// <returns>True if logged in.</returns>
    Task<bool> IsLoggedInAsync();
}
