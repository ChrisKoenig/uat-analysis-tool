# Disable unused VS Code extensions to improve performance
# Updated for microservices project with Azure Key Vault, Storage, and Container Apps
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "VS Code Extension Cleanup" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "✓ KEEPING (Required for this project):" -ForegroundColor Green
Write-Host "  - Python & Pylance" -ForegroundColor Gray
Write-Host "  - Docker & Containers (microservices)" -ForegroundColor Gray
Write-Host "  - PowerShell" -ForegroundColor Gray
Write-Host "  - GitHub Copilot" -ForegroundColor Gray
Write-Host "  - Azure: Storage, Key Vault, Container Apps, DevOps, Resource Groups" -ForegroundColor Gray
Write-Host "  - Azure MCP Server (Key Vault integration)" -ForegroundColor Gray
Write-Host "  - YAML (Docker Compose, configs)`n" -ForegroundColor Gray

Write-Host "🗑️  DISABLING (Not needed for this project):`n" -ForegroundColor Yellow

# Databricks (not used)
Write-Host "  Databricks extensions..." -ForegroundColor Gray
code --disable-extension databricks.databricks
code --disable-extension databricks.sqltools-databricks-driver
code --disable-extension paiqo.databricks-vscode

# Azure services not used in this project
Write-Host "  Unused Azure services..." -ForegroundColor Gray
code --disable-extension ms-azuretools.vscode-azurefunctions
code --disable-extension ms-azuretools.vscode-azurelogicapps
code --disable-extension ms-azuretools.vscode-azurestaticwebapps
code --disable-extension ms-azuretools.vscode-azurevirtualmachines
code --disable-extension ms-azuretools.vscode-cosmosdb
code --disable-extension ms-azuretools.vscode-bicep
code --disable-extension ms-vscode.vscode-node-azure-pack
code --disable-extension azurite.azurite

# .NET tools (Python project only)
Write-Host "  .NET extensions..." -ForegroundColor Gray
code --disable-extension ms-dotnettools.csdevkit
code --disable-extension ms-dotnettools.csharp
code --disable-extension ms-dotnettools.vscode-dotnet-runtime

# Jupyter (no notebooks in this project)
Write-Host "  Jupyter extensions..." -ForegroundColor Gray
code --disable-extension ms-toolsai.jupyter
code --disable-extension ms-toolsai.jupyter-keymap
code --disable-extension ms-toolsai.jupyter-renderers
code --disable-extension ms-toolsai.vscode-jupyter-cell-tags
code --disable-extension ms-toolsai.vscode-jupyter-slideshow

# Remote development (not needed)
Write-Host "  Remote development..." -ForegroundColor Gray
code --disable-extension github.codespaces
code --disable-extension ms-vscode-remote.remote-containers
code --disable-extension ms-vscode-remote.remote-wsl

# Other unused
Write-Host "  Other unused extensions..." -ForegroundColor Gray
code --disable-extension ms-edgedevtools.vscode-edge-devtools
code --disable-extension ritwickdey.liveserver
code --disable-extension teamsdevapp.ms-teams-vscode-extension
code --disable-extension teamsdevapp.vscode-ai-foundry
code --disable-extension ms-windows-ai-studio.windows-ai-studio
code --disable-extension mtxr.sqltools
code --disable-extension randomfractalsinc.vscode-data-table

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "✓ Cleanup complete!" -ForegroundColor Green
Write-Host "  Disabled: ~30 unused extensions" -ForegroundColor Gray
Write-Host "  Kept: Python, Docker, Azure (Storage, Key Vault, Containers), PowerShell, Copilot" -ForegroundColor Gray
Write-Host "`n⚠️  Restart VS Code to apply changes" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan
