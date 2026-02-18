using ForgeLens.Core.Configuration;
using ForgeLens.Core.Models;
using ForgeLens.Infrastructure.Browser;
using Serilog;
using System.Diagnostics;

namespace ForgeLens.Agents.Executors;

/// <summary>
/// Executor that posts images to Instagram with human-like behavior.
/// </summary>
public class InstagramPosterExecutor : ExecutorBase<ImageEvaluationResult, PostingResult>
{
    private readonly BrowserSessionManager _browserManager;
    private readonly InstagramConfiguration _instagramConfig;
    private readonly HumanBehaviorConfiguration _behaviorConfig;

    private const string InstagramBaseUrl = "https://www.instagram.com";

    public InstagramPosterExecutor(
        BrowserSessionManager browserManager,
        InstagramConfiguration instagramConfig,
        HumanBehaviorConfiguration behaviorConfig,
        ILogger logger)
        : base("InstagramPoster", logger)
    {
        _browserManager = browserManager;
        _instagramConfig = instagramConfig;
        _behaviorConfig = behaviorConfig;
    }

    public override async Task<PostingResult> ExecuteAsync(
        ImageEvaluationResult input,
        CancellationToken cancellationToken = default)
    {
        var stopwatch = Stopwatch.StartNew();
        Logger.Information("Starting Instagram posting process");
        ReportProgress("Starting Instagram posting...");

        var engagementActions = new List<EngagementAction>();

        try
        {
            var browser = await _browserManager.GetBrowserAsync(headless: false, cancellationToken);

            // Navigate to Instagram
            ReportProgress("Navigating to Instagram...");
            await browser.NavigateAsync(InstagramBaseUrl, cancellationToken);
            await browser.RandomDelayAsync(2000, 4000, cancellationToken);

            // Check if login is needed
            var needsLogin = await CheckIfLoginRequiredAsync(browser, cancellationToken);

            if (needsLogin)
            {
                ReportProgress("Logging into Instagram...");
                await LoginToInstagramAsync(browser, cancellationToken);
            }

            // Perform some natural engagement actions before posting
            ReportProgress("Performing natural engagement actions...");
            engagementActions.AddRange(await PerformPrePostEngagementAsync(browser, cancellationToken));

            // Create the post
            ReportProgress("Creating new post...");
            await CreatePostAsync(browser, input, cancellationToken);

            // Take a screenshot after posting
            var screenshotPath = Path.Combine(
                Path.GetDirectoryName(input.SelectedImage.FilePath) ?? ".",
                $"post_confirmation_{DateTime.UtcNow:yyyyMMdd_HHmmss}.png"
            );
            await browser.TakeScreenshotAsync(screenshotPath, cancellationToken);

            // Perform post-posting engagement
            engagementActions.AddRange(await PerformPostEngagementAsync(browser, cancellationToken));

            stopwatch.Stop();

            Logger.Information("Successfully posted to Instagram");
            ReportProgress("Post published successfully!");

            return new PostingResult
            {
                Status = PostingStatus.Success,
                PostedImage = input.SelectedImage,
                Caption = input.SuggestedCaption,
                Hashtags = input.SuggestedHashtags,
                PostingTime = stopwatch.Elapsed,
                PostedAt = DateTime.UtcNow,
                ScreenshotPath = screenshotPath,
                EngagementActions = engagementActions
            };
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            Logger.Error(ex, "Failed to post to Instagram");
            ReportProgress($"Failed: {ex.Message}");

            return new PostingResult
            {
                Status = PostingStatus.Failed,
                PostedImage = input.SelectedImage,
                Caption = input.SuggestedCaption,
                Hashtags = input.SuggestedHashtags,
                PostingTime = stopwatch.Elapsed,
                ErrorMessage = ex.Message,
                EngagementActions = engagementActions
            };
        }
    }

    private async Task<bool> CheckIfLoginRequiredAsync(
        Core.Interfaces.IBrowserAutomation browser,
        CancellationToken cancellationToken)
    {
        try
        {
            // Look for login form elements
            var texts = await browser.GetAllTextAsync("input[name='username'], a[href='/accounts/login/']", cancellationToken);
            return texts.Any();
        }
        catch
        {
            // If we can't determine, assume logged in
            return false;
        }
    }

    private async Task LoginToInstagramAsync(
        Core.Interfaces.IBrowserAutomation browser,
        CancellationToken cancellationToken)
    {
        Logger.Information("Performing Instagram login");

        // Navigate to login page
        await browser.NavigateAsync($"{InstagramBaseUrl}/accounts/login/", cancellationToken);
        await browser.RandomDelayAsync(2000, 4000, cancellationToken);

        // Wait for login form
        await browser.WaitForElementAsync("input[name='username']", 10000, cancellationToken);

        // Type username with human-like speed
        await browser.TypeAsync("input[name='username']", _instagramConfig.Username, cancellationToken);
        await browser.RandomDelayAsync(500, 1500, cancellationToken);

        // Type password with human-like speed
        await browser.TypeAsync("input[name='password']", _instagramConfig.Password, cancellationToken);
        await browser.RandomDelayAsync(500, 1500, cancellationToken);

        // Click login button
        await browser.ClickAsync("button[type='submit']", cancellationToken);

        // Wait for navigation
        await browser.RandomDelayAsync(3000, 5000, cancellationToken);

        // Handle "Save Login Info" dialog if present
        try
        {
            await browser.ClickAsync("button:has-text('Not Now')", cancellationToken);
        }
        catch { /* Dialog may not appear */ }

        // Handle notifications dialog if present
        try
        {
            await browser.RandomDelayAsync(1000, 2000, cancellationToken);
            await browser.ClickAsync("button:has-text('Not Now')", cancellationToken);
        }
        catch { /* Dialog may not appear */ }

        Logger.Information("Login completed");
    }

