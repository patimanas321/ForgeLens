# Build stage
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy solution and project files first for layer caching
COPY ForgeLens.sln ./
COPY src/ForgeLens.Core/ForgeLens.Core.csproj src/ForgeLens.Core/
COPY src/ForgeLens.Tools/ForgeLens.Tools.csproj src/ForgeLens.Tools/
COPY src/ForgeLens.Agents/ForgeLens.Agents.csproj src/ForgeLens.Agents/
COPY src/ForgeLens.Workflows/ForgeLens.Workflows.csproj src/ForgeLens.Workflows/
COPY src/ForgeLens.Api/ForgeLens.Api.csproj src/ForgeLens.Api/

# Restore dependencies
RUN dotnet restore src/ForgeLens.Api/ForgeLens.Api.csproj

# Copy all source code
COPY . .

# Build and publish
WORKDIR /src/src/ForgeLens.Api
RUN dotnet publish -c Release -o /app/publish --no-restore

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

# Install Playwright dependencies for browser automation
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy published app
COPY --from=build /app/publish .

# Create artifacts directory
RUN mkdir -p /app/artifacts/images

# Set environment variables
ENV ASPNETCORE_URLS=http://+:8080
ENV ASPNETCORE_ENVIRONMENT=Production
ENV OUTPUT_DIRECTORY=/app/artifacts/images

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

ENTRYPOINT ["dotnet", "ForgeLens.Api.dll"]
