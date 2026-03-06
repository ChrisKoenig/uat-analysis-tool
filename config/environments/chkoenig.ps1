# chkoenig environment — loads all variables from chkoenig.json via shared loader
$_configJsonPath = Join-Path $PSScriptRoot "chkoenig.json"
. (Join-Path $PSScriptRoot "_load-config.ps1")