    private async Task CreatePostAsync(
        Core.Interfaces.IBrowserAutomation browser,
        ImageEvaluationResult input,
        CancellationToken cancellationToken)
    {
        Logger.Information("Creating Instagram post");

        // Click create post button (+ icon in navigation)
        await browser.RandomDelayAsync(1000, 2000, cancellationToken);

        // Try different selectors for the create button (Instagram UI changes frequently)
        var createSelectors = new[]
        {
            "svg[aria-label='New post']",
            "[aria-label='New post']",
            "a[href='/create/style/']",
            "[data-testid='new-post-button']"
        };

        foreach (var selector in createSelectors)
        {
            try
            {
                await browser.ClickAsync(selector, cancellationToken);
                break;
            }
            catch
            {
                continue;
            }
        }

        await browser.RandomDelayAsync(1500, 3000, cancellationToken);

        // Upload the image
        Logger.Information("Uploading image: {ImagePath}", input.SelectedImage.FilePath);

        // Click "Select from computer" or find file input
        try
        {
            await browser.ClickAsync("button:has-text('Select from computer')", cancellationToken);
        }
        catch { /* Button may already be clicked */ }

        // Upload file
        await browser.UploadFileAsync("input[type='file']", input.SelectedImage.FilePath, cancellationToken);
        await browser.RandomDelayAsync(2000, 4000, cancellationToken);

        // Skip crop/filters - click Next
        try
        {
            await browser.ClickAsync("button:has-text('Next')", cancellationToken);
            await browser.RandomDelayAsync(1000, 2000, cancellationToken);
            await browser.ClickAsync("button:has-text('Next')", cancellationToken);
            await browser.RandomDelayAsync(1000, 2000, cancellationToken);
        }
        catch
        {
            Logger.Warning("Could not find Next button");
        }

        // Enter caption
        var fullCaption = BuildFullCaption(input.SuggestedCaption, input.SuggestedHashtags);
        await browser.TypeAsync("textarea[aria-label='Write a caption...']", fullCaption, cancellationToken);
        await browser.RandomDelayAsync(1000, 2000, cancellationToken);

        // Click Share
        await browser.ClickAsync("button:has-text('Share')", cancellationToken);
        await browser.RandomDelayAsync(3000, 5000, cancellationToken);

        Logger.Information("Post shared successfully");
    }

    private string BuildFullCaption(string caption, List<string> hashtags)
    {
        var limitedHashtags = hashtags
            .Take(_instagramConfig.MaxHashtags)
            .ToList();

        // Ensure default hashtags are included
        foreach (var defaultTag in _instagramConfig.DefaultHashtags)
        {
            if (limitedHashtags.Count < _instagramConfig.MaxHashtags &&
                !limitedHashtags.Contains(defaultTag, StringComparer.OrdinalIgnoreCase))
            {
                limitedHashtags.Add(defaultTag);
            }
        }

        return $"{caption}\n\n{string.Join(" ", limitedHashtags)}";
    }

    private async Task<List<EngagementAction>> PerformPrePostEngagementAsync(
        Core.Interfaces.IBrowserAutomation browser,
        CancellationToken cancellationToken)
    {
        var actions = new List<EngagementAction>();

        try
        {
            // Scroll through feed briefly
            for (int i = 0; i < 2; i++)
            {
                await browser.ScrollAsync("down", 400, cancellationToken);
                await browser.RandomDelayAsync(1500, 3000, cancellationToken);
            }

            actions.Add(new EngagementAction
            {
                ActionType = "feed_scroll",
                Success = true
            });

            // Like a random post (maybe)
            if (Random.Shared.NextDouble() < 0.3)
            {
                try
                {
                    await browser.ClickAsync("svg[aria-label='Like']", cancellationToken);
                    actions.Add(new EngagementAction
                    {
                        ActionType = "like_post",
                        Success = true
                    });
                }
                catch { /* Post may not be likeable */ }
            }
        }
        catch (Exception ex)
        {
            Logger.Warning(ex, "Pre-post engagement failed");
        }

        return actions;
    }

    private async Task<List<EngagementAction>> PerformPostEngagementAsync(
        Core.Interfaces.IBrowserAutomation browser,
        CancellationToken cancellationToken)
    {
        var actions = new List<EngagementAction>();

        try
        {
            await browser.RandomDelayAsync(2000, 4000, cancellationToken);

            // Check notifications
            try
            {
                await browser.ClickAsync("a[href='/direct/inbox/']", cancellationToken);
                await browser.RandomDelayAsync(1000, 2000, cancellationToken);

                actions.Add(new EngagementAction
                {
                    ActionType = "check_messages",
                    Success = true
                });
            }
            catch { /* May not be available */ }

            // Navigate home
            await browser.NavigateAsync(InstagramBaseUrl, cancellationToken);
            await browser.RandomDelayAsync(1000, 2000, cancellationToken);

            actions.Add(new EngagementAction
            {
                ActionType = "return_home",
                Success = true
            });
        }
        catch (Exception ex)
        {
            Logger.Warning(ex, "Post engagement failed");
        }

        return actions;
    }
}
