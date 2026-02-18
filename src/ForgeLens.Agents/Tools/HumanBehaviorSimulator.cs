using ForgeLens.Core.Configuration;

namespace ForgeLens.Agents.Tools;

/// <summary>
/// Simulates human-like behavior patterns for browser automation.
/// </summary>
public class HumanBehaviorSimulator
{
    private readonly HumanBehaviorConfiguration _config;
    private readonly Random _random;

    public HumanBehaviorSimulator(HumanBehaviorConfiguration config)
    {
        _config = config;
        _random = new Random();
    }

    /// <summary>
    /// Gets a random typing delay in milliseconds.
    /// </summary>
    public int GetTypingDelay()
    {
        return _random.Next(_config.MinTypingDelayMs, _config.MaxTypingDelayMs);
    }

    /// <summary>
    /// Gets a random action delay in milliseconds.
    /// </summary>
    public int GetActionDelay()
    {
        return _random.Next(_config.MinActionDelayMs, _config.MaxActionDelayMs);
    }

    /// <summary>
    /// Determines if a typo should be made based on configuration.
    /// </summary>
    public bool ShouldMakeTypo()
    {
        return _random.NextDouble() < _config.TypoChance;
    }

    /// <summary>
    /// Gets a random scroll amount with configured variation.
    /// </summary>
    public int GetScrollAmount(int baseAmount)
    {
        var variation = (int)(baseAmount * _config.ScrollVariation);
        return baseAmount + _random.Next(-variation, variation);
    }

    /// <summary>
    /// Generates Bézier curve control points for natural mouse movement.
    /// </summary>
    public List<(double X, double Y)> GenerateBezierPoints(
        (double X, double Y) start,
        (double X, double Y) end,
        int steps = 20)
    {
        if (!_config.UseBezierMouseMovement)
        {
            return [(start.X, start.Y), (end.X, end.Y)];
        }

        // Generate random control points for a cubic Bézier curve
        var cp1 = (
            X: start.X + (end.X - start.X) * _random.NextDouble() * 0.5,
            Y: start.Y + (end.Y - start.Y) * _random.NextDouble() + _random.Next(-50, 50)
        );
        var cp2 = (
            X: start.X + (end.X - start.X) * (0.5 + _random.NextDouble() * 0.5),
            Y: start.Y + (end.Y - start.Y) * _random.NextDouble() + _random.Next(-50, 50)
        );

        var points = new List<(double X, double Y)>();

        for (int i = 0; i <= steps; i++)
        {
            double t = (double)i / steps;
            double u = 1 - t;

            // Cubic Bézier formula
            double x = u * u * u * start.X +
                      3 * u * u * t * cp1.X +
                      3 * u * t * t * cp2.X +
                      t * t * t * end.X;

            double y = u * u * u * start.Y +
                      3 * u * u * t * cp1.Y +
                      3 * u * t * t * cp2.Y +
                      t * t * t * end.Y;

            points.Add((x, y));
        }

        return points;
    }

    /// <summary>
    /// Gets a natural reading speed (words per minute).
    /// </summary>
    public int GetReadingSpeed()
    {
        // Average human reading speed varies between 200-300 WPM
        return _random.Next(200, 300);
    }

    /// <summary>
    /// Calculates delay for reading a given text naturally.
    /// </summary>
    public int GetReadingDelay(string text)
    {
        var wordCount = text.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length;
        var wpm = GetReadingSpeed();
        var minutes = (double)wordCount / wpm;
        return (int)(minutes * 60 * 1000); // Convert to milliseconds
    }

    /// <summary>
    /// Gets a typo character for a given character (nearby key).
    /// </summary>
    public char GetTypoCharacter(char original)
    {
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

    /// <summary>
    /// Simulates human hesitation with variable pauses.
    /// </summary>
    public async Task SimulateHesitationAsync(CancellationToken cancellationToken = default)
    {
        // Humans often pause briefly during interactions
        if (_random.NextDouble() < 0.1) // 10% chance of longer pause
        {
            await Task.Delay(_random.Next(1000, 3000), cancellationToken);
        }
        else
        {
            await Task.Delay(_random.Next(100, 500), cancellationToken);
        }
    }

    /// <summary>
    /// Gets randomized viewport dimensions that look natural.
    /// </summary>
    public (int Width, int Height) GetNaturalViewportSize()
    {
        // Common screen sizes
        var sizes = new[]
        {
            (1920, 1080),  // Full HD
            (1366, 768),   // Common laptop
            (1536, 864),   // Common laptop
            (1440, 900),   // MacBook
            (1280, 720),   // HD
        };

        return sizes[_random.Next(sizes.Length)];
    }

    /// <summary>
    /// Gets a natural session duration in minutes.
    /// </summary>
    public int GetSessionDurationMinutes()
    {
        // Typical social media session: 5-30 minutes
        return _random.Next(5, 30);
    }
}
