#!/usr/bin/env python
"""
IBST_Materials - Standard Build Entry Point

This script is the single entry point for the workspace workflow.

Current phase:
    Phase 1 - enforce workspace rules and standard operating flow

Planned future phases:
    Phase 2 - read CSV inputs
    Phase 3 - map CSV rows into DesignBuilder material records
    Phase 4 - generate CDT
    Phase 5 - package CDT into DDF

Standard workflow enforced by this script:
    1. Read references only from 01_designbuilder_format/
    2. Read editable user inputs only from 02_csv_input/
    3. Write generated artifacts only to 03_output/
    4. Keep automation logic only in 04_scripts/
    5. Move removed files to 99_archive/ before permanent deletion

Rule alignment:
    - Do not create arbitrary files outside approved output paths.
    - Treat CSV as editable input, not as final import artifact.
    - Treat CDT as editable intermediate/package content.
    - Treat DDF as final DesignBuilder import package.
    - Default operation is update/repair on existing workspace structure.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable
import zipfile


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    rules_config: Path
    designbuilder_format: Path
    csv_input: Path
    output: Path
    scripts: Path
    archive: Path
    reference_ddf: Path
    reference_exported_cdt: Path
    reference_final_qa_cdt: Path
    reference_final_qa_ddf: Path
    reference_final_qa_schema: Path
    generated_cdt: Path
    generated_ddf: Path
    selected_csv_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class CsvSource:
    kind: str
    path: Path
    rows: list[dict[str, str]]


@dataclass(frozen=True)
class RecordMatch:
    source_kind: str
    match_type: str
    csv_name: str
    cdt_name: str
    csv_row: dict[str, str]
    cdt_row: dict[str, str]


@dataclass(frozen=True)
class MappingMismatch:
    csv_name: str
    cdt_name: str
    expected: str
    actual: str


@dataclass(frozen=True)
class MappingResult:
    rule_name: str
    cdt_field: str
    source_scope: str
    matched_count: int
    total_count: int
    mismatches: list[MappingMismatch]


@dataclass
class SourceCoverage:
    csv_rows: int = 0
    exact_matches: int = 0
    prefix_matches: list[tuple[str, str]] = field(default_factory=list)
    unmatched_rows: list[str] = field(default_factory=list)


@dataclass
class AlignmentCoverage:
    detailed: SourceCoverage = field(default_factory=SourceCoverage)
    nomass: SourceCoverage = field(default_factory=SourceCoverage)
    unused_cdt_names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IdRuleAnalysis:
    total_count: int
    numeric_count: int
    unique_count: int
    issues: list[str]


@dataclass(frozen=True)
class GenerationSummary:
    total_records: int
    detailed_count: int
    nomass_count: int
    id_start: int
    id_end: int


def load_rules_config(root: Path) -> dict:
    config_path = root / "workspace_rules.json"
    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_workspace_paths(
    script_path: Path,
    config: dict,
    selected_csv_names: tuple[str, ...] = (),
    output_subdir: str | None = None,
) -> WorkspacePaths:
    root = script_path.resolve().parent.parent
    paths_cfg = config["paths"]
    ref_cfg = config["reference_files"]
    allowed_outputs = config["artifacts"]["allowed_output_files"]
    generated_cdt_name = next(name for name in allowed_outputs if Path(name).suffix.lower() == ".cdt")
    generated_ddf_name = next(name for name in allowed_outputs if Path(name).suffix.lower() == ".ddf")
    output_path = root / paths_cfg["output"]

    if output_subdir:
        output_subdir_path = Path(output_subdir)
        if output_subdir_path.is_absolute() or ".." in output_subdir_path.parts:
            raise ValueError("--output-subdir must stay inside 03_output.")
        output_path = output_path / output_subdir_path

    output_path.mkdir(parents=True, exist_ok=True)

    return WorkspacePaths(
        root=root,
        rules_config=root / "workspace_rules.json",
        designbuilder_format=root / paths_cfg["reference"],
        csv_input=root / paths_cfg["input"],
        output=output_path,
        scripts=root / paths_cfg["scripts"],
        archive=root / paths_cfg["archive"],
        reference_ddf=root / paths_cfg["reference"] / ref_cfg["reference_ddf"],
        reference_exported_cdt=root / paths_cfg["reference"] / ref_cfg["reference_exported_cdt"],
        reference_final_qa_cdt=root / paths_cfg["reference"] / ref_cfg["reference_final_qa_cdt"],
        reference_final_qa_ddf=root / paths_cfg["reference"] / ref_cfg["reference_final_qa_ddf"],
        reference_final_qa_schema=root / paths_cfg["reference"] / ref_cfg["reference_final_qa_schema"],
        generated_cdt=output_path / generated_cdt_name,
        generated_ddf=output_path / generated_ddf_name,
        selected_csv_names=selected_csv_names,
    )


def sanitize_output_stem(name: str) -> str:
    sanitized = "".join(character.lower() if character.isalnum() else "_" for character in name.strip())
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized.strip("_") or "run"


def derive_output_subdir_name(selected_csv_names: tuple[str, ...]) -> str:
    stems = [sanitize_output_stem(Path(name).stem) for name in selected_csv_names if name.strip()]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not stems:
        return f"run_{timestamp}"
    return f"{'_and_'.join(stems)}_{timestamp}"


def standard_workflow_text() -> str:
    return (
        "STANDARD WORKFLOW\n"
        "1. Use DesignBuilder-exported DDF/CDT files in 01_designbuilder_format as reference only.\n"
        "2. Place editable CSV inputs in 02_csv_input.\n"
        "3. Run this script from 04_scripts as the single automation entry point.\n"
        "4. Future generated CDT/DDF files must be written only to 03_output.\n"
        "5. Files removed from active workspace should go to 99_archive before deletion.\n"
        "6. No manual creation of arbitrary CDT/DDF files outside the approved workflow.\n"
    )


def _require_dict_keys(container: dict, container_name: str, keys: list[str], issues: list[str]) -> None:
    for key in keys:
        if key not in container:
            issues.append(f"Missing config key: {container_name}.{key}")


def validate_config_structure(config: dict) -> list[str]:
    issues: list[str] = []

    _require_dict_keys(
        config,
        "root",
        [
            "workspace_name",
            "scope",
            "rule_source",
            "paths",
            "path_rules",
            "reference_files",
            "input_files",
            "artifacts",
            "behavior",
            "ddf_cdt",
            "materials",
            "materials_mapping",
            "maintenance_convention",
        ],
        issues,
    )

    if "scope" in config:
        _require_dict_keys(config["scope"], "scope", ["purpose", "domain"], issues)
    if "rule_source" in config:
        _require_dict_keys(
            config["rule_source"],
            "rule_source",
            [
                "rules_md_is_human_readable_source",
                "workspace_rules_json_is_machine_readable_source",
                "rules_update_requires_json_update",
                "rule_change_incomplete_without_both_files_updated",
            ],
            issues,
        )
    if "paths" in config:
        _require_dict_keys(config["paths"], "paths", ["reference", "input", "output", "scripts", "archive"], issues)
    if "path_rules" in config:
        _require_dict_keys(
            config["path_rules"],
            "path_rules",
            [
                "reference_is_read_only_by_default",
                "input_is_for_external_data_transformation",
                "output_is_only_for_pipeline_generated_files",
                "scripts_is_only_for_workspace_automation",
                "archive_is_for_removed_files_before_permanent_deletion",
            ],
            issues,
        )
    if "reference_files" in config:
        _require_dict_keys(
            config["reference_files"],
            "reference_files",
            [
                "reference_ddf",
                "reference_exported_cdt",
                "reference_final_qa_cdt",
                "reference_final_qa_ddf",
                "reference_final_qa_schema",
            ],
            issues,
        )
    if "input_files" in config:
        _require_dict_keys(
            config["input_files"],
            "input_files",
            [
                "discovery_mode",
                "file_extension",
                "ignore_filename_prefixes",
                "sort_order",
                "allow_multiple_files_per_kind",
                "type_column",
                "detailed_type_value",
                "nomass_type_value",
                "detailed_required_columns",
                "nomass_required_columns",
            ],
            issues,
        )
    if "artifacts" in config:
        _require_dict_keys(
            config["artifacts"],
            "artifacts",
            ["final_import_artifact", "editable_intermediate_artifact", "csv_is_not_final_import_artifact", "allowed_output_files"],
            issues,
        )
    if "behavior" in config:
        _require_dict_keys(
            config["behavior"],
            "behavior",
            [
                "allow_manual_new_files",
                "new_files_require_explicit_create_instruction_or_defined_pipeline_output",
                "archive_before_delete",
                "csv_is_final_artifact",
                "ddf_is_final_artifact",
                "cdt_is_editable_intermediate",
                "default_operation_is_repair_not_create",
                "manual_creation_of_cdt_or_ddf_without_defined_generation_step",
                "move_irrelevant_files_to_archive_before_final_delete",
            ],
            issues,
        )
    if "ddf_cdt" in config:
        _require_dict_keys(
            config["ddf_cdt"],
            "ddf_cdt",
            [
                "ddf_is_designbuilder_import_export_package",
                "designbuilder_reads_ddf_directly_for_import",
                "ddf_can_be_renamed_to_zip_for_inspection",
                "ddf_is_not_directly_editable_text",
                "cdt_is_text_inside_ddf_package",
                "cdt_field_delimiter",
                "cdt_expected_sections",
                "reference_package_cdt_entry_name",
                "package_entry_name_must_match_reference_ddf",
                "edit_external_data_on_cdt_then_repackage_to_ddf",
                "package_ddf_by_zipping_required_cdt_files_then_renaming_extension",
                "designbuilder_exported_csv_cannot_be_imported_back_directly",
                "must_compare_with_designbuilder_exported_reference_before_packaging",
            ],
            issues,
        )
    if "materials" in config:
        _require_dict_keys(
            config["materials"],
            "materials",
            [
                "is_component_data",
                "can_be_referenced_by_other_components",
                "reference_must_be_designbuilder_exported_materials_ddf",
                "must_compare_against_exported_materials_ddf_or_cdt_before_generating_new_materials",
                "data_groups",
                "import_to_open_model_targets_model_components",
                "import_to_library_requires_no_open_model",
                "component_added_while_model_is_open_becomes_model_component",
                "new_materials_for_future_models_must_be_imported_to_library",
                "system_materials_editable_directly",
                "clone_system_material_before_edit",
                "prefer_user_defined_materials_for_external_generation",
            ],
            issues,
        )
    if "materials_mapping" in config:
        _require_dict_keys(
            config["materials_mapping"],
            "materials_mapping",
            [
                "name_rule",
                "roughness_rule",
                "description_rule",
                "force_thickness_rule",
                "id_generation_rule",
                "seed_template_rule",
            ],
            issues,
        )
        if "name_rule" in config["materials_mapping"]:
            _require_dict_keys(
                config["materials_mapping"]["name_rule"],
                "materials_mapping.name_rule",
                [
                    "csv_source_column",
                    "cdt_field",
                    "trim_whitespace",
                    "forbidden_characters",
                    "allow_automatic_truncation",
                    "require_unique_after_normalization",
                    "legacy_shortened_names_are_rule_violations",
                ],
                issues,
            )
        if "roughness_rule" in config["materials_mapping"]:
            _require_dict_keys(
                config["materials_mapping"]["roughness_rule"],
                "materials_mapping.roughness_rule",
                [
                    "csv_source_column",
                    "cdt_field",
                    "allowed_csv_values",
                    "csv_to_cdt",
                ],
                issues,
            )
        if "description_rule" in config["materials_mapping"]:
            _require_dict_keys(
                config["materials_mapping"]["description_rule"],
                "materials_mapping.description_rule",
                [
                    "csv_source_column",
                    "cdt_field",
                    "copy_notes_to_description",
                    "trim_whitespace",
                    "replace_delimiter_with_space",
                    "collapse_internal_whitespace",
                ],
                issues,
            )
        if "force_thickness_rule" in config["materials_mapping"]:
            _require_dict_keys(
                config["materials_mapping"]["force_thickness_rule"],
                "materials_mapping.force_thickness_rule",
                [
                    "csv_source_column",
                    "cdt_field",
                    "detailed_truthy_values",
                    "detailed_falsy_values",
                    "nomass_default_value",
                    "detailed_requires_positive_default_thickness_when_true",
                ],
                issues,
            )
        if "id_generation_rule" in config["materials_mapping"]:
            _require_dict_keys(
                config["materials_mapping"]["id_generation_rule"],
                "materials_mapping.id_generation_rule",
                [
                    "cdt_field",
                    "source",
                    "strategy",
                    "assignment_order",
                    "reuse_existing_ids",
                ],
                issues,
            )
        if "seed_template_rule" in config["materials_mapping"]:
            _require_dict_keys(
                config["materials_mapping"]["seed_template_rule"],
                "materials_mapping.seed_template_rule",
                [
                    "reference_cdt_file",
                    "detailed_seed_name",
                    "nomass_seed_name",
                    "use_seed_only_for_unmapped_fields",
                    "rule_mapped_fields_always_override_seed_fields",
                    "prefer_designbuilder_exported_seed_over_legacy_generated_seed",
                ],
                issues,
            )
    if "maintenance_convention" in config:
        _require_dict_keys(
            config["maintenance_convention"],
            "maintenance_convention",
            ["sync_rules_md_with_config", "note"],
            issues,
        )

    return issues


def validate_schema_file(schema: dict) -> list[str]:
    issues: list[str] = []
    _require_dict_keys(
        schema,
        "schema",
        [
            "sample_file",
            "schema_type",
            "delimiter",
            "line_structure",
            "counts",
            "category_ids",
            "fields",
            "notes",
        ],
        issues,
    )

    if "counts" in schema:
        _require_dict_keys(
            schema["counts"],
            "schema.counts",
            ["line_count_at_capture", "category_id_count", "field_count", "record_count_at_capture"],
            issues,
        )

    if "line_structure" in schema:
        if not isinstance(schema["line_structure"], list) or len(schema["line_structure"]) < 3:
            issues.append("schema.line_structure must contain at least 3 sections.")

    if "delimiter" in schema and schema["delimiter"] != "#":
        issues.append("schema.delimiter must be '#'.")

    if "fields" in schema and "counts" in schema:
        if len(schema["fields"]) != schema["counts"]["field_count"]:
            issues.append("schema.fields count does not match schema.counts.field_count.")

    if "category_ids" in schema and "counts" in schema:
        if len(schema["category_ids"]) != schema["counts"]["category_id_count"]:
            issues.append("schema.category_ids count does not match schema.counts.category_id_count.")

    return issues


def validate_config_logic(config: dict) -> list[str]:
    issues: list[str] = []

    artifacts = config["artifacts"]
    behavior = config["behavior"]
    ddf_cdt = config["ddf_cdt"]
    input_files = config["input_files"]
    materials = config["materials"]
    materials_mapping = config["materials_mapping"]
    name_rule = materials_mapping["name_rule"]
    roughness_rule = materials_mapping["roughness_rule"]
    description_rule = materials_mapping["description_rule"]
    force_thickness_rule = materials_mapping["force_thickness_rule"]
    id_generation_rule = materials_mapping["id_generation_rule"]
    seed_template_rule = materials_mapping["seed_template_rule"]

    if artifacts["final_import_artifact"] != ".ddf":
        issues.append("artifacts.final_import_artifact must be '.ddf'.")
    if artifacts["editable_intermediate_artifact"] != ".cdt":
        issues.append("artifacts.editable_intermediate_artifact must be '.cdt'.")
    if not artifacts["per_run_output_must_use_new_subfolder"]:
        issues.append("artifacts.per_run_output_must_use_new_subfolder must be true.")
    if artifacts["output_subfolder_name_source"] != "input_data_name_with_optional_timestamp_suffix":
        issues.append(
            "artifacts.output_subfolder_name_source must be 'input_data_name_with_optional_timestamp_suffix'."
        )
    if not artifacts["output_subfolder_must_prevent_overwrite_between_runs"]:
        issues.append("artifacts.output_subfolder_must_prevent_overwrite_between_runs must be true.")
    if behavior["csv_is_final_artifact"] == artifacts["csv_is_not_final_import_artifact"]:
        issues.append("CSV artifact flags are logically inconsistent.")
    if not behavior["ddf_is_final_artifact"]:
        issues.append("behavior.ddf_is_final_artifact must be true.")
    if not behavior["cdt_is_editable_intermediate"]:
        issues.append("behavior.cdt_is_editable_intermediate must be true.")
    if behavior["allow_manual_new_files"] and behavior["default_operation_is_repair_not_create"]:
        issues.append("Manual new files cannot be allowed when default operation is repair-not-create.")
    if behavior["manual_creation_of_cdt_or_ddf_without_defined_generation_step"]:
        issues.append("Manual creation of CDT/DDF without a generation step must remain false.")
    if input_files["discovery_mode"] != "scan_all_matching_csv_in_input_folder":
        issues.append("input_files.discovery_mode must be 'scan_all_matching_csv_in_input_folder'.")
    if input_files["file_extension"] != ".csv":
        issues.append("input_files.file_extension must be '.csv'.")
    if input_files["sort_order"] != "filename_ascending":
        issues.append("input_files.sort_order must be 'filename_ascending'.")
    if not input_files["allow_multiple_files_per_kind"]:
        issues.append("input_files.allow_multiple_files_per_kind must be true.")
    if input_files["type_column"] != "Type":
        issues.append("input_files.type_column must be 'Type'.")
    if input_files["detailed_type_value"] != "Detailed":
        issues.append("input_files.detailed_type_value must be 'Detailed'.")
    if input_files["nomass_type_value"] != "NoMass":
        issues.append("input_files.nomass_type_value must be 'NoMass'.")
    if "_" not in input_files["ignore_filename_prefixes"]:
        issues.append("input_files.ignore_filename_prefixes must include '_'.")
    if not input_files["detailed_required_columns"] or not input_files["nomass_required_columns"]:
        issues.append("input_files required column lists must be non-empty.")
    if not ddf_cdt["ddf_is_not_directly_editable_text"]:
        issues.append("ddf_cdt.ddf_is_not_directly_editable_text must be true.")
    if ddf_cdt["cdt_field_delimiter"] != "#":
        issues.append("ddf_cdt.cdt_field_delimiter must be '#'.")
    if len(ddf_cdt["cdt_expected_sections"]) < 3:
        issues.append("ddf_cdt.cdt_expected_sections must define category/header/record sections.")
    if not ddf_cdt["reference_package_cdt_entry_name"].lower().endswith(".cdt"):
        issues.append("ddf_cdt.reference_package_cdt_entry_name must end with '.cdt'.")
    if not ddf_cdt["package_entry_name_must_match_reference_ddf"]:
        issues.append("ddf_cdt.package_entry_name_must_match_reference_ddf must be true.")
    if not materials["reference_must_be_designbuilder_exported_materials_ddf"]:
        issues.append("materials.reference_must_be_designbuilder_exported_materials_ddf must be true.")
    if materials["system_materials_editable_directly"]:
        issues.append("materials.system_materials_editable_directly must be false.")
    if not materials["clone_system_material_before_edit"]:
        issues.append("materials.clone_system_material_before_edit must be true.")
    if not materials["prefer_user_defined_materials_for_external_generation"]:
        issues.append("materials.prefer_user_defined_materials_for_external_generation must be true.")
    if name_rule["cdt_field"] != "Name":
        issues.append("materials_mapping.name_rule.cdt_field must be 'Name'.")
    if not name_rule["trim_whitespace"]:
        issues.append("materials_mapping.name_rule.trim_whitespace must be true.")
    if "#" not in name_rule["forbidden_characters"]:
        issues.append("materials_mapping.name_rule.forbidden_characters must include '#'.")
    if name_rule["allow_automatic_truncation"]:
        issues.append("materials_mapping.name_rule.allow_automatic_truncation must be false.")
    if not name_rule["require_unique_after_normalization"]:
        issues.append("materials_mapping.name_rule.require_unique_after_normalization must be true.")

    allowed_roughness_values = [
        "VeryRough",
        "Rough",
        "MediumRough",
        "MediumSmooth",
        "Smooth",
        "VerySmooth",
    ]
    if roughness_rule["cdt_field"] != "Roughness":
        issues.append("materials_mapping.roughness_rule.cdt_field must be 'Roughness'.")
    if roughness_rule["allowed_csv_values"] != allowed_roughness_values:
        issues.append("materials_mapping.roughness_rule.allowed_csv_values must match the canonical 6-value order.")
    if set(roughness_rule["csv_to_cdt"]) != set(allowed_roughness_values):
        issues.append("materials_mapping.roughness_rule.csv_to_cdt keys must match allowed_csv_values exactly.")

    if description_rule["cdt_field"] != "Description":
        issues.append("materials_mapping.description_rule.cdt_field must be 'Description'.")
    if not description_rule["copy_notes_to_description"]:
        issues.append("materials_mapping.description_rule.copy_notes_to_description must be true.")
    if not description_rule["replace_delimiter_with_space"]:
        issues.append("materials_mapping.description_rule.replace_delimiter_with_space must be true.")

    truthy_values = {value.lower() for value in force_thickness_rule["detailed_truthy_values"]}
    falsy_values = {value.lower() for value in force_thickness_rule["detailed_falsy_values"]}
    if force_thickness_rule["cdt_field"] != "ForceThickness":
        issues.append("materials_mapping.force_thickness_rule.cdt_field must be 'ForceThickness'.")
    if truthy_values & falsy_values:
        issues.append("materials_mapping.force_thickness_rule truthy/falsy values must not overlap.")
    if force_thickness_rule["nomass_default_value"] != "0":
        issues.append("materials_mapping.force_thickness_rule.nomass_default_value must be '0'.")
    if not force_thickness_rule["detailed_requires_positive_default_thickness_when_true"]:
        issues.append(
            "materials_mapping.force_thickness_rule.detailed_requires_positive_default_thickness_when_true must be true."
        )

    if id_generation_rule["cdt_field"] != "Id":
        issues.append("materials_mapping.id_generation_rule.cdt_field must be 'Id'.")
    if id_generation_rule["source"] != "generated_not_from_csv":
        issues.append("materials_mapping.id_generation_rule.source must be 'generated_not_from_csv'.")
    if id_generation_rule["strategy"] != "reference_max_plus_one":
        issues.append("materials_mapping.id_generation_rule.strategy must be 'reference_max_plus_one'.")
    if id_generation_rule["assignment_order"] != ["detailed_csv_file_order", "nomass_csv_file_order"]:
        issues.append(
            "materials_mapping.id_generation_rule.assignment_order must be ['detailed_csv_file_order', 'nomass_csv_file_order']."
        )
    if id_generation_rule["reuse_existing_ids"]:
        issues.append("materials_mapping.id_generation_rule.reuse_existing_ids must be false.")
    if seed_template_rule["reference_cdt_file"] != config["reference_files"]["reference_exported_cdt"]:
        issues.append("materials_mapping.seed_template_rule.reference_cdt_file must match reference_files.reference_exported_cdt.")
    if not seed_template_rule["use_seed_only_for_unmapped_fields"]:
        issues.append("materials_mapping.seed_template_rule.use_seed_only_for_unmapped_fields must be true.")
    if not seed_template_rule["rule_mapped_fields_always_override_seed_fields"]:
        issues.append("materials_mapping.seed_template_rule.rule_mapped_fields_always_override_seed_fields must be true.")
    if not seed_template_rule["prefer_designbuilder_exported_seed_over_legacy_generated_seed"]:
        issues.append(
            "materials_mapping.seed_template_rule.prefer_designbuilder_exported_seed_over_legacy_generated_seed must be true."
        )

    allowed_output_files = artifacts["allowed_output_files"]
    if not isinstance(allowed_output_files, list) or not allowed_output_files:
        issues.append("artifacts.allowed_output_files must be a non-empty list.")
    else:
        allowed_suffixes = {Path(name).suffix.lower() for name in allowed_output_files}
        if allowed_suffixes != {".cdt", ".ddf"}:
            issues.append("artifacts.allowed_output_files should contain one .cdt and one .ddf output.")

    return issues


def _read_non_empty_lines(file_path: Path) -> list[str]:
    return [line.rstrip("\r\n") for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _split_cdt_line(line: str, delimiter: str) -> list[str]:
    parts = line.split(delimiter)
    if parts and parts[0] == "":
        parts = parts[1:]
    return [part.rstrip() for part in parts]


def infer_cdt_structure(cdt_path: Path, delimiter: str) -> dict:
    lines = _read_non_empty_lines(cdt_path)
    category_ids = _split_cdt_line(lines[0], delimiter)
    header_fields = _split_cdt_line(lines[1], delimiter)
    record_lines = lines[2:]
    record_field_counts = [len(_split_cdt_line(line, delimiter)) for line in record_lines]

    return {
        "line_count": len(lines),
        "category_id_count": len(category_ids),
        "header_field_count": len(header_fields),
        "record_count": len(record_lines),
        "record_field_counts_unique": sorted(set(record_field_counts)),
        "category_ids": category_ids,
        "header_fields": header_fields,
        "sample_file": cdt_path.name,
    }


def load_cdt_records(cdt_path: Path, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
    lines = _read_non_empty_lines(cdt_path)
    header_fields = _split_cdt_line(lines[1], delimiter)
    records: list[dict[str, str]] = []
    for line in lines[2:]:
        parts = _split_cdt_line(line, delimiter)
        record = {
            field: parts[index] if index < len(parts) else ""
            for index, field in enumerate(header_fields)
        }
        records.append(record)
    return header_fields, records


def load_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for raw_row in reader:
            cleaned_row: dict[str, str] = {}
            for key, value in raw_row.items():
                if key is None:
                    continue
                cleaned_row[key.strip()] = (value or "").strip()
            rows.append(cleaned_row)
    return rows


def load_csv_fieldnames(csv_path: Path) -> list[str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [field.strip() for field in (reader.fieldnames or []) if field is not None]


def collapse_internal_whitespace(value: str) -> str:
    return " ".join(value.split())


def normalize_name(value: str, name_rule: dict) -> str:
    normalized = value
    if name_rule["trim_whitespace"]:
        normalized = normalized.strip()
    return normalized


def normalize_description(value: str, description_rule: dict, delimiter: str) -> str:
    normalized = value
    if description_rule["replace_delimiter_with_space"]:
        normalized = normalized.replace(delimiter, " ")
    if description_rule["trim_whitespace"]:
        normalized = normalized.strip()
    if description_rule["collapse_internal_whitespace"]:
        normalized = collapse_internal_whitespace(normalized)
    return normalized


def normalize_force_thickness(value: str, force_thickness_rule: dict) -> str:
    normalized = value.strip().lower()
    truthy_values = {item.lower() for item in force_thickness_rule["detailed_truthy_values"]}
    falsy_values = {item.lower() for item in force_thickness_rule["detailed_falsy_values"]}
    if normalized in truthy_values:
        return "1"
    if normalized in falsy_values:
        return "0"
    return "<invalid>"


def map_roughness(value: str, roughness_rule: dict) -> str:
    return roughness_rule["csv_to_cdt"].get(value.strip(), f"<invalid:{value.strip()}>")


def discover_csv_sources(paths: WorkspacePaths, config: dict) -> tuple[list[CsvSource], list[str]]:
    input_cfg = config["input_files"]
    file_extension = input_cfg["file_extension"].lower()
    ignore_prefixes = tuple(input_cfg["ignore_filename_prefixes"])
    type_column = input_cfg["type_column"]
    expected_type_values = {
        "detailed": input_cfg["detailed_type_value"].strip().lower(),
        "nomass": input_cfg["nomass_type_value"].strip().lower(),
    }
    required_columns = {
        "detailed": set(input_cfg["detailed_required_columns"]),
        "nomass": set(input_cfg["nomass_required_columns"]),
    }

    issues: list[str] = []
    sources: list[CsvSource] = []
    if not paths.csv_input.is_dir():
        issues.append(f"Missing CSV input directory: {paths.csv_input}")
        return sources, issues

    requested_names = set(paths.selected_csv_names)
    if requested_names:
        available_names = {
            path.name
            for path in paths.csv_input.iterdir()
            if path.is_file()
        }
        missing_names = sorted(requested_names - available_names)
        for missing_name in missing_names:
            issues.append(f"Requested CSV input was not found: {missing_name}")

    candidate_paths = sorted(
        path for path in paths.csv_input.iterdir()
        if path.is_file()
        and path.suffix.lower() == file_extension
        and not path.name.startswith(ignore_prefixes)
        and (not requested_names or path.name in requested_names)
    )

    if not candidate_paths:
        issues.append("No active CSV files were found in 02_csv_input.")
        return sources, issues

    for csv_path in candidate_paths:
        fieldnames = load_csv_fieldnames(csv_path)
        if not fieldnames:
            issues.append(f"{csv_path.name} does not contain a readable CSV header.")
            continue

        rows = load_csv_rows(csv_path)
        if not rows:
            issues.append(f"{csv_path.name} contains no data rows.")
            continue

        columns = set(fieldnames)
        candidate_kinds = [
            kind
            for kind, required in required_columns.items()
            if required.issubset(columns)
        ]
        if not candidate_kinds:
            issues.append(f"{csv_path.name} does not match the required columns for Detailed or NoMass materials.")
            continue

        matched_kinds: list[str] = []
        for kind in candidate_kinds:
            expected_type = expected_type_values[kind]
            row_types = {
                row.get(type_column, "").strip().lower()
                for row in rows
            }
            if row_types == {expected_type}:
                matched_kinds.append(kind)

        if len(matched_kinds) != 1:
            issues.append(
                f"{csv_path.name} could not be classified uniquely as Detailed or NoMass from its columns and Type values."
            )
            continue

        sources.append(CsvSource(kind=matched_kinds[0], path=csv_path, rows=rows))

    return sources, issues


def get_source_sequence(paths: WorkspacePaths, config: dict) -> list[CsvSource]:
    discovered_sources, discovery_issues = discover_csv_sources(paths, config)
    if discovery_issues:
        raise ValueError("; ".join(discovery_issues))

    grouped_sources = {
        "detailed": [source for source in discovered_sources if source.kind == "detailed"],
        "nomass": [source for source in discovered_sources if source.kind == "nomass"],
    }
    ordered_sources: list[CsvSource] = []
    kind_order = {
        "detailed_csv_file_order": "detailed",
        "nomass_csv_file_order": "nomass",
    }
    for token in config["materials_mapping"]["id_generation_rule"]["assignment_order"]:
        ordered_sources.extend(grouped_sources[kind_order[token]])
    return ordered_sources


def validate_csv_inputs_against_material_rules(paths: WorkspacePaths, config: dict) -> list[str]:
    issues: list[str] = []
    materials_mapping = config["materials_mapping"]
    name_rule = materials_mapping["name_rule"]
    roughness_rule = materials_mapping["roughness_rule"]
    force_thickness_rule = materials_mapping["force_thickness_rule"]
    input_cfg = config["input_files"]

    discovered_sources, discovery_issues = discover_csv_sources(paths, config)
    issues.extend(discovery_issues)
    if discovery_issues:
        return issues

    seen_names: dict[str, str] = {}
    for source in get_source_sequence(paths, config):
        csv_path = source.path
        source_kind = source.kind
        for row_number, row in enumerate(source.rows, start=2):
            name = normalize_name(row.get(name_rule["csv_source_column"], ""), name_rule)
            if not name:
                issues.append(f"{csv_path.name}:{row_number} has a blank material name after normalization.")
                continue

            for forbidden_character in name_rule["forbidden_characters"]:
                if forbidden_character in name:
                    issues.append(
                        f"{csv_path.name}:{row_number} material name '{name}' contains forbidden character '{forbidden_character}'."
                    )

            if name_rule["require_unique_after_normalization"]:
                previous_location = seen_names.get(name)
                current_location = f"{csv_path.name}:{row_number}"
                if previous_location:
                    issues.append(
                        f"Duplicate normalized material name '{name}' found at {previous_location} and {current_location}."
                    )
                else:
                    seen_names[name] = current_location

            roughness_value = row.get(roughness_rule["csv_source_column"], "")
            if roughness_value not in roughness_rule["allowed_csv_values"]:
                issues.append(
                    f"{csv_path.name}:{row_number} roughness '{roughness_value}' is outside the allowed canonical values."
                )

            type_value = row.get(input_cfg["type_column"], "").strip().lower()
            expected_type = (
                input_cfg["detailed_type_value"].strip().lower()
                if source_kind == "detailed"
                else input_cfg["nomass_type_value"].strip().lower()
            )
            if type_value != expected_type:
                issues.append(
                    f"{csv_path.name}:{row_number} has {input_cfg['type_column']} '{row.get(input_cfg['type_column'], '')}' "
                    f"but file ordering expects '{expected_type}'."
                )

            if source_kind == "detailed":
                normalized_force_thickness = normalize_force_thickness(
                    row.get(force_thickness_rule["csv_source_column"], ""),
                    force_thickness_rule,
                )
                if normalized_force_thickness == "<invalid>":
                    issues.append(
                        f"{csv_path.name}:{row_number} has unsupported ForceThickness value "
                        f"'{row.get(force_thickness_rule['csv_source_column'], '')}'."
                    )
                if (
                    force_thickness_rule["detailed_requires_positive_default_thickness_when_true"]
                    and normalized_force_thickness == "1"
                ):
                    thickness_text = row.get("DefaultThickness_m", "").strip()
                    try:
                        if Decimal(thickness_text) <= 0:
                            issues.append(
                                f"{csv_path.name}:{row_number} requires DefaultThickness_m > 0 when ForceThickness is true."
                            )
                    except InvalidOperation:
                        issues.append(
                            f"{csv_path.name}:{row_number} has invalid DefaultThickness_m '{thickness_text}' for ForceThickness validation."
                        )

    return issues


def values_equivalent(expected: str, actual: str) -> bool:
    expected_value = expected.strip()
    actual_value = actual.strip()
    if expected_value == actual_value:
        return True

    try:
        return Decimal(expected_value) == Decimal(actual_value)
    except InvalidOperation:
        return False


def get_analysis_cdt_path(paths: WorkspacePaths) -> Path:
    if paths.generated_cdt.is_file():
        return paths.generated_cdt
    return paths.reference_final_qa_cdt


def build_seed_record_map(paths: WorkspacePaths, config: dict) -> dict[str, dict[str, str]]:
    delimiter = config["ddf_cdt"]["cdt_field_delimiter"]
    _, records = load_cdt_records(paths.reference_exported_cdt, delimiter)
    records_by_name = {record["Name"]: record for record in records}
    seed_rule = config["materials_mapping"]["seed_template_rule"]

    missing_seed_names = [
        seed_name
        for seed_name in [seed_rule["detailed_seed_name"], seed_rule["nomass_seed_name"]]
        if seed_name not in records_by_name
    ]
    if missing_seed_names:
        raise ValueError(
            "Missing seed records in exported reference CDT: " + ", ".join(missing_seed_names)
        )

    return {
        "detailed": records_by_name[seed_rule["detailed_seed_name"]].copy(),
        "nomass": records_by_name[seed_rule["nomass_seed_name"]].copy(),
    }


def serialize_cdt_line(values: list[str], delimiter: str) -> str:
    safe_values = []
    for value in values:
        text = value if value != "" else " "
        safe_values.append(text)
    return delimiter + f"  {delimiter}".join(safe_values)


def build_generated_record(
    csv_row: dict[str, str],
    source_kind: str,
    next_id: int,
    seed_record: dict[str, str],
    config: dict,
    delimiter: str,
) -> dict[str, str]:
    materials_mapping = config["materials_mapping"]
    name_rule = materials_mapping["name_rule"]
    roughness_rule = materials_mapping["roughness_rule"]
    description_rule = materials_mapping["description_rule"]
    force_thickness_rule = materials_mapping["force_thickness_rule"]

    record = seed_record.copy()
    record["Id"] = str(next_id)
    record["Name"] = normalize_name(csv_row.get(name_rule["csv_source_column"], ""), name_rule)
    record["Roughness"] = map_roughness(csv_row.get(roughness_rule["csv_source_column"], ""), roughness_rule)
    record["Description"] = normalize_description(
        csv_row.get(description_rule["csv_source_column"], ""),
        description_rule,
        delimiter,
    )

    if source_kind == "detailed":
        record["Simple"] = "0"
        record["Detailed"] = "1"
        record["DefaultThickness"] = csv_row.get("DefaultThickness_m", "").strip()
        record["Conductivity (W/mK)"] = csv_row.get("Conductivity_W_mK", "").strip()
        record["Capacity (J/kgK)"] = csv_row.get("SpecificHeat_J_kgK", "").strip()
        record["Density (kg/m3)"] = csv_row.get("Density_kg_m3", "").strip()
        record["ForceThickness"] = normalize_force_thickness(
            csv_row.get(force_thickness_rule["csv_source_column"], ""),
            force_thickness_rule,
        )
    else:
        record["Simple"] = "1"
        record["Detailed"] = "0"
        record["R-Value"] = csv_row.get("ThermalResistance_m2K_W", "").strip()
        record["ForceThickness"] = force_thickness_rule["nomass_default_value"]

    for csv_field, cdt_field in [
        ("ThermalAbsorptance", "ThermalAbsorptance"),
        ("SolarAbsorptance", "SolarAbsorptance"),
        ("VisibleAbsorptance", "VisibleAbsorptance"),
    ]:
        record[cdt_field] = csv_row.get(csv_field, "").strip()

    return record


def generate_material_records(paths: WorkspacePaths, config: dict, schema: dict) -> list[dict[str, str]]:
    delimiter = schema["delimiter"]
    seed_records = build_seed_record_map(paths, config)
    reference_fields, reference_records = load_cdt_records(paths.reference_exported_cdt, delimiter)
    if reference_fields != schema["fields"]:
        raise ValueError("Exported reference CDT header does not match the schema fields.")

    id_field = config["materials_mapping"]["id_generation_rule"]["cdt_field"]
    max_reference_id = max(int(record[id_field]) for record in reference_records)
    next_id = max_reference_id + 1

    generated_records: list[dict[str, str]] = []
    for source in get_source_sequence(paths, config):
        for csv_row in source.rows:
            generated_records.append(
                build_generated_record(
                    csv_row=csv_row,
                    source_kind=source.kind,
                    next_id=next_id,
                    seed_record=seed_records[source.kind],
                    config=config,
                    delimiter=delimiter,
                )
            )
            next_id += 1

    return generated_records


def write_generated_cdt(paths: WorkspacePaths, schema: dict, records: list[dict[str, str]]) -> Path:
    delimiter = schema["delimiter"]
    field_order = schema["fields"]
    lines = [
        serialize_cdt_line(schema["category_ids"], delimiter),
        serialize_cdt_line(field_order, delimiter),
    ]
    for record in records:
        row_values = [record.get(field, "").strip() for field in field_order]
        lines.append(serialize_cdt_line(row_values, delimiter))

    content = "\n".join(lines) + "\n"
    paths.output.mkdir(parents=True, exist_ok=True)
    paths.generated_cdt.write_text(content, encoding="utf-8")
    return paths.generated_cdt


def get_reference_package_cdt_entry_name(paths: WorkspacePaths, config: dict) -> str:
    configured_entry_name = config["ddf_cdt"]["reference_package_cdt_entry_name"]
    with zipfile.ZipFile(paths.reference_ddf) as archive:
        cdt_entries = [name for name in archive.namelist() if name.lower().endswith(".cdt")]

    if len(cdt_entries) != 1:
        raise ValueError(
            f"Reference DDF must contain exactly one CDT entry for packaging, found {len(cdt_entries)}."
        )
    reference_entry_name = cdt_entries[0]

    if config["ddf_cdt"]["package_entry_name_must_match_reference_ddf"] and reference_entry_name != configured_entry_name:
        raise ValueError(
            "Configured package CDT entry name does not match the reference DDF entry name: "
            f"{configured_entry_name} vs {reference_entry_name}."
        )

    return reference_entry_name


def package_generated_ddf(paths: WorkspacePaths, config: dict) -> Path:
    if not paths.generated_cdt.is_file():
        raise ValueError("Generated CDT file does not exist yet and cannot be packaged.")

    entry_name = get_reference_package_cdt_entry_name(paths, config)
    paths.output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(paths.generated_ddf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(paths.generated_cdt, arcname=entry_name)
    return paths.generated_ddf


def validate_generated_ddf_package(paths: WorkspacePaths, config: dict) -> list[str]:
    issues: list[str] = []
    if not paths.generated_ddf.is_file():
        return [f"Missing generated DDF: {paths.generated_ddf}"]
    if not paths.generated_cdt.is_file():
        return [f"Missing generated CDT required for DDF validation: {paths.generated_cdt}"]

    try:
        expected_entry_name = get_reference_package_cdt_entry_name(paths, config)
    except ValueError as error:
        return [str(error)]

    try:
        with zipfile.ZipFile(paths.generated_ddf) as archive:
            entry_names = archive.namelist()
            cdt_entries = [name for name in entry_names if name.lower().endswith(".cdt")]
            if expected_entry_name not in entry_names:
                issues.append(
                    f"Generated DDF does not contain expected CDT entry '{expected_entry_name}'."
                )
            if len(cdt_entries) != 1:
                issues.append(
                    f"Generated DDF should contain exactly one CDT entry, found {len(cdt_entries)}."
                )
            if expected_entry_name in entry_names:
                packaged_bytes = archive.read(expected_entry_name)
                generated_bytes = paths.generated_cdt.read_bytes()
                if packaged_bytes != generated_bytes:
                    issues.append("Generated DDF CDT entry content does not match Materials_generated.cdt.")
    except zipfile.BadZipFile:
        issues.append("Generated DDF is not readable as a zip-compatible package.")

    return issues


def build_generation_summary(records: list[dict[str, str]]) -> GenerationSummary:
    if not records:
        raise ValueError("Cannot build generation summary from an empty record set.")

    ids = [int(record["Id"]) for record in records]
    detailed_count = sum(1 for record in records if record.get("Detailed", "").strip() == "1")
    nomass_count = sum(1 for record in records if record.get("Simple", "").strip() == "1")
    return GenerationSummary(
        total_records=len(records),
        detailed_count=detailed_count,
        nomass_count=nomass_count,
        id_start=min(ids),
        id_end=max(ids),
    )


def print_generation_summary(summary: GenerationSummary, final_output_path: Path) -> None:
    print("GENERATION SUMMARY")
    print(f"- Total records: {summary.total_records}")
    print(f"- Detailed records: {summary.detailed_count}")
    print(f"- NoMass records: {summary.nomass_count}")
    print(f"- Id range: {summary.id_start} -> {summary.id_end}")
    print(f"- Final output path: {final_output_path}")
    print("")


def align_csv_inputs_to_cdt(
    cdt_path: Path,
    paths: WorkspacePaths,
    config: dict,
    delimiter: str,
) -> tuple[list[RecordMatch], AlignmentCoverage]:
    name_rule = config["materials_mapping"]["name_rule"]
    _, cdt_records = load_cdt_records(cdt_path, delimiter)
    normalized_cdt_by_name = {
        normalize_name(record["Name"], name_rule): record
        for record in cdt_records
    }
    unused_cdt_names = set(normalized_cdt_by_name)

    coverage = AlignmentCoverage()
    source_coverages = {
        "detailed": coverage.detailed,
        "nomass": coverage.nomass,
    }

    matches: list[RecordMatch] = []
    for source in get_source_sequence(paths, config):
        source_coverage = source_coverages[source.kind]
        source_coverage.csv_rows += len(source.rows)

        for csv_row in source.rows:
            csv_name = normalize_name(csv_row.get(name_rule["csv_source_column"], ""), name_rule)
            if not csv_name:
                source_coverage.unmatched_rows.append("<blank name>")
                continue

            if csv_name in normalized_cdt_by_name and csv_name in unused_cdt_names:
                unused_cdt_names.remove(csv_name)
                source_coverage.exact_matches += 1
                cdt_record = normalized_cdt_by_name[csv_name]
                matches.append(
                    RecordMatch(
                        source_kind=source.kind,
                        match_type="exact",
                        csv_name=csv_name,
                        cdt_name=cdt_record["Name"],
                        csv_row=csv_row,
                        cdt_row=cdt_record,
                    )
                )
                continue

            prefix_candidates = sorted(
                candidate_name
                for candidate_name in unused_cdt_names
                if csv_name.startswith(candidate_name)
            )
            if len(prefix_candidates) == 1:
                matched_name = prefix_candidates[0]
                unused_cdt_names.remove(matched_name)
                cdt_record = normalized_cdt_by_name[matched_name]
                source_coverage.prefix_matches.append((csv_name, cdt_record["Name"]))
                matches.append(
                    RecordMatch(
                        source_kind=source.kind,
                        match_type="prefix",
                        csv_name=csv_name,
                        cdt_name=cdt_record["Name"],
                        csv_row=csv_row,
                        cdt_row=cdt_record,
                    )
                )
                continue

            source_coverage.unmatched_rows.append(csv_name)

    coverage.unused_cdt_names = sorted(unused_cdt_names)
    return matches, coverage


def analyse_id_generation_rule(matches: list[RecordMatch], config: dict) -> IdRuleAnalysis:
    id_field = config["materials_mapping"]["id_generation_rule"]["cdt_field"]
    parsed_ids: list[int] = []
    issues: list[str] = []

    for match in matches:
        raw_id = match.cdt_row.get(id_field, "").strip()
        try:
            parsed_ids.append(int(raw_id))
        except ValueError:
            issues.append(f"Record '{match.cdt_name}' has non-integer Id '{raw_id}'.")

    if len(parsed_ids) != len(set(parsed_ids)):
        issues.append("Current aligned CDT records do not have unique Id values.")
    if any(next_id <= current_id for current_id, next_id in zip(parsed_ids, parsed_ids[1:])):
        issues.append("Current aligned CDT Id values are not strictly increasing in configured generator order.")

    return IdRuleAnalysis(
        total_count=len(matches),
        numeric_count=len(parsed_ids),
        unique_count=len(set(parsed_ids)),
        issues=issues,
    )


def evaluate_mapping_rule(
    matches: list[RecordMatch],
    cdt_field: str,
    source_scope: str,
    rule_name: str,
    expected_builder: Callable[[dict[str, str]], str],
) -> MappingResult:
    scoped_matches = [
        match for match in matches if source_scope == "both" or match.source_kind == source_scope
    ]

    mismatches: list[MappingMismatch] = []
    for match in scoped_matches:
        expected = expected_builder(match.csv_row).strip()
        actual = match.cdt_row.get(cdt_field, "").strip()
        if not values_equivalent(expected, actual):
            mismatches.append(
                MappingMismatch(
                    csv_name=match.csv_name,
                    cdt_name=match.cdt_name,
                    expected=expected,
                    actual=actual,
                )
            )

    return MappingResult(
        rule_name=rule_name,
        cdt_field=cdt_field,
        source_scope=source_scope,
        matched_count=len(scoped_matches) - len(mismatches),
        total_count=len(scoped_matches),
        mismatches=mismatches,
    )


def classify_template_fields(
    fields: list[str],
    matches: list[RecordMatch],
    mapped_fields: set[str],
) -> tuple[list[tuple[str, str]], list[str]]:
    constant_fields: list[tuple[str, str]] = []
    varying_fields: list[str] = []

    for field in fields:
        if field in mapped_fields:
            continue

        values = {match.cdt_row.get(field, "").strip() for match in matches}
        if len(values) == 1:
            constant_fields.append((field, next(iter(values))))
        else:
            varying_fields.append(field)

    return constant_fields, varying_fields


def print_mapping_analysis(paths: WorkspacePaths, config: dict, schema: dict) -> list[str]:
    delimiter = schema["delimiter"]
    analysis_cdt_path = get_analysis_cdt_path(paths)
    materials_mapping = config["materials_mapping"]
    name_rule = materials_mapping["name_rule"]
    roughness_rule = materials_mapping["roughness_rule"]
    description_rule = materials_mapping["description_rule"]
    force_thickness_rule = materials_mapping["force_thickness_rule"]
    id_generation_rule = materials_mapping["id_generation_rule"]

    fields, _ = load_cdt_records(analysis_cdt_path, delimiter)
    matches, coverage = align_csv_inputs_to_cdt(analysis_cdt_path, paths, config, delimiter)
    csv_input_issues = validate_csv_inputs_against_material_rules(paths, config)

    baseline_direct_rules = [
        ("DefaultThickness", "detailed", "DefaultThickness_m", "DefaultThickness <- CSV DefaultThickness_m"),
        ("Conductivity (W/mK)", "detailed", "Conductivity_W_mK", "Conductivity <- CSV Conductivity_W_mK"),
        ("Capacity (J/kgK)", "detailed", "SpecificHeat_J_kgK", "Capacity <- CSV SpecificHeat_J_kgK"),
        ("Density (kg/m3)", "detailed", "Density_kg_m3", "Density <- CSV Density_kg_m3"),
        ("ThermalAbsorptance", "both", "ThermalAbsorptance", "ThermalAbsorptance <- CSV ThermalAbsorptance"),
        ("SolarAbsorptance", "both", "SolarAbsorptance", "SolarAbsorptance <- CSV SolarAbsorptance"),
        ("VisibleAbsorptance", "both", "VisibleAbsorptance", "VisibleAbsorptance <- CSV VisibleAbsorptance"),
        ("R-Value", "nomass", "ThermalResistance_m2K_W", "R-Value <- CSV ThermalResistance_m2K_W"),
    ]
    baseline_direct_results = [
        evaluate_mapping_rule(
            matches,
            cdt_field=cdt_field,
            source_scope=source_scope,
            rule_name=rule_name,
            expected_builder=lambda row, csv_field=csv_field: row.get(csv_field, ""),
        )
        for cdt_field, source_scope, csv_field, rule_name in baseline_direct_rules
    ]

    derived_results = [
        evaluate_mapping_rule(
            matches,
            cdt_field="Simple",
            source_scope="both",
            rule_name="Simple <- derived from CSV Type",
            expected_builder=lambda row: "1" if row.get("Type", "").strip().lower() == "nomass" else "0",
        ),
        evaluate_mapping_rule(
            matches,
            cdt_field="Detailed",
            source_scope="both",
            rule_name="Detailed <- derived from CSV Type",
            expected_builder=lambda row: "1" if row.get("Type", "").strip().lower() == "detailed" else "0",
        ),
    ]

    rule_based_results = [
        evaluate_mapping_rule(
            matches,
            cdt_field=name_rule["cdt_field"],
            source_scope="both",
            rule_name="Name <- normalized CSV Name",
            expected_builder=lambda row: normalize_name(row.get(name_rule["csv_source_column"], ""), name_rule),
        ),
        evaluate_mapping_rule(
            matches,
            cdt_field=roughness_rule["cdt_field"],
            source_scope="both",
            rule_name="Roughness <- canonical CSV Roughness mapped to DesignBuilder labels",
            expected_builder=lambda row: map_roughness(row.get(roughness_rule["csv_source_column"], ""), roughness_rule),
        ),
        evaluate_mapping_rule(
            matches,
            cdt_field=description_rule["cdt_field"],
            source_scope="both",
            rule_name="Description <- sanitized CSV Notes",
            expected_builder=lambda row: normalize_description(
                row.get(description_rule["csv_source_column"], ""),
                description_rule,
                delimiter,
            ),
        ),
        evaluate_mapping_rule(
            matches,
            cdt_field=force_thickness_rule["cdt_field"],
            source_scope="detailed",
            rule_name="ForceThickness <- normalized CSV ForceThickness for Detailed materials",
            expected_builder=lambda row: normalize_force_thickness(
                row.get(force_thickness_rule["csv_source_column"], ""),
                force_thickness_rule,
            ),
        ),
    ]

    id_analysis = analyse_id_generation_rule(matches, config)
    mapped_fields = {result.cdt_field for result in baseline_direct_results + derived_results + rule_based_results}
    mapped_fields.add(id_generation_rule["cdt_field"])
    constant_fields, varying_fields = classify_template_fields(fields, matches, mapped_fields)

    compliance_issues = list(csv_input_issues)
    for result in [*baseline_direct_results, *derived_results, *rule_based_results]:
        if result.mismatches:
            compliance_issues.append(f"{result.rule_name}: {len(result.mismatches)} mismatches")
    compliance_issues.extend(id_analysis.issues)

    print("CSV-TO-CDT MAPPING ANALYSIS")
    print(f"- Analysis target CDT: {analysis_cdt_path.name}")
    print(f"- Total aligned CSV rows: {len(matches)}")
    print(
        f"- Detailed CSV coverage: {coverage.detailed.csv_rows} rows, "
        f"{coverage.detailed.exact_matches} exact name matches, "
        f"{len(coverage.detailed.prefix_matches)} shortened-name matches, "
        f"{len(coverage.detailed.unmatched_rows)} unmatched."
    )
    print(
        f"- NoMass CSV coverage: {coverage.nomass.csv_rows} rows, "
        f"{coverage.nomass.exact_matches} exact name matches, "
        f"{len(coverage.nomass.prefix_matches)} shortened-name matches, "
        f"{len(coverage.nomass.unmatched_rows)} unmatched."
    )
    print("")

    if csv_input_issues:
        print("RULE INPUT VALIDATION")
        for issue in csv_input_issues:
            print(f"- {issue}")
        print("")

    prefix_examples = [
        *coverage.detailed.prefix_matches,
        *coverage.nomass.prefix_matches,
    ]
    if prefix_examples:
        print("LEGACY SHORTENED-NAME ALIGNMENTS")
        for csv_name, cdt_name in prefix_examples:
            print(f"- {csv_name} -> {cdt_name}")
        if name_rule["legacy_shortened_names_are_rule_violations"]:
            print("- Current name rule treats these shortened names as violations, not as valid mapping behaviour.")
        print("")

    print("BASELINE DIRECT FIELD CHECKS")
    for result in baseline_direct_results:
        print(f"- {result.rule_name}: {result.matched_count}/{result.total_count} matched.")
        if result.mismatches:
            sample = result.mismatches[0]
            print(
                f"  Example mismatch: CSV '{sample.csv_name}' expected '{sample.expected}' "
                f"but CDT '{sample.cdt_name}' contains '{sample.actual}'."
            )
    print("")

    print("DERIVED TYPE CHECKS")
    for result in derived_results:
        print(f"- {result.rule_name}: {result.matched_count}/{result.total_count} matched.")
        if result.mismatches:
            sample = result.mismatches[0]
            print(
                f"  Example mismatch: CSV '{sample.csv_name}' expected '{sample.expected}' "
                f"but CDT '{sample.cdt_name}' contains '{sample.actual}'."
            )
    print("")

    print("RULE-BASED FIELD CHECKS")
    for result in rule_based_results:
        print(f"- {result.rule_name}: {result.matched_count}/{result.total_count} matched.")
        if result.mismatches:
            sample = result.mismatches[0]
            print(
                f"  Example mismatch: CSV '{sample.csv_name}' expected '{sample.expected}' "
                f"but CDT '{sample.cdt_name}' contains '{sample.actual}'."
            )
    print("")

    print("ID GENERATION RULE")
    print(f"- Strategy: {id_generation_rule['strategy']}")
    print(f"- Assignment order: {', '.join(id_generation_rule['assignment_order'])}")
    print(f"- Numeric Id values in aligned records: {id_analysis.numeric_count}/{id_analysis.total_count}")
    print(f"- Unique Id values in aligned records: {id_analysis.unique_count}/{id_analysis.total_count}")
    if id_analysis.issues:
        for issue in id_analysis.issues:
            print(f"- {issue}")
    else:
        print("- Current aligned CDT Id values are numeric, unique, and strictly increasing in configured generator order.")
    print("- Exact Id start value cannot be revalidated from a post-generation sample alone.")
    print("")

    print("TEMPLATE-DRIVEN FIELDS")
    print(
        f"- {len(constant_fields)} fields are constant across all aligned sample rows and therefore behave "
        "like template or seed values in the current sample."
    )
    if constant_fields:
        example_text = ", ".join(f"{field}={value}" for field, value in constant_fields[:8])
        print(f"- Examples: {example_text}")
    print("")

    print("FIELDS REQUIRING GENERATOR LOGIC")
    if varying_fields:
        print(f"- Varying non-template fields outside the current checked rule set: {', '.join(varying_fields)}")
    else:
        print("- No additional varying fields were found outside the current checked rule set.")
    print("")

    print("INTERPRETATION")
    if analysis_cdt_path == paths.generated_cdt:
        if compliance_issues:
            print(
                "- The generated CDT output was analysed directly and still diverges from the current rule set."
            )
            print(
                "- The generator or seed-handling logic must be adjusted before the output can be treated as rule-compliant."
            )
        else:
            print(
                "- The generated CDT output was analysed directly and matches the current rule set."
            )
            print(
                "- The generator is now driven by exported DesignBuilder seed records plus workspace rules, rather than by the legacy QA sample."
            )
    else:
        print(
            "- The current reference sample does not fully comply with the normalized name, roughness, description, "
            "force-thickness, and Id-order rules now defined in workspace_rules.json."
        )
        print(
            "- This is expected at this stage: the purpose of analyse-mapping is now to expose where the legacy sample "
            "and the target generator rules diverge."
        )
        print(
            "- Future CDT generation should follow the config rules even when the current sample contains legacy shortcuts "
            "or placeholder values."
        )
    print("")

    return compliance_issues


def compare_cdt_structure_to_schema(inferred: dict, schema: dict) -> list[str]:
    issues: list[str] = []
    schema_counts = schema["counts"]

    if inferred["category_id_count"] != schema_counts["category_id_count"]:
        issues.append(
            f"CDT category count mismatch: inferred {inferred['category_id_count']} vs schema {schema_counts['category_id_count']}."
        )
    if inferred["header_field_count"] != schema_counts["field_count"]:
        issues.append(
            f"CDT header field count mismatch: inferred {inferred['header_field_count']} vs schema {schema_counts['field_count']}."
        )
    if inferred["line_count"] < 3:
        issues.append("CDT must contain at least category/header/record lines.")
    if inferred["record_field_counts_unique"] != [schema_counts["field_count"]]:
        issues.append(
            "CDT record field counts are inconsistent with schema field count."
        )
    if inferred["category_ids"] != schema["category_ids"]:
        issues.append("CDT category id line does not match schema category_ids.")
    if inferred["header_fields"] != schema["fields"]:
        issues.append("CDT header fields do not match schema fields.")

    return issues


def validate_workspace(paths: WorkspacePaths, config: dict, schema: dict) -> list[str]:
    issues: list[str] = []

    required_dirs = [
        paths.designbuilder_format,
        paths.csv_input,
        paths.output,
        paths.scripts,
        paths.archive,
    ]
    for directory in required_dirs:
        if not directory.is_dir():
            issues.append(f"Missing required directory: {directory}")

    required_files = [
        paths.reference_ddf,
        paths.reference_exported_cdt,
        paths.reference_final_qa_cdt,
        paths.reference_final_qa_ddf,
        paths.reference_final_qa_schema,
    ]
    for file_path in required_files:
        if not file_path.is_file():
            issues.append(f"Missing required file: {file_path}")

    if paths.reference_ddf.exists() and paths.reference_ddf.parent != paths.designbuilder_format:
        issues.append("Reference DDF is outside 01_designbuilder_format.")
    if paths.reference_exported_cdt.exists() and paths.reference_exported_cdt.parent != paths.designbuilder_format:
        issues.append("Reference exported CDT is outside 01_designbuilder_format.")
    if paths.reference_final_qa_cdt.exists() and paths.reference_final_qa_cdt.parent != paths.designbuilder_format:
        issues.append("Reference FINAL_QA CDT is outside 01_designbuilder_format.")
    if paths.reference_final_qa_ddf.exists() and paths.reference_final_qa_ddf.parent != paths.designbuilder_format:
        issues.append("Reference FINAL_QA DDF is outside 01_designbuilder_format.")
    if paths.reference_final_qa_schema.exists() and paths.reference_final_qa_schema.parent != paths.designbuilder_format:
        issues.append("Reference FINAL_QA schema is outside 01_designbuilder_format.")

    discovered_sources, discovery_issues = discover_csv_sources(paths, config)
    issues.extend(discovery_issues)
    for source in discovered_sources:
        if source.path.parent != paths.csv_input:
            issues.append(f"Discovered CSV is outside 02_csv_input: {source.path}")

    output_files = [item.name for item in paths.output.iterdir() if item.is_file()] if paths.output.exists() else []
    allowed_output_files = set(config["artifacts"]["allowed_output_files"])
    unexpected_outputs = sorted(name for name in output_files if name not in allowed_output_files)
    for name in unexpected_outputs:
        issues.append(f"Unexpected file in output folder: {name}")

    if paths.reference_ddf.is_file():
        try:
            with zipfile.ZipFile(paths.reference_ddf) as archive:
                entry_names = archive.namelist()
            cdt_entries = [name for name in entry_names if name.lower().endswith(".cdt")]
            if not cdt_entries:
                issues.append("Reference DDF does not contain any CDT entry.")
            elif config["ddf_cdt"]["package_entry_name_must_match_reference_ddf"]:
                expected_entry_name = config["ddf_cdt"]["reference_package_cdt_entry_name"]
                if expected_entry_name not in cdt_entries:
                    issues.append(
                        f"Reference DDF does not contain configured package entry name '{expected_entry_name}'."
                    )
        except zipfile.BadZipFile:
            issues.append("Reference DDF is not readable as a zip-compatible package.")

    if paths.reference_final_qa_ddf.is_file():
        try:
            with zipfile.ZipFile(paths.reference_final_qa_ddf) as archive:
                entry_names = archive.namelist()
            if not any(name.lower().endswith(".cdt") for name in entry_names):
                issues.append("Reference FINAL_QA DDF does not contain any CDT entry.")
        except zipfile.BadZipFile:
            issues.append("Reference FINAL_QA DDF is not readable as a zip-compatible package.")

    if paths.reference_exported_cdt.is_file():
        inferred = infer_cdt_structure(paths.reference_exported_cdt, schema["delimiter"])
        issues.extend(compare_cdt_structure_to_schema(inferred, schema))

    if paths.reference_final_qa_cdt.is_file():
        inferred = infer_cdt_structure(paths.reference_final_qa_cdt, schema["delimiter"])
        issues.extend(compare_cdt_structure_to_schema(inferred, schema))

    if paths.generated_ddf.is_file():
        issues.extend(validate_generated_ddf_package(paths, config))

    return issues


def print_workspace_summary(paths: WorkspacePaths, config: dict, schema: dict) -> None:
    print("WORKSPACE SUMMARY")
    print(f"Root: {paths.root}")
    print(f"Rules config: {paths.rules_config}")
    print(f"Workspace name: {config['workspace_name']}")
    print(f"Purpose: {config['scope']['purpose']}")
    print(f"Reference folder: {paths.designbuilder_format}")
    print(f"CSV input folder: {paths.csv_input}")
    print(f"Output folder: {paths.output}")
    print(f"Scripts folder: {paths.scripts}")
    print(f"Archive folder: {paths.archive}")
    print("")
    print("REFERENCE FILES")
    print(f"- {paths.reference_ddf.name}")
    print(f"- {paths.reference_exported_cdt.name}")
    print(f"- {paths.reference_final_qa_cdt.name}")
    print(f"- {paths.reference_final_qa_ddf.name}")
    print(f"- {paths.reference_final_qa_schema.name}")
    print("")
    discovered_sources, discovery_issues = discover_csv_sources(paths, config)
    print("CSV INPUT FILES")
    if discovered_sources:
        for source in discovered_sources:
            print(f"- {source.path.name} [{source.kind}]")
    else:
        print("- No active CSV files discovered.")
    if discovery_issues:
        for issue in discovery_issues:
            print(f"- Discovery issue: {issue}")
    print("")
    print("ALLOWED OUTPUT FILES")
    for name in config["artifacts"]["allowed_output_files"]:
        print(f"- {name}")
    print("")
    print("REFERENCE CDT SCHEMA")
    print(f"- Sample file: {schema['sample_file']}")
    print(f"- Delimiter: {schema['delimiter']}")
    print(f"- Category count: {schema['counts']['category_id_count']}")
    print(f"- Field count: {schema['counts']['field_count']}")
    print(f"- Record count at capture: {schema['counts']['record_count_at_capture']}")
    print("")


def print_cdt_structure_inference(paths: WorkspacePaths, schema: dict) -> None:
    target_cdt = get_analysis_cdt_path(paths)
    inferred = infer_cdt_structure(target_cdt, schema["delimiter"])
    print("INFERRED CDT STRUCTURE")
    print(f"- Sample file: {inferred['sample_file']}")
    print(f"- Line count: {inferred['line_count']}")
    print(f"- Category id count: {inferred['category_id_count']}")
    print(f"- Header field count: {inferred['header_field_count']}")
    print(f"- Record count: {inferred['record_count']}")
    print(f"- Record field counts found: {inferred['record_field_counts_unique']}")
    print("")


def run_preflight(paths: WorkspacePaths, config: dict, schema: dict) -> int:
    print(standard_workflow_text())
    print_workspace_summary(paths, config, schema)
    print_cdt_structure_inference(paths, schema)

    issues: list[str] = []
    issues.extend(validate_config_structure(config))
    issues.extend(validate_config_logic(config))
    issues.extend(validate_schema_file(schema))
    issues.extend(validate_workspace(paths, config, schema))
    if issues:
        print("PREFLIGHT RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("PREFLIGHT RESULT: PASS")
    print("The workspace structure follows the current standard workflow rules.")
    print("No CDT/DDF generation is performed in this phase.")
    return 0


def run_analyse_mapping(paths: WorkspacePaths, config: dict, schema: dict) -> int:
    issues: list[str] = []
    issues.extend(validate_config_structure(config))
    issues.extend(validate_config_logic(config))
    issues.extend(validate_schema_file(schema))
    issues.extend(validate_workspace(paths, config, schema))
    if issues:
        print("ANALYSE-MAPPING RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(standard_workflow_text())
    compliance_issues = print_mapping_analysis(paths, config, schema)
    if compliance_issues:
        print("ANALYSE-MAPPING RESULT: FAIL")
        for issue in compliance_issues:
            print(f"- {issue}")
        print("The CSV-to-CDT relationship was analysed against the current rule set and mismatches were found.")
        print("No CDT/DDF generation is performed in this phase.")
        return 1

    print("ANALYSE-MAPPING RESULT: PASS")
    print("The CSV-to-CDT relationship matches the current rule set.")
    print("No CDT/DDF generation is performed in this phase.")
    return 0


def run_generate_cdt(paths: WorkspacePaths, config: dict, schema: dict) -> int:
    issues: list[str] = []
    issues.extend(validate_config_structure(config))
    issues.extend(validate_config_logic(config))
    issues.extend(validate_schema_file(schema))
    issues.extend(validate_workspace(paths, config, schema))
    issues.extend(validate_csv_inputs_against_material_rules(paths, config))
    if issues:
        print("GENERATE-CDT RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(standard_workflow_text())
    generated_records = generate_material_records(paths, config, schema)
    generation_summary = build_generation_summary(generated_records)
    output_path = write_generated_cdt(paths, schema, generated_records)
    generated_structure = infer_cdt_structure(output_path, schema["delimiter"])
    structure_issues = compare_cdt_structure_to_schema(generated_structure, schema)
    compliance_issues = print_mapping_analysis(paths, config, schema)
    print_generation_summary(generation_summary, output_path)

    if structure_issues or compliance_issues:
        print("GENERATE-CDT RESULT: FAIL")
        for issue in structure_issues:
            print(f"- {issue}")
        for issue in compliance_issues:
            print(f"- {issue}")
        print(f"Generated CDT path: {output_path}")
        print("The CDT file was written but does not fully comply with the current rule set.")
        return 1

    print("GENERATE-CDT RESULT: PASS")
    print(f"Generated CDT path: {output_path}")
    print("The CDT file was generated from CSV using the current rule set and passed schema/rule checks.")
    return 0


def run_generate_ddf(paths: WorkspacePaths, config: dict, schema: dict) -> int:
    issues: list[str] = []
    issues.extend(validate_config_structure(config))
    issues.extend(validate_config_logic(config))
    issues.extend(validate_schema_file(schema))
    issues.extend(validate_workspace(paths, config, schema))
    issues.extend(validate_csv_inputs_against_material_rules(paths, config))
    if issues:
        print("GENERATE-DDF RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(standard_workflow_text())
    generated_records = generate_material_records(paths, config, schema)
    generation_summary = build_generation_summary(generated_records)
    output_cdt_path = write_generated_cdt(paths, schema, generated_records)
    generated_structure = infer_cdt_structure(output_cdt_path, schema["delimiter"])
    structure_issues = compare_cdt_structure_to_schema(generated_structure, schema)
    compliance_issues = print_mapping_analysis(paths, config, schema)

    if structure_issues or compliance_issues:
        print_generation_summary(generation_summary, output_cdt_path)
        print("GENERATE-DDF RESULT: FAIL")
        for issue in structure_issues:
            print(f"- {issue}")
        for issue in compliance_issues:
            print(f"- {issue}")
        print(f"Generated CDT path: {output_cdt_path}")
        print("The CDT generation step failed rule/schema checks, so DDF packaging was not completed.")
        return 1

    try:
        output_ddf_path = package_generated_ddf(paths, config)
    except ValueError as error:
        print("GENERATE-DDF RESULT: FAIL")
        print(f"- {error}")
        return 1

    package_issues = validate_generated_ddf_package(paths, config)
    if package_issues:
        print_generation_summary(generation_summary, output_ddf_path)
        print("GENERATE-DDF RESULT: FAIL")
        for issue in package_issues:
            print(f"- {issue}")
        print(f"Generated CDT path: {output_cdt_path}")
        print(f"Generated DDF path: {output_ddf_path}")
        print("The DDF package was written but did not pass package validation.")
        return 1

    print_generation_summary(generation_summary, output_ddf_path)
    print("GENERATE-DDF RESULT: PASS")
    print(f"Generated CDT path: {output_cdt_path}")
    print(f"Generated DDF path: {output_ddf_path}")
    print("The DDF package was generated from CSV, packaged with the reference internal CDT entry name, and passed validation.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate IBST_Materials workspace, analyse rule compliance, and generate rule-based CDT/DDF outputs."
    )
    parser.add_argument(
        "--mode",
        choices=["preflight", "analyse-mapping", "generate-cdt", "generate-ddf"],
        default="preflight",
        help="Supported modes: preflight, analyse-mapping, generate-cdt, and generate-ddf.",
    )
    parser.add_argument(
        "--input-file",
        action="append",
        default=[],
        help="Optional CSV filename inside 02_csv_input to include. Repeat to include multiple files.",
    )
    parser.add_argument(
        "--output-subdir",
        help="Optional subfolder inside 03_output for this run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    config = load_rules_config(root)
    auto_output_subdir = args.output_subdir
    if args.mode in {"generate-cdt", "generate-ddf"} and not auto_output_subdir:
        auto_output_subdir = derive_output_subdir_name(tuple(args.input_file))
    try:
        paths = build_workspace_paths(
            Path(__file__),
            config,
            selected_csv_names=tuple(args.input_file),
            output_subdir=auto_output_subdir,
        )
    except ValueError as error:
        print(f"ARGUMENT ERROR: {error}")
        return 2
    schema = json.loads(paths.reference_final_qa_schema.read_text(encoding="utf-8"))

    if args.mode == "preflight":
        return run_preflight(paths, config, schema)
    if args.mode == "analyse-mapping":
        return run_analyse_mapping(paths, config, schema)
    if args.mode == "generate-cdt":
        return run_generate_cdt(paths, config, schema)
    if args.mode == "generate-ddf":
        return run_generate_ddf(paths, config, schema)

    print(f"Unsupported mode: {args.mode}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
