# Dev environment — loads all variables from dev.json via shared loader
# Dot-source this file at the top of any script that needs env-specific values:
#
#   . $PSScriptRoot\..\config\environments\dev.ps1
#
# Or from the repo root:
#   . .\config\environments\dev.ps1
#
# Single source of truth: config/environments/dev.json

$_configJsonPath = Join-Path $PSScriptRoot "dev.json"
. (Join-Path $PSScriptRoot "_load-config.ps1")

