using Serilog;

namespace ForgeLens.Agents.Executors;

/// <summary>
/// Base class for workflow executors that provides logging and progress reporting.
/// </summary>
public abstract class ExecutorBase<TInput, TOutput>
{
    public string Id { get; }
    protected readonly ILogger Logger;

    public event Action<string, string>? OnProgress;

    protected ExecutorBase(string id, ILogger logger)
    {
        Id = id;
        Logger = logger;
    }

    /// <summary>
    /// Executes the operation with the given input.
    /// </summary>
    public abstract Task<TOutput> ExecuteAsync(TInput input, CancellationToken cancellationToken = default);

    /// <summary>
    /// Reports progress to subscribers.
    /// </summary>
    protected void ReportProgress(string message)
    {
        Logger.Information("[{ExecutorId}] {Message}", Id, message);
        OnProgress?.Invoke(Id, message);
    }
}
