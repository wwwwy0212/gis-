from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PYT = ROOT / "面重叠处理工具.pyt"


def read_toolbox():
    return PYT.read_text(encoding="utf-8")


class OverlapToolboxStaticTest(unittest.TestCase):
    def test_toolbox_exposes_input_output_and_optional_priority_field_parameters(self):
        text = read_toolbox()
        self.assertIn('name="in_layer"', text)
        self.assertIn('name="out_layer"', text)
        self.assertIn('name="priority_field"', text)
        self.assertIn("return [p0, p1, p2]", text)
        self.assertIn("GPFeatureLayer", text)
        self.assertIn("DEFeatureClass", text)

    def test_overlap_keep_side_logic_uses_compare_priority_or_default_oid(self):
        text = read_toolbox()
        self.assertIn("_compare_priority", text)
        self.assertIn("_build_priority_lookup", text)
        # Default path when no priority field is set
        self.assertIn("keep_a = ao <= bo", text)
        # Still keeps OID tracking
        self.assertIn("KEEP_OID", text)
        self.assertIn("Sort_management", text)
        self.assertIn('DeleteIdentical_management(overlap_sorted, ["Shape"])', text)

    def test_geometry_check_and_temp_cleanup_are_present(self):
        text = read_toolbox()
        self.assertIn("CheckGeometry_management", text)
        self.assertIn(r"\u51e0\u4f55\u7834\u635f", text)
        self.assertIn("finally:", text)
        self.assertIn("Delete_management(gdb_path)", text)

    def test_toolbox_source_is_ascii_only_for_arcgis_10_loader(self):
        PYT.read_bytes().decode("ascii")

    def test_toolbox_uses_message_helpers_for_arcgis_10_messages_object(self):
        text = read_toolbox()
        self.assertIn("def _msg(", text)
        self.assertIn("def _warn(", text)
        self.assertIn("def _err(", text)
        self.assertNotIn("messages.AddMessage", text)
        self.assertNotIn("messages.AddWarning", text)
        self.assertNotIn("messages.AddError", text)

    def test_output_uses_dissolve_to_group_fragments_by_original_feature(self):
        text = read_toolbox()
        self.assertIn("_write_final_output(", text)
        self.assertIn("_write_final_output(dissolved_fc, out_layer, uid, messages)", text)
        self.assertIn("Dissolve_management", text)
        self.assertIn('"MERGE_KEY"', text)
        self.assertIn('"MULTI_PART"', text)
        self.assertNotIn("Merge_management", text)
        self.assertNotIn("Append_management(overlap_fc, final_output,", text)

    def test_output_write_has_000210_fallback(self):
        text = read_toolbox()
        self.assertIn("def _write_final_output(", text)
        self.assertIn("OverlapResult_", text)
        self.assertIn("SetParameterAsText(1, final_output)", text)
        self.assertIn(r"\u65e0\u6cd5\u521b\u5efa\u6307\u5b9a\u8f93\u51fa", text)

    def test_priority_field_parameter_is_optional_field_datatype(self):
        text = read_toolbox()
        self.assertIn('parameterType="Optional"', text)

    def test_priority_lookup_handles_null_and_incomparable_types(self):
        text = read_toolbox()
        self.assertIn("val_a is None and val_b is None", text)
        self.assertIn("val_a <= val_b", text)
        self.assertIn("except TypeError", text)

    def test_execute_reads_priority_field_from_parameters(self):
        text = read_toolbox()
        self.assertIn("parameters[2].value", text)
        self.assertIn("priority_field = parameters[2].valueAsText", text)


if __name__ == "__main__":
    unittest.main()
