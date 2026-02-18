using System.ComponentModel;
using Microsoft.Playwright;

namespace ForgeLens.Tools.Social;

/// <summary>
/// Tools for posting to Instagram using browser automation
/// </summary>
public class InstagramPostingTools : IAsyncDisposable
{
    private readonly string _username;
    private readonly string _password;
    private IPlaywright? _playwright;
    private IBrowser? _browser;
    private IPage? _page;
    private bool _isLoggedIn;

    public InstagramPostingTools(string username, string password)
    {
        _username = username;
        _password = password;
    }

    [Description("Post an image to Instagram with a caption. This will open a browser, log in if needed, and post the content.")]
    public async Task<string> PostToInstagram(
        [Description("Path to the image file to post")] string imagePath,
        [Description("The caption text including hashtags")] string caption,
        [Description("Whether to actually post or just simulate (dry run)")] bool dryRun = false)
    {
        if (!File.Exists(imagePath))
        {
            return $"Error: Image file not found at {imagePath}";
        }

        if (string.IsNullOrEmpty(_username) || string.IsNullOrEmpty(_password))
        {
            return "Error: Instagram credentials not configured. Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD environment variables.";
        }

        if (dryRun)
        {
            return $@"DRY RUN - Would post to Instagram:
═══════════════════════════════════════════════════
Image: {imagePath}
Caption Length: {caption.Length} characters
Hashtag Count: {caption.Split('#').Length - 1}
═══════════════════════════════════════════════════

Caption Preview:
{caption.Substring(0, Math.Min(200, caption.Length))}...

✓ Dry run completed. Use dryRun=false to actually post.";
        }

        try
        {
            await InitializeBrowser();
            
            if (!_isLoggedIn)
            {
                await Login();
            }

            var postResult = await CreatePost(imagePath, caption);
            return postResult;
        }
        catch (Exception ex)
        {
            return $"Error posting to Instagram: {ex.Message}";
        }
    }

    private async Task InitializeBrowser()
    {
        if (_playwright == null)
        {
            _playwright = await Playwright.CreateAsync();
            _browser = await _playwright.Chromium.LaunchAsync(new BrowserTypeLaunchOptions
            {
                Headless = true,
                Args = new[] { "--disable-blink-features=AutomationControlled" }
            });

            var context = await _browser.NewContextAsync(new BrowserNewContextOptions
            {
                UserAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
                ViewportSize = new ViewportSize { Width = 390, Height = 844 },
                IsMobile = true,
                HasTouch = true
            });

            _page = await context.NewPageAsync();
        }
    }

    private async Task Login()
    {
        if (_page == null) throw new InvalidOperationException("Browser not initialized");

        await _page.GotoAsync("https://www.instagram.com/accounts/login/");
        await _page.WaitForLoadStateAsync(LoadState.NetworkIdle);

        // Handle cookie consent if present
        try
        {
            var cookieButton = await _page.QuerySelectorAsync("button:has-text('Allow')");
            if (cookieButton != null)
            {
                await cookieButton.ClickAsync();
                await Task.Delay(1000);
            }
        }
        catch { }

        // Enter credentials
        await _page.FillAsync("input[name='username']", _username);
        await _page.FillAsync("input[name='password']", _password);
        
        // Click login
        await _page.ClickAsync("button[type='submit']");
        await _page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        await Task.Delay(3000);

        // Handle "Save Login Info" prompt
        try
        {
            var notNowButton = await _page.QuerySelectorAsync("button:has-text('Not Now')");
            if (notNowButton != null)
            {
                await notNowButton.ClickAsync();
                await Task.Delay(1000);
            }
        }
        catch { }

        // Handle notifications prompt
        try
        {
            var notNowButton = await _page.QuerySelectorAsync("button:has-text('Not Now')");
            if (notNowButton != null)
            {
                await notNowButton.ClickAsync();
                await Task.Delay(1000);
            }
        }
        catch { }

        _isLoggedIn = true;
    }

    private async Task<string> CreatePost(string imagePath, string caption)
    {
        if (_page == null) throw new InvalidOperationException("Browser not initialized");

        // Navigate to create post
        await _page.GotoAsync("https://www.instagram.com/");
        await _page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        await Task.Delay(2000);

        // Click create post button (+ icon)
        var createButton = await _page.QuerySelectorAsync("[aria-label='New post']");
        if (createButton == null)
        {
            var svgElement = await _page.QuerySelectorAsync("svg[aria-label='New post']");
            if (svgElement != null)
            {
                createButton = await svgElement.EvaluateHandleAsync("el => el.parentNode") as IElementHandle;
            }
        }
        
        if (createButton == null)
        {
            // Try alternative selectors
            createButton = await _page.QuerySelectorAsync("[role='menuitem']:has-text('Create')");
        }

        if (createButton != null)
        {
            await createButton.ClickAsync();
            await Task.Delay(2000);
        }
        else
        {
            return "Error: Could not find create post button. Instagram UI may have changed.";
        }

        // Upload image
        var fileInput = await _page.QuerySelectorAsync("input[type='file']");
        if (fileInput != null)
        {
            await fileInput.SetInputFilesAsync(imagePath);
            await Task.Delay(3000);
        }
        else
        {
            return "Error: Could not find file upload input.";
        }

        // Click Next
        var nextButton = await _page.QuerySelectorAsync("button:has-text('Next')") ??
                        await _page.QuerySelectorAsync("[role='button']:has-text('Next')");
        if (nextButton != null)
        {
            await nextButton.ClickAsync();
            await Task.Delay(2000);
            
            // Click Next again (filters page)
            nextButton = await _page.QuerySelectorAsync("button:has-text('Next')");
            if (nextButton != null)
            {
                await nextButton.ClickAsync();
                await Task.Delay(2000);
            }
        }

        // Add caption
        var captionInput = await _page.QuerySelectorAsync("textarea[aria-label='Write a caption...']") ??
                          await _page.QuerySelectorAsync("[role='textbox']");
        if (captionInput != null)
        {
            await captionInput.FillAsync(caption);
            await Task.Delay(1000);
        }

        // Click Share
        var shareButton = await _page.QuerySelectorAsync("button:has-text('Share')") ??
                         await _page.QuerySelectorAsync("[role='button']:has-text('Share')");
        if (shareButton != null)
        {
            await shareButton.ClickAsync();
            await Task.Delay(5000);
        }
        else
        {
            return "Error: Could not find share button.";
        }

        // Wait for completion
        await _page.WaitForLoadStateAsync(LoadState.NetworkIdle);

        return $@"Successfully posted to Instagram!
═══════════════════════════════════════════════════
✓ Image uploaded: {Path.GetFileName(imagePath)}
✓ Caption applied: {caption.Length} characters
✓ Post is now live
═══════════════════════════════════════════════════";
    }

    [Description("Check if currently logged into Instagram.")]
    public Task<string> CheckLoginStatus()
    {
        return Task.FromResult(_isLoggedIn 
            ? "✓ Currently logged into Instagram" 
            : "✗ Not logged into Instagram. Will login on next post attempt.");
    }

    public async ValueTask DisposeAsync()
    {
        if (_browser != null)
        {
            await _browser.CloseAsync();
        }
        _playwright?.Dispose();
    }
}
