# StripSdeCredentials

An ArcGIS Python Toolbox that strips embedded SDE database credentials from `.lyr` and `.mxd` files.

When ArcMap users connect to an SDE geodatabase with saved credentials, those credentials can become embedded inside layer files and map documents. This tool scans a folder tree, identifies layers that store a specific username, and replaces the workspace path with a clean `.sde` connection file that does not save credentials.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage Guide](#usage-guide)
  - [Parameters](#parameters)
  - [Running the Tool](#running-the-tool)
- [Examples](#examples)
  - [Example 1: GUI Walkthrough](#example-1-gui-walkthrough)
  - [Example 2: Python Console](#example-2-python-console)
- [How It Works](#how-it-works)
  - [Phase 1: Discovery](#phase-1-discovery)
  - [Phase 2: Process .lyr Files](#phase-2-process-lyr-files)
  - [Phase 3: Process .mxd Files](#phase-3-process-mxd-files)
  - [Phase 4: Summary](#phase-4-summary)
  - [Username Detection](#username-detection)
  - [Layer Filtering](#layer-filtering)
- [Output and Logging](#output-and-logging)
- [Known Issues](#known-issues)
- [Project Structure](#project-structure)
- [License](#license)

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

## Usage Guide

### Parameters

| Parameter | Name | Type | Description |
|-----------|------|------|-------------|
| **Root Folder to Scan** | `root_folder` | Folder (Required) | Top-level directory to scan. The tool walks all subdirectories recursively looking for `.lyr` and `.mxd` files. |
| **SDE Username to Match** | `sde_username` | String (Required) | The database username whose embedded credentials should be stripped. Matching is case-insensitive. |
| **Replacement .sde Connection File** | `replacement_sde` | File `.sde` (Required) | A clean `.sde` connection file that does not store credentials. This replaces the existing workspace path on every matched layer. |
| **Message Level** | `message_level` | String (Required) | Controls output verbosity. **Minimal** (default): compact progress counters. **Verbose**: full per-layer diagnostic output. **Unhinged**: minimal output plus escalating milestone commentary every 50 layers. |

### Running the Tool

1. In the ArcToolbox window, expand **Strip SDE Credentials**.
2. Double-click the **Strip SDE Credentials** tool to open the dialog.
3. Fill in the three required parameters:
   - Browse to the root folder you want to scan.
   - Enter the SDE username (e.g., `sde_admin`).
   - Browse to your replacement `.sde` file.
4. Click **OK** to run the tool.
5. Monitor progress in the **Results** window (Geoprocessing > Results).

---

## Examples

### Example 1: GUI Walkthrough

Open the tool dialog and enter:

| Parameter | Value |
|-----------|-------|
| Root Folder to Scan | `\\server\gis\projects\water_main` |
| SDE Username to Match | `sde_editor` |
| Replacement .sde Connection File | `\\server\gis\connections\PRODUCTION.sde` |

Click **OK**. The tool will:
1. Recursively scan `\\server\gis\projects\water_main` for `.lyr` and `.mxd` files.
2. Open each file, inspect every layer for SDE connections owned by `sde_editor`.
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
    r"\\server\gis\projects\water_main",   # root_folder
    "sde_editor",                           # sde_username
    r"\\server\gis\connections\PRODUCTION.sde"  # replacement_sde
)
```

Expected output:

```
Found 12 files to scan (5 .lyr, 7 .mxd).
Target username: 'sde_editor'
Replacement .sde: '\\server\gis\connections\PRODUCTION.sde'
--------------------------------------------------
Scanning: \\server\gis\projects\water_main\Parcels.lyr
  Contains 1 layer(s)
    [Parcels] REPLACED: 'C:\Users\sde_editor\AppData\...\connection.sde' -> '\\server\gis\connections\PRODUCTION.sde'
...
==================================================
Summary:
  Files scanned:      12
  Files modified:      4
  Layers updated:      7
  Files with errors:   0
==================================================
```

---

## How It Works

The tool processes files in four sequential phases.

### Phase 1: Discovery

Walks the root folder tree using `os.walk` and collects all `.lyr` and `.mxd` file paths. Reports the total count before processing begins.

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
4. If any layers were modified, saves the map document with `mxd.save()`.

### Phase 4: Summary

Prints a summary report with counts of files scanned, files modified, layers updated, and files with errors.

### Username Detection

The tool uses two methods to determine the SDE username for each layer:

1. **`serviceProperties` (primary):** Reads the `UserName` key from the layer's `serviceProperties` dictionary. This is the most reliable method when available.
2. **`arcpy.Describe` connectionProperties (fallback):** If `serviceProperties` does not return a username, the tool falls back to `arcpy.Describe(lyr).connectionProperties.user`.

Both methods are logged to the output for diagnostic purposes.

### Layer Filtering

A layer is **skipped** if any of the following are true:

- It is a **group layer** (`lyr.isGroupLayer` is `True`) - the tool descends into the group's children instead.
- It does not support **`WORKSPACEPATH`** (e.g., basemap layers, raster layers without SDE backing).
- Its workspace path does **not** end in `.sde` (i.e., it is not an SDE layer).
- The tool **could not determine** the layer's username from either detection method.
- The layer's username does **not match** the target username (case-insensitive comparison).
- The layer's workspace path **already matches** the replacement `.sde` file (normalized comparison via `os.path.normcase`).

If a layer passes all filters, the tool calls `lyr.findAndReplaceWorkspacePath()` to swap in the clean connection file.

---

## Output and Logging

The tool writes messages to the ArcMap Results window using two message types:

| Type | Function | Usage |
|------|----------|-------|
| Info | `arcpy.AddMessage()` | Progress updates, layer inspection results, replacement confirmations, summary statistics |
| Warning | `arcpy.AddWarning()` | Errors processing individual files, no files found in the root folder |

Example console output for a single `.lyr` file:

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

The final summary block uses `=` separators:

```
==================================================
Summary:
  Files scanned:      15
  Files modified:      3
  Layers updated:      5
  Files with errors:   0
==================================================
```

---

## Known Issues

### Esri Bug BUG-000010966 (UNC Path Requirement)

The replacement `.sde` file should be located on a **UNC network path** (e.g., `\\server\share\connection.sde`). Due to [Esri Bug BUG-000010966](https://support.esri.com/en/bugs/nimbus/QlVHLTAwMDAxMDk2Ng==), credential state changes may not persist when using local file paths. The tool displays a warning in the parameter validation dialog if a non-UNC path is provided.

### ArcMap 10.x Only

This tool uses `arcpy.mapping`, which is specific to ArcGIS Desktop (ArcMap). It is **not compatible with ArcGIS Pro**, which uses `arcpy.mp` and a different project file format (`.aprx` instead of `.mxd`).

### Python 2.7

The tool targets Python 2.7, which ships with ArcGIS Desktop. It does not use Python 3 syntax.

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
