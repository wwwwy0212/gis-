# -*- coding: utf-8 -*-
# ArcGIS Desktop 10.6 / Python 2.7 Python Toolbox
# Source is ASCII-only on purpose. ArcGIS 10.x can mark UTF-8 .pyt files
# with Chinese text as broken on some Windows code pages.

import arcpy
import os
import shutil
import tempfile
import uuid


class Toolbox(object):
    def __init__(self):
        self.label = u"\u9762\u91cd\u53e0\u5904\u7406\u5de5\u5177\u7bb1"
        self.alias = "OverlapTools"
        self.tools = [OverlapRemoveOne]


class OverlapRemoveOne(object):
    def __init__(self):
        self.label = u"\u9762\u91cd\u53e0\u5904\u7406\u5de5\u5177"
        self.description = (
            u"\u5355\u56fe\u5c42\u4e00\u952e\u53bb\u91cd\u53e0\uff1a"
            u"1 \u81ea\u76f8\u4ea4\u63d0\u53d6\u5c40\u90e8\u91cd\u53e0\u9762\uff1b"
            u"2 \u5220\u9664\u76f8\u540c\u9879\u5e76\u4fdd\u7559 OBJECTID/FID "
            u"\u8f83\u5c0f\u56fe\u6591\u5c5e\u6027\uff1b"
            u"3 \u64e6\u9664\u5e76\u5408\u5e76\u8f93\u51fa\u3002")
        self.canRunInBackground = True

    def getParameterInfo(self):
        p0 = arcpy.Parameter(
            displayName=u"\u8f93\u5165\u9762\u56fe\u5c42\uff08\u5355\u56fe\u5c42\u5185\u90e8\u53bb\u91cd\u53e0\uff09",
            name="in_layer",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        p0.filter.list = ["Polygon"]

        p1 = arcpy.Parameter(
            displayName=u"\u8f93\u51fa\u6210\u679c\u56fe\u5c42\uff08\u65e0\u7a7a\u95f4\u91cd\u53e0\uff09",
            name="out_layer",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output")

        return [p0, p1]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        if parameters[0].altered and parameters[0].value:
            try:
                desc = arcpy.Describe(parameters[0].value)
                if desc.shapeType.lower() != "polygon":
                    parameters[0].setErrorMessage(
                        u"\u8f93\u5165\u6570\u636e\u5fc5\u987b\u662f\u9762\u56fe\u5c42\uff08Polygon\uff09\u3002")
            except Exception:
                pass
        return

    def execute(self, parameters, messages):
        in_layer = parameters[0].valueAsText
        out_layer = parameters[1].valueAsText

        uid = uuid.uuid4().hex[:8]
        tmp_dir = _make_temp_dir(out_layer, uid)
        gdb_path = os.path.join(tmp_dir, "scratch.gdb")

        try:
            arcpy.env.overwriteOutput = True
            _msg(messages, u"========== \u9762\u91cd\u53e0\u5904\u7406\u5f00\u59cb ==========")
            _msg(messages,
                u"\u6d41\u7a0b\uff1a\u81ea\u76f8\u4ea4\u63d0\u53d6 -> "
                u"\u5220\u9664\u76f8\u540c\u9879\u4fdd\u7559\u8f83\u5c0f OBJECTID \u5c5e\u6027 -> "
                u"\u64e6\u9664\u91cd\u53e0\u533a -> "
                u"\u6309\u539f\u59cb\u56fe\u6591\u5408\u5e76\u788e\u7247\u8f93\u51fa")

            if not arcpy.Exists(in_layer):
                _raise_tool_error(messages, u"\u8f93\u5165\u56fe\u5c42\u4e0d\u5b58\u5728\u6216\u4e0d\u53ef\u8bbf\u95ee\u3002")

            desc = arcpy.Describe(in_layer)
            if desc.shapeType.lower() != "polygon":
                _raise_tool_error(
                    messages,
                    u"\u8f93\u5165\u56fe\u5c42\u5fc5\u987b\u662f\u9762\u8981\u7d20\uff0c\u5f53\u524d\u7c7b\u578b\uff1a%s"
                    % desc.shapeType)

            input_count = _get_count(in_layer)
            _msg(messages, u"\u8f93\u5165\u56fe\u6591\u6570\u91cf\uff1a%d" % input_count)
            if input_count == 0:
                _raise_tool_error(messages, u"\u8f93\u5165\u56fe\u5c42\u4e3a\u7a7a\uff0c\u672a\u751f\u6210\u6210\u679c\u3002")

            if arcpy.Exists(gdb_path):
                arcpy.Delete_management(gdb_path)
            arcpy.CreateFileGDB_management(tmp_dir, "scratch.gdb")

            _msg(messages, u"[0] \u521b\u5efa\u4e34\u65f6\u6570\u636e\u5e76\u68c0\u67e5\u51e0\u4f55...")
            src_a = os.path.join(gdb_path, "src_a")
            src_b = os.path.join(gdb_path, "src_b")
            arcpy.CopyFeatures_management(in_layer, src_a)
            arcpy.CopyFeatures_management(in_layer, src_b)

            _capture_original_order(src_a, "A_ORIGOID")
            _capture_original_order(src_b, "B_ORIGOID")
            _check_geometry_or_raise(src_a, gdb_path, messages)

            original_fields = _field_names_to_keep(src_a)

            _msg(messages, u"[1/3] \u81ea\u76f8\u4ea4\u63d0\u53d6\u5168\u90e8\u5c40\u90e8\u91cd\u53e0\u9762...")
            raw_fc = os.path.join(gdb_path, "raw_intersect")
            arcpy.Intersect_analysis([src_a, src_b], raw_fc, "ALL", "", "INPUT")
            raw_count = _get_count(raw_fc)
            _msg(messages, u"  Intersect \u4ea7\u7269\u6570\u91cf\uff1a%d" % raw_count)

            if raw_count == 0:
                _msg(messages, u"\u672a\u53d1\u73b0\u5c40\u90e8\u91cd\u53e0\uff0c\u76f4\u63a5\u590d\u5236\u8f93\u5165\u4e3a\u8f93\u51fa\u6210\u679c\u3002")
                arcpy.CopyFeatures_management(in_layer, out_layer)
                return

            fid_a = _find_required_field(raw_fc, "FID_src_a")
            fid_b = _find_required_field(raw_fc, "FID_src_b")
            a_oid = _find_required_field(raw_fc, "A_ORIGOID")
            b_oid = _find_required_field(raw_fc, "B_ORIGOID")

            arcpy.AddField_management(raw_fc, "IS_OVLP", "SHORT")
            arcpy.AddField_management(raw_fc, "KEEP_OID", "LONG")
            arcpy.AddField_management(raw_fc, "KEEP_SIDE", "TEXT", "", "", 1)

            field_list = "%s;%s;%s;%s;IS_OVLP;KEEP_OID;KEEP_SIDE" % (fid_a, fid_b, a_oid, b_oid)
            rows = arcpy.UpdateCursor(raw_fc, "", "", field_list)
            row = rows.next()
            while row:
                fa = row.getValue(fid_a)
                fb = row.getValue(fid_b)
                ao = row.getValue(a_oid)
                bo = row.getValue(b_oid)
                is_overlap = 1 if fa != fb else 0
                row.setValue("IS_OVLP", is_overlap)
                if is_overlap:
                    row.setValue("KEEP_OID", min(ao, bo))
                    row.setValue("KEEP_SIDE", "A" if ao <= bo else "B")
                rows.updateRow(row)
                row = rows.next()
            del row
            del rows

            overlap_temp = os.path.join(gdb_path, "overlap_candidates")
            arcpy.Select_analysis(raw_fc, overlap_temp, "IS_OVLP = 1 AND KEEP_SIDE = 'A'")
            overlap_count = _get_count(overlap_temp)
            _msg(messages, u"  \u8de8\u56fe\u6591\u5c40\u90e8\u91cd\u53e0\u5019\u9009\u6570\u91cf\uff1a%d" % overlap_count)

            if overlap_count == 0:
                _msg(messages, u"\u672a\u53d1\u73b0\u8de8\u56fe\u6591\u5c40\u90e8\u91cd\u53e0\uff0c\u76f4\u63a5\u590d\u5236\u8f93\u5165\u4e3a\u8f93\u51fa\u6210\u679c\u3002")
                arcpy.CopyFeatures_management(in_layer, out_layer)
                return

            _msg(messages, u"[2/3] \u5220\u9664\u76f8\u540c\u9879\uff0c\u4fdd\u7559 OBJECTID/FID \u8f83\u5c0f\u56fe\u6591\u5c5e\u6027...")
            overlap_sorted = os.path.join(gdb_path, "overlap_sorted")
            arcpy.Sort_management(overlap_temp, overlap_sorted, [["KEEP_OID", "ASCENDING"]])
            arcpy.DeleteIdentical_management(overlap_sorted, ["Shape"])
            _msg(messages, u"  \u5220\u9664\u76f8\u540c\u9879\u540e\u91cd\u53e0\u9762\u6570\u91cf\uff1a%d" %
                 _get_count(overlap_sorted))

            overlap_fc = overlap_sorted

            _msg(messages, u"[3/3] \u64e6\u9664\u91cd\u53e0\u533a\u5e76\u5408\u5e76\u6700\u7ec8\u6210\u679c...")
            erased_fc = os.path.join(gdb_path, "erased")
            arcpy.Erase_analysis(src_a, overlap_fc, erased_fc)
            _msg(messages, u"  \u64e6\u9664\u540e\u975e\u91cd\u53e0\u788e\u7247\u6570\u91cf\uff1a%d" %
                 _get_count(erased_fc))

            _msg(messages, u"  \u6309\u539f\u59cb\u56fe\u6591\u5408\u5e76\u788e\u7247...")
            arcpy.AddField_management(erased_fc, "MERGE_KEY", "LONG")
            arcpy.CalculateField_management(erased_fc, "MERGE_KEY", "!A_ORIGOID!", "PYTHON_9.3")
            arcpy.AddField_management(overlap_fc, "MERGE_KEY", "LONG")
            arcpy.CalculateField_management(overlap_fc, "MERGE_KEY", "!KEEP_OID!", "PYTHON_9.3")

            merge_fc = os.path.join(gdb_path, "fragments_merge")
            arcpy.CopyFeatures_management(erased_fc, merge_fc)
            arcpy.Append_management(overlap_fc, merge_fc, "NO_TEST")

            dissolved_fc = os.path.join(gdb_path, "dissolved")
            arcpy.Dissolve_management(merge_fc, dissolved_fc, "MERGE_KEY", "", "MULTI_PART")
            _msg(messages, u"  \u878d\u89e3\u540e\u56fe\u6591\u6570\u91cf\uff1a%d" %
                 _get_count(dissolved_fc))

            # Dissolve drops user attributes; join them back from the original table
            join_table = os.path.join(gdb_path, "src_attr")
            arcpy.CopyFeatures_management(src_a, join_table)
            arcpy.AddField_management(join_table, "MERGE_KEY", "LONG")
            arcpy.CalculateField_management(join_table, "MERGE_KEY", "!A_ORIGOID!", "PYTHON_9.3")
            arcpy.JoinField_management(dissolved_fc, "MERGE_KEY", join_table, "MERGE_KEY", original_fields)

            _drop_non_output_fields(dissolved_fc, original_fields)

            final_output = _write_final_output(dissolved_fc, out_layer, uid, messages)

            _msg(messages, u"\u8f93\u51fa\u6210\u679c\u6570\u91cf\uff1a%d" % _get_count(final_output))
            _msg(messages, u"\u8f93\u51fa\u8def\u5f84\uff1a%s" % final_output)
            _msg(messages, u"\u5904\u7406\u5b8c\u6210\uff1a\u6210\u679c\u5168\u56fe\u4e0d\u518d\u91cd\u590d\u6838\u7b97\u5c40\u90e8\u91cd\u53e0\u9762\u79ef\u3002")

        except arcpy.ExecuteError:
            arcpy_msg = arcpy.GetMessages(2)
            if arcpy_msg:
                _err(messages, arcpy_msg)
            raise
        except Exception as e:
            _err(messages, u"\u5de5\u5177\u8fd0\u884c\u5f02\u5e38\uff1a%s" % _to_unicode(e))
            raise arcpy.ExecuteError
        finally:
            _msg(messages, u"--- \u6e05\u7406\u4e34\u65f6\u6570\u636e ---")
            try:
                if arcpy.Exists(gdb_path):
                    arcpy.Delete_management(gdb_path)
            except Exception as cleanup_error:
                _warn(messages, u"\u4e34\u65f6 GDB \u6e05\u7406\u5931\u8d25\uff0c\u4e0d\u5f71\u54cd\u6210\u679c\uff1a%s" %
                      _to_unicode(cleanup_error))
            try:
                if os.path.isdir(tmp_dir):
                    shutil.rmtree(tmp_dir)
            except Exception as cleanup_error:
                _warn(messages, u"\u4e34\u65f6\u76ee\u5f55\u6e05\u7406\u5931\u8d25\uff0c\u4e0d\u5f71\u54cd\u6210\u679c\uff1a%s" %
                      _to_unicode(cleanup_error))
            _msg(messages, u"========== \u9762\u91cd\u53e0\u5904\u7406\u7ed3\u675f ==========")


def _make_temp_dir(out_layer, uid):
    base_dir = os.path.dirname(out_layer)
    if base_dir and base_dir.lower().endswith(".gdb"):
        base_dir = os.path.dirname(base_dir)
    if not base_dir or not os.path.isdir(base_dir):
        base_dir = tempfile.gettempdir()
    tmp_dir = os.path.join(base_dir, "overlap_tmp_" + uid)
    if not os.path.isdir(tmp_dir):
        os.makedirs(tmp_dir)
    return tmp_dir


def _get_count(feature_class):
    return int(arcpy.GetCount_management(feature_class).getOutput(0))


def _raise_tool_error(messages, text):
    _err(messages, text)
    raise arcpy.ExecuteError


def _capture_original_order(feature_class, field_name):
    desc = arcpy.Describe(feature_class)
    oid_field = desc.OIDFieldName
    arcpy.AddField_management(feature_class, field_name, "LONG")
    rows = arcpy.UpdateCursor(feature_class, "", "", oid_field + ";" + field_name)
    row = rows.next()
    while row:
        row.setValue(field_name, row.getValue(oid_field))
        rows.updateRow(row)
        row = rows.next()
    del row
    del rows


def _check_geometry_or_raise(feature_class, gdb_path, messages):
    check_table = os.path.join(gdb_path, "geometry_check")
    arcpy.CheckGeometry_management(feature_class, check_table)
    issue_count = _get_count(check_table)
    if issue_count > 0:
        _err(messages,
            u"\u68c0\u6d4b\u5230\u51e0\u4f55\u7834\u635f\u8bb0\u5f55\uff1a%d "
            u"\u6761\u3002\u8bf7\u5148\u8fd0\u884c\u201c\u4fee\u590d\u51e0\u4f55\u201d\u540e\u518d\u5904\u7406\u3002"
            % issue_count)
        raise arcpy.ExecuteError
    _msg(messages, u"  \u51e0\u4f55\u68c0\u67e5\u901a\u8fc7\uff0c\u672a\u53d1\u73b0\u51e0\u4f55\u7834\u635f\u3002")


def _field_names_to_keep(feature_class):
    keep = []
    helper_fields = ["A_ORIGOID", "B_ORIGOID", "IS_OVLP", "KEEP_OID", "KEEP_SIDE", "MERGE_KEY"]
    for field in arcpy.ListFields(feature_class):
        if field.type in ("OID", "Geometry"):
            continue
        if field.name in helper_fields:
            continue
        keep.append(field.name.upper())
    return keep


def _find_required_field(feature_class, expected_name):
    for field in arcpy.ListFields(feature_class):
        if field.name.upper() == expected_name.upper():
            return field.name
    raise arcpy.ExecuteError


def _drop_non_output_fields(feature_class, original_fields):
    protected = ["OBJECTID", "FID", "OID", "SHAPE", "SHAPE_LENGTH", "SHAPE_AREA"]
    delete_fields = []
    for field in arcpy.ListFields(feature_class):
        name_upper = field.name.upper()
        if field.required:
            continue
        if field.type in ("OID", "Geometry"):
            continue
        if name_upper in protected:
            continue
        if name_upper not in original_fields:
            delete_fields.append(field.name)
    if delete_fields:
        arcpy.DeleteField_management(feature_class, delete_fields)


def _write_final_output(result_fc, out_layer, uid, messages):
    final_output = out_layer
    try:
        if arcpy.Exists(final_output):
            arcpy.Delete_management(final_output)
        arcpy.CopyFeatures_management(result_fc, final_output)
        arcpy.SetParameterAsText(1, final_output)
        return final_output
    except arcpy.ExecuteError:
        arcpy_msg = arcpy.GetMessages(2)
        if arcpy_msg:
            _warn(messages, arcpy_msg)
        fallback = _fallback_output_path(out_layer, uid)
        _warn(
            messages,
            u"\u65e0\u6cd5\u521b\u5efa\u6307\u5b9a\u8f93\u51fa\uff0c\u53ef\u80fd\u662f\u540c\u540d\u6b8b\u7559\u3001"
            u"\u56fe\u5c42\u9501\u5b9a\u3001Default.gdb \u5143\u6570\u636e\u9501\u6216\u540d\u79f0\u8fc7\u957f\u3002"
            u"\u5c06\u81ea\u52a8\u6539\u7528\u5b89\u5168\u8f93\u51fa\uff1a%s" % fallback)
        if arcpy.Exists(fallback):
            arcpy.Delete_management(fallback)
        arcpy.CopyFeatures_management(result_fc, fallback)
        final_output = fallback
        arcpy.SetParameterAsText(1, final_output)
        return final_output


def _fallback_output_path(out_layer, uid):
    workspace = os.path.dirname(out_layer)
    if not workspace:
        workspace = arcpy.env.scratchGDB
    safe_name = "OverlapResult_" + uid
    return os.path.join(workspace, safe_name)


def _msg(messages, text):
    _send_gp_message(messages, text, "message")


def _warn(messages, text):
    _send_gp_message(messages, text, "warning")


def _err(messages, text):
    _send_gp_message(messages, text, "error")


def _send_gp_message(messages, text, level):
    method_names = {
        "message": ["addMessage", "AddMessage"],
        "warning": ["addWarningMessage", "addWarning", "AddWarning"],
        "error": ["addErrorMessage", "addError", "AddError"]
    }[level]
    for method_name in method_names:
        method = getattr(messages, method_name, None)
        if method:
            try:
                method(text)
                return
            except Exception:
                pass
    if level == "warning":
        arcpy.AddWarning(text)
    elif level == "error":
        arcpy.AddError(text)
    else:
        arcpy.AddMessage(text)


def _to_unicode(value):
    try:
        return unicode(value)
    except NameError:
        return str(value)
