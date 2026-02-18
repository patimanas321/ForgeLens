using ForgeLens.Core.Models;

namespace ForgeLens.Core.Interfaces;

/// <summary>
/// Interface for trend analysis operations.
/// </summary>
public interface ITrendAnalyzer
{
    /// <summary>
    /// Analyzes current trends across configured sources.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Analysis result with selected topic.</returns>
    Task<TrendAnalysisResult> AnalyzeTrendsAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets trends from a specific source.
    /// </summary>
    /// <param name="sourceUrl">The URL to analyze.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>List of discovered trends.</returns>
    Task<List<TrendingTopic>> GetTrendsFromSourceAsync(string sourceUrl, CancellationToken cancellationToken = default);
}
