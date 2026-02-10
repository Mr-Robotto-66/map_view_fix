# -*- coding: utf-8 -*-
"""
StripSdeCredentials.pyt - Python Toolbox for ArcMap 10.8

Scans a folder tree for .lyr and .mxd files that contain SDE layers
with embedded credentials for a specified username, and replaces the
workspace path with a clean .sde connection file that does not store
credentials.

Python 2.7 / ArcMap 10.x compatible.
"""

import arcpy
import os
import time


class Toolbox(object):
    def __init__(self):
        self.label = "Strip SDE Credentials"
        self.alias = "stripsdecreds"
        self.tools = [StripSdeCredentials]


class StripSdeCredentials(object):
    def __init__(self):
        self.label = "Strip SDE Credentials"
        self.description = (
            "Scans a folder for .lyr and .mxd files containing SDE layers "
            "with embedded credentials for a target username, and replaces "
            "the workspace path with a clean .sde connection file that does "
            "not save credentials."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        param_root = arcpy.Parameter(
            displayName="Root Folder to Scan",
            name="root_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input",
        )

        param_username = arcpy.Parameter(
            displayName="SDE Username to Match",
            name="sde_username",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        param_username.value = "map_view_"

        param_sde_file = arcpy.Parameter(
            displayName="Replacement .sde Connection File",
            name="replacement_sde",
            datatype="DEFile",
            parameterType="Required",
            direction="Input",
        )
        param_sde_file.filter.list = ["sde"]
        param_sde_file.value = r"\\bctsdata\data\south_root\GIS_Workspace\Scripts_and_Tools\Map_view_fix\DBP06.sde"

        return [param_root, param_username, param_sde_file]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        sde_param = parameters[2]
        if sde_param.altered and sde_param.valueAsText:
            sde_path = sde_param.valueAsText
            if not sde_path.startswith("\\\\"):
                sde_param.setWarningMessage(
                    "The replacement .sde file is not on a UNC path. "
                    "Due to Esri Bug BUG-000010966, credential state "
                    "changes may not persist when using local paths. "
                    "Consider placing the .sde file on a network share."
                )
        return

    def _process_layer(self, lyr, target_username_lower, replacement_sde):
        """Check a single layer for embedded SDE credentials and replace
        the workspace path if the username matches.

        Returns True if the layer was modified, False otherwise.
        """
        layer_name = lyr.longName if lyr.supports("LONGNAME") else lyr.name

        if lyr.isGroupLayer:
            arcpy.AddMessage("    [{}] group layer - descending".format(layer_name))
            return False

        # --- Identify SDE layers by workspace path (.sde file) ---
        if not lyr.supports("WORKSPACEPATH"):
            arcpy.AddMessage(
                "    [{}] no WORKSPACEPATH support - skipped".format(layer_name)
            )
            return False

        old_workspace = lyr.workspacePath
        if not old_workspace.lower().endswith(".sde"):
            arcpy.AddMessage(
                "    [{}] workspace='{}' (not .sde) - skipped".format(
                    layer_name, old_workspace
                )
            )
            return False

        # --- It's an SDE layer. Try to get username via multiple methods ---
        layer_user = ""

        # Method 1: serviceProperties
        svc_props = {}
        if lyr.supports("SERVICEPROPERTIES"):
            try:
                svc_props = lyr.serviceProperties
                layer_user = svc_props.get("UserName", "")
            except Exception as exc:
                arcpy.AddWarning(
                    "    [{}] error reading serviceProperties: {}".format(
                        layer_name, exc
                    )
                )

        # Dump all serviceProperties keys for diagnostics
        if svc_props:
            sp_items = ", ".join(
                "{}='{}'".format(k, v) for k, v in sorted(svc_props.items())
            )
            arcpy.AddMessage(
                "    [{}] serviceProperties: {{{}}}".format(layer_name, sp_items)
            )
        else:
            arcpy.AddMessage(
                "    [{}] serviceProperties: empty or unavailable".format(layer_name)
            )

        # Method 2: arcpy.Describe connectionProperties (fallback)
        desc_user = ""
        if not layer_user:
            try:
                desc = arcpy.Describe(lyr)
                if hasattr(desc, "connectionProperties"):
                    cp = desc.connectionProperties
                    desc_user = getattr(cp, "user", "")
                    arcpy.AddMessage(
                        "    [{}] Describe connectionProperties: user='{}', "
                        "server='{}', database='{}', auth_mode='{}'".format(
                            layer_name,
                            desc_user,
                            getattr(cp, "server", ""),
                            getattr(cp, "database", ""),
                            getattr(cp, "authentication_mode", ""),
                        )
                    )
                    if desc_user:
                        layer_user = desc_user
                else:
                    arcpy.AddMessage(
                        "    [{}] Describe has no connectionProperties".format(
                            layer_name
                        )
                    )
            except Exception as exc:
                arcpy.AddMessage(
                    "    [{}] Describe fallback failed: {}".format(layer_name, exc)
                )

        arcpy.AddMessage(
            "    [{}] resolved username: '{}'".format(layer_name, layer_user)
        )

        # --- Match username ---
        if not layer_user:
            arcpy.AddMessage(
                "    [{}] could not determine username - skipped".format(
                    layer_name
                )
            )
            return False

        if target_username_lower not in layer_user.lower():
            arcpy.AddMessage(
                "    [{}] username '{}' does not contain '{}' - skipped".format(
                    layer_name, layer_user, target_username_lower
                )
            )
            return False

        # --- Check if already clean ---
        if os.path.normcase(old_workspace) == os.path.normcase(replacement_sde):
            arcpy.AddMessage(
                "    [{}] workspace already matches replacement - skipped".format(
                    layer_name
                )
            )
            return False

        # --- Replace workspace ---
        lyr.findAndReplaceWorkspacePath(
            old_workspace, replacement_sde, validate=False
        )
        arcpy.AddMessage(
            "    [{}] REPLACED: '{}' -> '{}'".format(
                layer_name, old_workspace, replacement_sde
            )
        )
        return True

    def execute(self, parameters, messages):
        root_folder = parameters[0].valueAsText
        target_username_lower = parameters[1].valueAsText.lower()
        replacement_sde = parameters[2].valueAsText

        # --- Phase 1: Discover files ---
        overall_start = time.time()
        arcpy.AddMessage("Discovering files...")
        lyr_files = []
        mxd_files = []
        for dirpath, _dirnames, filenames in os.walk(root_folder):
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                full_path = os.path.join(dirpath, fn)
                if ext == ".lyr":
                    lyr_files.append(full_path)
                elif ext == ".mxd":
                    mxd_files.append(full_path)

        total_files = len(lyr_files) + len(mxd_files)
        arcpy.AddMessage(
            "Found {} files to scan ({} .lyr, {} .mxd).".format(
                total_files, len(lyr_files), len(mxd_files)
            )
        )

        arcpy.AddMessage("Target username: '{}'".format(target_username_lower))
        arcpy.AddMessage("Replacement .sde: '{}'".format(replacement_sde))
        arcpy.AddMessage("-" * 50)

        if total_files == 0:
            arcpy.AddWarning(
                "No .lyr or .mxd files found under '{}'.".format(root_folder)
            )
            return

        files_modified = 0
        layers_updated = 0
        files_with_errors = 0

        # --- Phase 2: Process .lyr files ---
        if lyr_files:
            arcpy.AddMessage(
                "========== Phase 2: Processing {} .lyr files ==========".format(
                    len(lyr_files)
                )
            )
        for i, lyr_path in enumerate(lyr_files, 1):
            file_start = time.time()
            arcpy.AddMessage("[{}/{}] Scanning: {}".format(i, len(lyr_files), lyr_path))
            try:
                lyr_file_obj = arcpy.mapping.Layer(lyr_path)
                all_layers = arcpy.mapping.ListLayers(lyr_file_obj)
                arcpy.AddMessage("  Contains {} layer(s)".format(len(all_layers)))
                modified_in_file = 0
                for lyr in all_layers:
                    if self._process_layer(
                        lyr, target_username_lower, replacement_sde
                    ):
                        modified_in_file += 1
                if modified_in_file > 0:
                    arcpy.AddMessage(
                        "  Saving changes ({} layers updated)...".format(modified_in_file)
                    )
                    lyr_file_obj.save()
                    files_modified += 1
                    layers_updated += modified_in_file
                del lyr_file_obj
            except Exception as exc:
                arcpy.AddWarning(
                    "  Error processing '{}': {}".format(lyr_path, exc)
                )
                files_with_errors += 1
            arcpy.AddMessage("  Done ({:.1f}s)".format(time.time() - file_start))

        # --- Phase 3: Process .mxd files ---
        if mxd_files:
            arcpy.AddMessage(
                "========== Phase 3: Processing {} .mxd files ==========".format(
                    len(mxd_files)
                )
            )
        for i, mxd_path in enumerate(mxd_files, 1):
            file_start = time.time()
            arcpy.AddMessage("[{}/{}] Scanning: {}".format(i, len(mxd_files), mxd_path))
            try:
                mxd = arcpy.mapping.MapDocument(mxd_path)
                all_layers = arcpy.mapping.ListLayers(mxd)
                arcpy.AddMessage("  Contains {} layer(s)".format(len(all_layers)))
                modified_in_file = 0
                for lyr in all_layers:
                    if self._process_layer(
                        lyr, target_username_lower, replacement_sde
                    ):
                        modified_in_file += 1
                if modified_in_file > 0:
                    folder, basename = os.path.split(mxd_path)
                    save_path = os.path.join(folder, "fixed_" + basename)
                    arcpy.AddMessage(
                        "  Saving changes ({} layers updated) -> {}".format(
                            modified_in_file, save_path
                        )
                    )
                    mxd.saveACopy(save_path)
                    files_modified += 1
                    layers_updated += modified_in_file
                del mxd
            except Exception as exc:
                arcpy.AddWarning(
                    "  Error processing '{}': {}".format(mxd_path, exc)
                )
                files_with_errors += 1
            arcpy.AddMessage("  Done ({:.1f}s)".format(time.time() - file_start))

        # --- Phase 4: Summary ---
        arcpy.AddMessage("=" * 50)
        arcpy.AddMessage("Summary:")
        arcpy.AddMessage("  Files scanned:      {}".format(total_files))
        arcpy.AddMessage("  Files modified:      {}".format(files_modified))
        arcpy.AddMessage("  Layers updated:      {}".format(layers_updated))
        if files_with_errors > 0:
            arcpy.AddWarning(
                "  Files with errors:   {}".format(files_with_errors)
            )
        else:
            arcpy.AddMessage("  Files with errors:   0")
        elapsed = time.time() - overall_start
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        if minutes > 0:
            arcpy.AddMessage("  Elapsed time:        {}m {:02d}s".format(minutes, seconds))
        else:
            arcpy.AddMessage("  Elapsed time:        {:.1f}s".format(elapsed))
        arcpy.AddMessage("=" * 50)
