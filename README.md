# StripSdeCredentials

An ArcGIS Python Toolbox that strips embedded SDE database credentials from `.lyr` and `.mxd` files.

When ArcMap users connect to an SDE geodatabase with saved credentials, those credentials can become embedded inside layer files and map documents. This tool scans a folder tree, identifies layers that store a specific username, and replaces the workspace path with a clean `.sde` connection file that does not save credentials.

---

## Table of Contents

- [Compatibility](#compatibility)
- [Usage Guide](#usage-guide)
  - [Parameters](#parameters)
  - [Running the Tool](#running-the-tool)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Examples](#examples)
  - [Example 1: GUI Walkthrough](#example-1-gui-walkthrough)
  - [Example 2: Python Console](#example-2-python-console)
- [How It Works](#how-it-works)
  - [Phase 1: Discovery](#phase-1-discovery)
  - [Phase 2: Process .lyr Files](#phase-2-process-lyr-files)
  - [Phase 3: Process .mxd Files](#phase-3-process-mxd-files)
  - [Phase 4: Deferred Cleanup](#phase-4-deferred-cleanup)
  - [Phase 5: Summary](#phase-5-summary)
  - [Username Detection](#username-detection)
  - [Layer Filtering](#layer-filtering)
- [Output and Logging](#output-and-logging)
- [Known Issues](#known-issues)
- [Project Structure](#project-structure)
- [License](#license)

---

## Compatibility

> **ArcMap only** — this tool is not compatible with ArcGIS Pro.

- Must be run on the **Farm** or **Kamloops Desktop 10.6**.
- Uses `arcpy.mapping`, which is specific to ArcGIS Desktop (ArcMap 10.x).
- Requires **Python 2.7** (bundled with ArcGIS Desktop).

---

## Usage Guide

### Parameters

| Parameter | Name | Type | Description |
|-----------|------|------|-------------|
| **Root Folder to Scan** | `root_folder` | Folder (Required) | Top-level directory to scan. The tool walks all subdirectories recursively looking for `.lyr` and `.mxd` files. |
| **SDE Username to Match** | `sde_username` | String (Required) | The database username whose embedded credentials should be stripped. Matching is case-insensitive and uses a **contains** check (e.g., `sde_editor` matches a layer owned by `DOMAIN\sde_editor`). |
| **Replacement .sde Connection File** | `replacement_sde` | File `.sde` (Required) | A clean `.sde` connection file that does not store credentials. This replaces the existing workspace path on every matched layer. |
| **Process .lyr Files** | `process_lyr` | Boolean (Required) | Whether to scan and process `.lyr` files. Default: `True`. |
| **Process .mxd Files** | `process_mxd` | Boolean (Required) | Whether to scan and process `.mxd` files. Default: `True`. |
| **Message Level** | `message_level` | String (Required) | Controls output verbosity. **Minimal** (default): compact progress counters and summary. **Verbose**: full per-layer diagnostic output. |

### Running the Tool

> **Before you start:** Open a BCGW database connection in ArcCatalog so that your session is already authenticated. When the tool opens `.mxd` files that contain BCGW layers, ArcMap will try to connect to the database. If you are not already logged in, a credential prompt will appear in the background and you will not be able to interact with it while the tool is running, causing it to hang.

1. In the ArcToolbox window, expand **Strip SDE Credentials**.
2. Double-click the **Strip SDE Credentials** tool to open the dialog.
3. Fill in the parameters:
   - Browse to the root folder you want to scan.
   - Enter the SDE username (e.g., `sde_admin`).
   - Browse to your replacement `.sde` file.
   - Check or uncheck the `.lyr` and `.mxd` processing checkboxes (both enabled by default).
   - Choose a message level (Minimal is the default).
4. Click **OK** to run the tool.
5. Monitor progress in the **Results** window (Geoprocessing > Results).

---

## Prerequisites

- **ArcGIS Desktop 10.8** (or compatible 10.x release)
- **Python 2.7** (bundled with ArcGIS Desktop)
- **Windows OS**
- A **clean `.sde` connection file** that does not store credentials (created via ArcCatalog with the "Do not save credentials" option)

---

## Installation

1. Open **ArcMap**.
2. Open the **ArcToolbox** window (Geoprocessing > ArcToolbox, or click the toolbox icon).
3. Right-click inside the ArcToolbox window and select **Add Toolbox...**
4. Navigate to the folder containing `StripSdeCredentials.pyt` and select it.
5. Click **Open**. The "Strip SDE Credentials" toolbox now appears in ArcToolbox.

To make the toolbox available in every session, right-click ArcToolbox > **Save Settings** > **To Default**.

---

## Examples

### Example 1: GUI Walkthrough

Open the tool dialog and enter:

| Parameter | Value |
|-----------|-------|
| Root Folder to Scan | `\\server\gis\projects\water_main` |
| SDE Username to Match | `sde_editor` |
| Replacement .sde Connection File | `\\server\gis\connections\PRODUCTION.sde` |
| Process .lyr Files | `True` |
| Process .mxd Files | `True` |
| Message Level | `Minimal` |

Click **OK**. The tool will:
1. Recursively scan `\\server\gis\projects\water_main` for `.lyr` and `.mxd` files.
2. Open each file, inspect every layer for SDE connections whose username contains `sde_editor`.
3. Replace matching workspace paths with `\\server\gis\connections\PRODUCTION.sde`.
4. Save modified files and print a summary.

### Example 2: Python Console

Run the tool from the ArcMap Python console window:

```python
import arcpy

# Import the toolbox
arcpy.ImportToolbox(r"\\server\gis\tools\StripSdeCredentials.pyt", "stripsdecreds")

# Execute the tool
arcpy.StripSdeCredentials_stripsdecreds(
    r"\\server\gis\projects\water_main",       # root_folder
    "sde_editor",                               # sde_username
    r"\\server\gis\connections\PRODUCTION.sde", # replacement_sde
    True,                                       # process_lyr
    True,                                       # process_mxd
    "Minimal"                                   # message_level
)
```

Expected output (Minimal mode):

```
Found 12 files to scan (5 .lyr, 7 .mxd).
[1/12] 1 fixed 0 already good
[2/12] 1 fixed 1 already good
[3/12] 2 fixed 1 already good
...
[12/12] 4 fixed 7 already good 1 errors
==================================================
Summary:
  Files scanned:      12
  Files modified:      4
  Layers updated:      7
  Files with errors:   1
  Elapsed time:        12.3s
==================================================
```

---

## How It Works

The tool processes files in five sequential phases.

### Phase 1: Discovery

Walks the root folder tree using `os.walk` and collects `.lyr` and/or `.mxd` file paths (depending on which checkboxes are enabled). Reports the total count before processing begins.

### Phase 2: Process .lyr Files

For each `.lyr` file:
1. Opens the file with `arcpy.mapping.Layer()`.
2. Lists all layers (including nested group layers) with `arcpy.mapping.ListLayers()`.
3. Runs each layer through the `_process_layer` method (see [Username Detection](#username-detection) and [Layer Filtering](#layer-filtering) below).
4. If any layers were modified, saves the file with `lyr_file_obj.save()`.

### Phase 3: Process .mxd Files

For each `.mxd` file:
1. Opens the file with `arcpy.mapping.MapDocument()`.
2. Lists all layers with `arcpy.mapping.ListLayers()`.
3. Runs each layer through `_process_layer`.
4. If any layers were modified, attempts to save in-place with `mxd.save()`. If the in-place save fails (e.g., file lock), retries once after a 10-second delay. If the retry also fails, saves a temporary copy with the `fixed_` prefix using `mxd.saveACopy()` and defers cleanup to Phase 4.

### Phase 4: Deferred Cleanup

Handles MXDs that could not be saved in-place during Phase 3. For each deferred file, the tool:
1. Deletes the original `.mxd`.
2. Renames the `fixed_` copy to the original filename.

If the rename fails (e.g., the original is still locked), the `fixed_` copy is left in place and reported in the summary.

### Phase 5: Summary

Prints a summary report with counts of files scanned, files modified, layers updated, files with errors, and elapsed time. If any `fixed_` copies could not be renamed, they are listed as warnings.

### Username Detection

The tool uses two methods to determine the SDE username for each layer:

1. **`serviceProperties` (primary):** Reads the `UserName` key from the layer's `serviceProperties` dictionary. This is the most reliable method when available.
2. **`arcpy.Describe` connectionProperties (fallback):** If `serviceProperties` does not return a username, the tool falls back to `arcpy.Describe(lyr).connectionProperties.user`.

Both methods are logged to the output (in Verbose mode) for diagnostic purposes.

### Layer Filtering

A layer is **skipped** if any of the following are true:

- It is a **group layer** (`lyr.isGroupLayer` is `True`) - the tool descends into the group's children instead.
- It does not support **`WORKSPACEPATH`** (e.g., basemap layers, raster layers without SDE backing).
- Its workspace path does **not** end in `.sde` (i.e., it is not an SDE layer).
- The tool **could not determine** the layer's username from either detection method.
- The layer's username does **not contain** the target username (case-insensitive substring check).
- The layer's workspace path **already matches** the replacement `.sde` file (normalized comparison via `os.path.normcase`).

If a layer passes all filters, the tool calls `lyr.findAndReplaceWorkspacePath()` to swap in the clean connection file.

---

## Output and Logging

The tool writes messages to the ArcMap Results window using two message types:

| Type | Function | Usage |
|------|----------|-------|
| Info | `arcpy.AddMessage()` | Progress updates, layer inspection results, replacement confirmations, summary statistics |
| Warning | `arcpy.AddWarning()` | Errors processing individual files, no files found in the root folder |

The amount of detail is controlled by the **Message Level** parameter.

### Minimal mode (default)

Prints a discovery line, one compact progress counter per file, and a summary:

```
Found 15 files to scan (8 .lyr, 7 .mxd).
[1/15] 1 fixed 0 already good
[2/15] 1 fixed 1 already good
...
[15/15] 3 fixed 11 already good 1 errors
==================================================
Summary:
  Files scanned:      15
  Files modified:      3
  Layers updated:      5
  Files with errors:   1
  Elapsed time:        18.7s
==================================================
```

### Verbose mode

Shows the full per-layer diagnostic output for every file. This is useful when troubleshooting which layers matched or were skipped:

```
Scanning: \\server\gis\projects\Parcels.lyr
  Contains 3 layer(s)
    [Parcels\Tax Parcels] serviceProperties: {Database='SDE_DB', Service='sde:oracle11g', UserName='sde_editor', Version='SDE.DEFAULT'}
    [Parcels\Tax Parcels] resolved username: 'sde_editor'
    [Parcels\Tax Parcels] REPLACED: 'C:\Users\jdoe\AppData\...\old_conn.sde' -> '\\server\gis\connections\PRODUCTION.sde'
    [Parcels\Boundaries] workspace='C:\data\boundaries.gdb' (not .sde) - skipped
    [Parcels\Labels] serviceProperties: empty or unavailable
    [Parcels\Labels] Describe has no connectionProperties
    [Parcels\Labels] resolved username: ''
    [Parcels\Labels] could not determine username - skipped
```

The summary block at the end is the same in both modes.

---

## Known Issues

### Esri Bug BUG-000010966 (UNC Path Requirement)

The replacement `.sde` file should be located on a **UNC network path** (e.g., `\\server\share\connection.sde`). Due to [Esri Bug BUG-000010966](https://support.esri.com/en/bugs/nimbus/QlVHLTAwMDAxMDk2Ng==), credential state changes may not persist when using local file paths. The tool displays a warning in the parameter validation dialog if a non-UNC path is provided.

### ArcMap and Python 2.7

See [Compatibility](#compatibility) for platform and runtime requirements.

---

## Project Structure

```
Map_view_fix/
    StripSdeCredentials.pyt                          # Python Toolbox (main tool code)
    StripSdeCredentials.pyt.xml                      # ArcGIS toolbox-level metadata
    StripSdeCredentials.StripSdeCredentials.pyt.xml  # ArcGIS tool-level metadata
    README.md                                        # This file
```

---

## License

No license is currently specified for this project.
