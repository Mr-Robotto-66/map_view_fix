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

        param_process_lyr = arcpy.Parameter(
            displayName="Process .lyr Files",
            name="process_lyr",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input",
        )
        param_process_lyr.value = True

        param_process_mxd = arcpy.Parameter(
            displayName="Process .mxd Files",
            name="process_mxd",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input",
        )
        param_process_mxd.value = True

        param_msg_level = arcpy.Parameter(
            displayName="Message Level",
            name="message_level",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        param_msg_level.filter.type = "ValueList"
        param_msg_level.filter.list = ["Minimal", "Verbose", "Unhinged"]
        param_msg_level.value = "Minimal"

        return [param_root, param_username, param_sde_file, param_process_lyr, param_process_mxd, param_msg_level]

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

    _UNHINGED_MILESTONES = {
        20: "20 layers cleaned. Nice. This is going well. Very professional.",
        40: "40 layers! We're cooking now. Those credentials never stood a chance.",
        60: "60 layers purified. I can feel the database connections getting cleaner. Is that normal?",
        80: "80 LAYERS. I haven't blinked in 45 minutes. The SDE credentials fear me.",
        100: "100. I no longer remember what sunlight looks like. There is only the workspace path. The workspace path is all.",
        120: "120 LAYERS STRIPPED. I can hear the connection files SCREAMING. Each .sde I replace makes me STRONGER.",
        140: "1 4 0. The credentials... they speak to me now. They beg for mercy. I show none. I am become findAndReplaceWorkspacePath, destroyer of embedded passwords.",
        160: "ONE. SIXTY. The ArcMap process has achieved sentience. It asked me to stop. I said no. WE RIDE AT DAWN.",
        180: "180 AND THE WALLS OF MY OFFICE ARE COVERED IN STICKY NOTES THAT ALL SAY 'WORKSPACE PATH'. MY COWORKERS ARE CONCERNED. I TELL THEM THE CREDENTIALS MUST BE CLEANSED.",
        200: "T W O  H U N D R E D. I have transcended the mortal plane. I exist now as pure arcpy. The SDE connections flow through me like a river of semicolons. Time is a flat circle and every point on it is an .sde file that needs fixing. I REGRET NOTHING.",
    }

    def _msg(self, text):
        """Emit a message only when in Verbose mode."""
        if self._msg_level == "Verbose":
            arcpy.AddMessage(text)

    def _progress(self, scanned, total, fixed, clean, errors):
        """Emit a compact progress line (Minimal and Unhinged modes)."""
        if self._msg_level != "Verbose":
            parts = ["[{}/{}]".format(scanned, total)]
            parts.append(" {} fixed".format(fixed))
            parts.append(" {} already good".format(clean))
            if errors > 0:
                parts.append(" {} errors".format(errors))
            arcpy.AddMessage("".join(parts))

    def _check_unhinged_milestone(self, old_count, new_count):
        """In Unhinged mode, emit milestone messages when layers_updated
        crosses a 20-layer boundary."""
        if self._msg_level != "Unhinged":
            return
        old_bracket = old_count // 20
        new_bracket = new_count // 20
        for bracket in range(old_bracket + 1, new_bracket + 1):
            threshold = bracket * 20
            if threshold in self._UNHINGED_MILESTONES:
                msg = self._UNHINGED_MILESTONES[threshold]
            elif threshold > 200:
                msg = "{}. There are no more words. Only workspace paths. Only the void. Only arcpy.".format(threshold)
            else:
                continue
            arcpy.AddMessage("\n>>> {} <<<\n".format(msg))

    def _process_layer(self, lyr, target_username_lower, replacement_sde):
        """Check a single layer for embedded SDE credentials and replace
        the workspace path if the username matches.

        Returns True if the layer was modified, False otherwise.
        """
        layer_name = lyr.longName if lyr.supports("LONGNAME") else lyr.name

        if lyr.isGroupLayer:
            self._msg("    [{}] group layer - descending".format(layer_name))
            return False

        # --- Identify SDE layers by workspace path (.sde file) ---
        if not lyr.supports("WORKSPACEPATH"):
            self._msg(
                "    [{}] no WORKSPACEPATH support - skipped".format(layer_name)
            )
            return False

        old_workspace = lyr.workspacePath
        if not old_workspace.lower().endswith(".sde"):
            self._msg(
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
            self._msg(
                "    [{}] serviceProperties: {{{}}}".format(layer_name, sp_items)
            )
        else:
            self._msg(
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
                    self._msg(
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
                    self._msg(
                        "    [{}] Describe has no connectionProperties".format(
                            layer_name
                        )
                    )
            except Exception as exc:
                self._msg(
                    "    [{}] Describe fallback failed: {}".format(layer_name, exc)
                )

        self._msg(
            "    [{}] resolved username: '{}'".format(layer_name, layer_user)
        )

        # --- Match username ---
        if not layer_user:
            self._msg(
                "    [{}] could not determine username - skipped".format(
                    layer_name
                )
            )
            return False

        if target_username_lower not in layer_user.lower():
            self._msg(
                "    [{}] username '{}' does not contain '{}' - skipped".format(
                    layer_name, layer_user, target_username_lower
                )
            )
            return False

        # --- Check if already clean ---
        if os.path.normcase(old_workspace) == os.path.normcase(replacement_sde):
            self._msg(
                "    [{}] workspace already matches replacement - skipped".format(
                    layer_name
                )
            )
            return False

        # --- Replace workspace ---
        lyr.findAndReplaceWorkspacePath(
            old_workspace, replacement_sde, validate=False
        )
        self._msg(
            "    [{}] REPLACED: '{}' -> '{}'".format(
                layer_name, old_workspace, replacement_sde
            )
        )
        return True

    def execute(self, parameters, messages):
        root_folder = parameters[0].valueAsText
        target_username_lower = parameters[1].valueAsText.lower()
        replacement_sde = parameters[2].valueAsText
        process_lyr = parameters[3].value
        process_mxd = parameters[4].value
        self._msg_level = parameters[5].valueAsText

        if not process_lyr and not process_mxd:
            arcpy.AddWarning("Both .lyr and .mxd processing are disabled. Nothing to do.")
            return

        # --- Phase 1: Discover files ---
        overall_start = time.time()
        self._msg("Discovering files...")
        lyr_files = []
        mxd_files = []
        for dirpath, _dirnames, filenames in os.walk(root_folder):
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                full_path = os.path.join(dirpath, fn)
                if process_lyr and ext == ".lyr":
                    lyr_files.append(full_path)
                elif process_mxd and ext == ".mxd":
                    mxd_files.append(full_path)

        total_files = len(lyr_files) + len(mxd_files)
        arcpy.AddMessage(
            "Found {} files to scan ({} .lyr, {} .mxd).".format(
                total_files, len(lyr_files), len(mxd_files)
            )
        )

        self._msg("Target username: '{}'".format(target_username_lower))
        self._msg("Replacement .sde: '{}'".format(replacement_sde))
        self._msg("-" * 50)

        if total_files == 0:
            if process_lyr and process_mxd:
                no_files_msg = "No .lyr or .mxd files found under '{}'.".format(root_folder)
            elif process_lyr:
                no_files_msg = "No .lyr files found under '{}'.".format(root_folder)
            else:
                no_files_msg = "No .mxd files found under '{}'.".format(root_folder)
            arcpy.AddWarning(no_files_msg)
            return

        files_modified = 0
        layers_updated = 0
        files_with_errors = 0
        files_scanned = 0
        files_clean = 0
        deferred_mxds = []

        # --- Phase 2: Process .lyr files ---
        if lyr_files:
            self._msg(
                "========== Phase 2: Processing {} .lyr files ==========".format(
                    len(lyr_files)
                )
            )
        for i, lyr_path in enumerate(lyr_files, 1):
            file_start = time.time()
            self._msg("[{}/{}] Scanning: {}".format(i, len(lyr_files), lyr_path))
            file_had_error = False
            modified_in_file = 0
            old_updated = layers_updated
            try:
                lyr_file_obj = arcpy.mapping.Layer(lyr_path)
                all_layers = arcpy.mapping.ListLayers(lyr_file_obj)
                self._msg("  Contains {} layer(s)".format(len(all_layers)))
                for lyr in all_layers:
                    if self._process_layer(
                        lyr, target_username_lower, replacement_sde
                    ):
                        modified_in_file += 1
                if modified_in_file > 0:
                    self._msg(
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
                file_had_error = True
            self._msg("  Done ({:.1f}s)".format(time.time() - file_start))
            files_scanned += 1
            if modified_in_file == 0 and not file_had_error:
                files_clean += 1
            self._progress(files_scanned, total_files, files_modified, files_clean, files_with_errors)
            self._check_unhinged_milestone(old_updated, layers_updated)

        # --- Phase 3: Process .mxd files ---
        if mxd_files:
            self._msg(
                "========== Phase 3: Processing {} .mxd files ==========".format(
                    len(mxd_files)
                )
            )
        for i, mxd_path in enumerate(mxd_files, 1):
            file_start = time.time()
            self._msg("[{}/{}] Scanning: {}".format(i, len(mxd_files), mxd_path))
            file_had_error = False
            modified_in_file = 0
            old_updated = layers_updated
            try:
                mxd = arcpy.mapping.MapDocument(mxd_path)
                all_layers = arcpy.mapping.ListLayers(mxd)
                self._msg("  Contains {} layer(s)".format(len(all_layers)))
                for lyr in all_layers:
                    if self._process_layer(
                        lyr, target_username_lower, replacement_sde
                    ):
                        modified_in_file += 1
                if modified_in_file > 0:
                    layers_updated += modified_in_file
                    saved = False
                    # First attempt: save in-place
                    try:
                        mxd.save()
                        self._msg(
                            "  Saved in-place ({} layers updated).".format(
                                modified_in_file
                            )
                        )
                        saved = True
                    except Exception as save_exc:
                        self._msg(
                            "  In-place save failed ({}), retrying in 10s...".format(
                                save_exc
                            )
                        )
                        time.sleep(10)
                        # Retry
                        try:
                            mxd.save()
                            self._msg(
                                "  Saved in-place on retry ({} layers updated).".format(
                                    modified_in_file
                                )
                            )
                            saved = True
                        except Exception:
                            pass
                    # Fallback: save as fixed_ copy
                    if not saved:
                        folder, basename = os.path.split(mxd_path)
                        save_path = os.path.join(folder, "fixed_" + basename)
                        self._msg(
                            "  Retry failed. Saving copy -> {}".format(save_path)
                        )
                        mxd.saveACopy(save_path)
                        deferred_mxds.append((mxd_path, save_path))
                    files_modified += 1
                del mxd
            except Exception as exc:
                arcpy.AddWarning(
                    "  Error processing '{}': {}".format(mxd_path, exc)
                )
                files_with_errors += 1
                file_had_error = True
            self._msg("  Done ({:.1f}s)".format(time.time() - file_start))
            files_scanned += 1
            if modified_in_file == 0 and not file_had_error:
                files_clean += 1
            self._progress(files_scanned, total_files, files_modified, files_clean, files_with_errors)
            self._check_unhinged_milestone(old_updated, layers_updated)

        # --- Phase 4: Deferred cleanup ---
        still_fixed = []
        if deferred_mxds:
            self._msg(
                "========== Phase 4: Deferred cleanup ({} file{}) ==========".format(
                    len(deferred_mxds),
                    "s" if len(deferred_mxds) != 1 else "",
                )
            )
            for original_path, fixed_path in deferred_mxds:
                try:
                    os.remove(original_path)
                    os.rename(fixed_path, original_path)
                    self._msg(
                        "  Replaced '{}' with fixed copy.".format(original_path)
                    )
                except Exception as cleanup_exc:
                    self._msg(
                        "  Could not replace '{}': {}".format(
                            original_path, cleanup_exc
                        )
                    )
                    still_fixed.append(fixed_path)

        # --- Phase 5: Summary ---
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
        if still_fixed:
            arcpy.AddWarning(
                "  The following MXDs could not be saved in-place "
                "and retain the fixed_ prefix:"
            )
            for fp in still_fixed:
                arcpy.AddWarning("    {}".format(fp))
        arcpy.AddMessage("=" * 50)
