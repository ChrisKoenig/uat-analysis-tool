# Pre-prod environment — loads all variables from preprod.json via shared loader
# Dot-source this file at the top of any script that needs env-specific values:
#
#   . $PSScriptRoot\..\config\environments\preprod.ps1
#
# Or from the repo root:
#   . .\config\environments\preprod.ps1
#
# Single source of truth: config/environments/preprod.json

$_configJsonPath = Join-Path $PSScriptRoot "preprod.json"
. (Join-Path $PSScriptRoot "_load-config.ps1")

