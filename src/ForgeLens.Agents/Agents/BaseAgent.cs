using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace ForgeLens.Agents;

/// <summary>
/// Base class for all ForgeLens AI agents
/// </summary>
public abstract class BaseAgent
{
    protected readonly IChatClient ChatClient;
    
    /// <summary>
    /// The underlying AI Agent instance
    /// </summary>
    public AIAgent Agent { get; protected set; } = null!;

    /// <summary>
    /// Agent name
    /// </summary>
    public abstract string Name { get; }

    /// <summary>
    /// Agent description
    /// </summary>
    public abstract string Description { get; }

    protected BaseAgent(IChatClient chatClient)
    {
        ChatClient = chatClient;
    }

    /// <summary>
    /// Initialize the agent - must be called after construction
    /// </summary>
    protected abstract void Initialize();

    /// <summary>
    /// Run the agent with a message
    /// </summary>
    public async Task<AgentResponse> RunAsync(string message, CancellationToken cancellationToken = default)
    {
        return await Agent.RunAsync(message);
    }

    /// <summary>
    /// Get this agent as an AIFunction for use by orchestrators
    /// </summary>
    public AIFunction AsAIFunction() => Agent.AsAIFunction();
}
