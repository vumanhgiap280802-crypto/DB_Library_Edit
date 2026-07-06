#!/usr/bin/env python
"""
IBST_Construction_Test - Standard Build Entry Point

This script is the single entry point for the current construction-test workflow.

Current phase:
    Phase 1 - capture exported DesignBuilder construction references
    Phase 2 - analyse reference schema/content for future input design
    Phase 3 - lock CSV-to-CDT mapping rules from real construction data
    Phase 4 - generate CDT from mapped construction CSV input
    Phase 5 - package CDT into DDF

Planned future phases:
    None

Supported modes right now:
    - summary
    - extract-reference
    - analyse-schema
    - analyse-input
    - generate-cdt
    - generate-ddf
    - preflight
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import glob
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, TypedDict, cast
import zipfile


REPEATED_FIELD_PATTERN = re.compile(r"^(?P<base>.+?)\s+(?P<index>\d+)$")
MAX_LAYER_SLOTS = 20
GROUP_PLACEHOLDER_VALUES = {
    "Mat": {"1"},
    "Thick": {"", "0"},
    "BMat": {"1"},
    "PercBridge": {"0"},
    "Bridged": {"0"},
}
IDENTITY_FIELDS = {"Id", "Name", "CategoryId", "Description", "Source"}
AGGREGATE_THERMAL_FIELDS = {
    "U-Value",
    "UValueSurfaceToSurface",
    "RValue",
    "BSRValue",
    "BSUValue",
    "BSUValueSurfaceToSurface",
    "Thickness",
    "NumberLayers",
    "DefinitionMethod",
    "UseUserUValue",
    "UserUValue",
    "GroundFloorUValueCorrected",
    "L5GroundFloorUValueCorrected",
    "FFactor",
    "CFactor",
    "CM",
    "CM2",
}
SURFACE_BOUNDARY_FIELDS = {
    "SRO",
    "SRI",
    "HCO",
    "HCI",
    "RadO",
    "RadI",
    "SolarAbsorptivity",
    "OverrideDefaultHCO",
    "ManualHCO",
    "OverrideDefaultHCI",
    "ManualHCI",
    "InsideTexture",
    "OutsideTexture",
    "Colour",
}
SYSTEM_LIBRARY_FIELDS = {
    "RegionId",
    "IsSystem",
    "Locked",
    "Scratch",
    "HideInLists",
    "LibraryCategory",
    "LibraryConstructionName",
    "URL",
    "LRL",
    "SBEMType",
    "CostPerArea",
    "CostMethod",
    "SimulationAlgorithmOverride",
    "ParamSelected",
}

ConstructionRecord = dict[str, str]
FieldCountPair = tuple[str, int]
FieldVariationPair = tuple[str, list[str]]


class ReferenceSchemaLine(TypedDict, total=False):
    line_number: int | str
    role: str
    count: int
    count_at_capture: int


class ReferenceSchemaCounts(TypedDict):
    line_count_at_capture: int
    category_id_count: int
    field_count: int
    record_count_at_capture: int


class ReferenceSchema(TypedDict):
    sample_file: str
    schema_type: str
    delimiter: str
    line_structure: list[ReferenceSchemaLine]
    counts: ReferenceSchemaCounts
    category_ids: list[str]
    fields: list[str]
    notes: list[str]


class InferredCdtStructure(TypedDict):
    line_count: int
    category_id_count: int
    field_count: int
    record_count: int
    record_field_counts_unique: list[int]
    category_ids: list[str]
    fields: list[str]
    sample_file: str


class NonRepeatedFieldGroups(TypedDict):
    identity: list[str]
    aggregate_thermal: list[str]
    surface_boundary: list[str]
    system_library: list[str]
    advanced_optional: list[str]


class RepeatedGroupSummary(TypedDict):
    base: str
    slot_count: int
    varying_slots: list[int]
    constant_placeholder_slots: list[int]
    constant_value_slots: list[int]
    always_empty_slots: list[int]
    sparse_slots: list[int]


class FieldPopulationSummary(TypedDict):
    always_non_empty: list[str]
    always_empty: list[str]
    sometimes_non_empty: list[FieldCountPair]


class FieldVariationSummary(TypedDict):
    constant_fields: list[tuple[str, str]]
    varying_fields: list[FieldVariationPair]


class RecordLayerSummary(TypedDict):
    name: str
    category_id: str
    number_layers: int
    active_layers: list[str]
    overflow_slots: list[int]


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
    reference_exported_schema: Path
    generated_cdt: Path
    generated_ddf: Path


@dataclass(frozen=True)
class CsvLayerInput:
    source_file: Path
    row_number: int
    construction_code: str
    construction_name: str
    category_text: str
    layer_order: int
    material_name: str
    thickness_override_m: str
    notes: str


@dataclass(frozen=True)
class MaterialReference:
    name: str
    source: str
    material_id: str = ""
    default_thickness: str = ""


@dataclass(frozen=True)
class MaterialCatalog:
    source: str
    category_ids: list[str]
    fields: list[str]
    records: list[ConstructionRecord]
    records_by_name: dict[str, ConstructionRecord]


@dataclass(frozen=True)
class ResolvedConstructionLayer:
    slot_index: int
    material_name: str
    material_id: str
    thickness_decimal: Decimal
    thickness_source: str


@dataclass(frozen=True)
class GeneratedConstructionPlan:
    construction_code: str
    construction_name: str
    category_text: str
    category_id: str
    description: str
    seed_name: str
    layers: list[ResolvedConstructionLayer]
    total_thickness: Decimal


@dataclass(frozen=True)
class GeneratedOutputArtifacts:
    schema: ReferenceSchema
    plans: list[GeneratedConstructionPlan]
    generated_records: list[ConstructionRecord]
    material_id_catalog: MaterialCatalog
    inferred_structure: InferredCdtStructure
    output_dir: Path
    output_cdt_path: Path
    output_ddf_path: Path
    replaced_existing_cdt: bool


def load_rules_config(root: Path) -> dict:
    return json.loads((root / "workspace_rules.json").read_text(encoding="utf-8"))


def build_workspace_paths(script_path: Path, config: dict) -> WorkspacePaths:
    root = script_path.resolve().parent.parent
    paths_cfg = config["paths"]
    ref_cfg = config["reference_files"]
    allowed_outputs = config["artifacts"]["allowed_output_files"]
    generated_cdt_name = next(name for name in allowed_outputs if Path(name).suffix.lower() == ".cdt")
    generated_ddf_name = next(name for name in allowed_outputs if Path(name).suffix.lower() == ".ddf")

    return WorkspacePaths(
        root=root,
        rules_config=root / "workspace_rules.json",
        designbuilder_format=root / paths_cfg["reference"],
        csv_input=root / paths_cfg["input"],
        output=root / paths_cfg["output"],
        scripts=root / paths_cfg["scripts"],
        archive=root / paths_cfg["archive"],
        reference_ddf=root / paths_cfg["reference"] / ref_cfg["reference_ddf"],
        reference_exported_cdt=root / paths_cfg["reference"] / ref_cfg["reference_exported_cdt"],
        reference_exported_schema=root / paths_cfg["reference"] / ref_cfg["reference_exported_schema"],
        generated_cdt=root / paths_cfg["output"] / generated_cdt_name,
        generated_ddf=root / paths_cfg["output"] / generated_ddf_name,
    )


def standard_workflow_text() -> str:
    return (
        "STANDARD WORKFLOW\n"
        "1. Use DesignBuilder-exported DDF/CDT files in 01_designbuilder_format as reference only.\n"
        "2. Extract the construction CDT from the reference DDF before defining mapping rules.\n"
        "3. Capture a schema JSON directly from the extracted reference CDT.\n"
        "4. Analyse the extracted CDT/schema before designing CSV input structure.\n"
        "5. Place editable CSV inputs in 02_csv_input.\n"
        "6. Run this script from 04_scripts as the single automation entry point.\n"
    )


def discover_csv_files(
    paths: WorkspacePaths,
    config: dict,
    selected_csv_names: tuple[str, ...] = (),
) -> tuple[list[Path], list[str]]:
    input_cfg = config["input_files"]
    extension = input_cfg["file_extension"]
    ignore_prefixes = tuple(input_cfg["ignore_filename_prefixes"])

    if not paths.csv_input.exists():
        return [], [f"Missing input directory: {paths.csv_input}"]

    files = [
        path
        for path in paths.csv_input.iterdir()
        if path.is_file() and path.suffix.lower() == extension.lower() and not path.name.startswith(ignore_prefixes)
    ]
    files.sort(key=lambda path: path.name.lower())
    if not selected_csv_names:
        return files, []

    normalized_selected_names = {
        name if name.lower().endswith(extension.lower()) else f"{name}{extension}"
        for name in selected_csv_names
    }
    selected_files = [path for path in files if path.name in normalized_selected_names]
    selected_file_names = {path.name for path in selected_files}
    missing_files = sorted(normalized_selected_names - selected_file_names)
    issues = [f"Requested CSV input not found or inactive: {name}" for name in missing_files]
    return selected_files, issues


def _require_dict_keys(
    container: Mapping[str, object],
    container_name: str,
    keys: list[str],
    issues: list[str],
) -> None:
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
            "construction_csv_mapping",
            "artifacts",
            "behavior",
            "ddf_cdt",
            "constructions",
            "future_pipeline",
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
    if "reference_files" in config:
        _require_dict_keys(
            config["reference_files"],
            "reference_files",
            [
                "reference_ddf",
                "reference_exported_cdt",
                "reference_exported_schema",
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
                "allow_multiple_files",
            ],
            issues,
        )
    if "construction_csv_mapping" in config:
        _require_dict_keys(
            config["construction_csv_mapping"],
            "construction_csv_mapping",
            [
                "layout",
                "required_columns",
                "group_by_columns",
                "sort_by_column",
                "name_column",
                "code_column",
                "category_column",
                "material_name_column",
                "thickness_override_column",
                "notes_column",
                "category_text_to_id",
                "definition_method_fixed_value",
                "number_layers_from_group_size",
                "thickness_from_sum_of_layer_thicknesses",
                "description_from_first_non_empty_note",
                "seed_records_by_category",
                "material_lookup",
            ],
            issues,
        )
        if "material_lookup" in config["construction_csv_mapping"]:
            _require_dict_keys(
                config["construction_csv_mapping"]["material_lookup"],
                "construction_csv_mapping.material_lookup",
                ["id_priority", "default_thickness_priority"],
                issues,
            )
    if "artifacts" in config:
        _require_dict_keys(
            config["artifacts"],
            "artifacts",
            [
                "final_import_artifact",
                "editable_intermediate_artifact",
                "csv_is_not_final_import_artifact",
                "per_run_output_must_use_new_subfolder",
                "output_subfolder_name_source",
                "output_subfolder_must_prevent_overwrite_between_runs",
                "allowed_output_files",
            ],
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
                "reference_package_materials_entry_name",
                "package_entry_name_must_match_reference_ddf",
                "edit_external_data_on_cdt_then_repackage_to_ddf",
                "package_ddf_by_zipping_required_cdt_files_then_renaming_extension",
                "designbuilder_exported_csv_cannot_be_imported_back_directly",
                "must_compare_with_designbuilder_exported_reference_before_packaging",
            ],
            issues,
        )
    if "constructions" in config:
        _require_dict_keys(
            config["constructions"],
            "constructions",
            [
                "is_component_data",
                "requires_designbuilder_exported_reference",
                "depends_on_material_references",
                "must_lock_mapping_after_real_reference_capture",
                "allow_generator_before_reference_capture",
                "notes",
            ],
            issues,
        )
    if "future_pipeline" in config:
        _require_dict_keys(
            config["future_pipeline"],
            "future_pipeline",
            [
                "reference_capture_complete",
                "mapping_rules_complete",
                "generator_implemented",
                "package_generator_implemented",
                "current_supported_modes",
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


def validate_config_logic(config: dict) -> list[str]:
    issues: list[str] = []
    artifacts = config["artifacts"]
    behavior = config["behavior"]
    csv_mapping = config["construction_csv_mapping"]
    ddf_cdt = config["ddf_cdt"]
    future_pipeline = config["future_pipeline"]
    constructions = config["constructions"]

    if artifacts["final_import_artifact"] != ".ddf":
        issues.append("artifacts.final_import_artifact must be '.ddf'.")
    if artifacts["editable_intermediate_artifact"] != ".cdt":
        issues.append("artifacts.editable_intermediate_artifact must be '.cdt'.")
    if behavior["csv_is_final_artifact"] == artifacts["csv_is_not_final_import_artifact"]:
        issues.append("CSV artifact flags are logically inconsistent.")
    if not behavior["ddf_is_final_artifact"]:
        issues.append("behavior.ddf_is_final_artifact must be true.")
    if not behavior["cdt_is_editable_intermediate"]:
        issues.append("behavior.cdt_is_editable_intermediate must be true.")
    if artifacts["per_run_output_must_use_new_subfolder"]:
        issues.append(
            "artifacts.per_run_output_must_use_new_subfolder must be false so same-request same-data runs reuse one output folder."
        )
    if artifacts["output_subfolder_must_prevent_overwrite_between_runs"]:
        issues.append(
            "artifacts.output_subfolder_must_prevent_overwrite_between_runs must be false so error-fix reruns can replace prior output."
        )
    if artifacts["output_subfolder_name_source"] != "input_data_name_stable_for_same_request_replace":
        issues.append(
            "artifacts.output_subfolder_name_source must be 'input_data_name_stable_for_same_request_replace'."
        )
    if csv_mapping["layout"] != "long_by_layer":
        issues.append("construction_csv_mapping.layout must be 'long_by_layer'.")
    if csv_mapping["definition_method_fixed_value"] != "1-Layers":
        issues.append("construction_csv_mapping.definition_method_fixed_value must be '1-Layers'.")
    if not csv_mapping["number_layers_from_group_size"]:
        issues.append("construction_csv_mapping.number_layers_from_group_size must be true.")
    if not csv_mapping["thickness_from_sum_of_layer_thicknesses"]:
        issues.append("construction_csv_mapping.thickness_from_sum_of_layer_thicknesses must be true.")
    if not csv_mapping["description_from_first_non_empty_note"]:
        issues.append("construction_csv_mapping.description_from_first_non_empty_note must be true.")
    if not ddf_cdt["package_entry_name_must_match_reference_ddf"]:
        issues.append("ddf_cdt.package_entry_name_must_match_reference_ddf must be true.")
    if not ddf_cdt["reference_package_cdt_entry_name"].lower().endswith(".cdt"):
        issues.append("ddf_cdt.reference_package_cdt_entry_name must end with '.cdt'.")
    if not ddf_cdt["reference_package_materials_entry_name"].lower().endswith(".cdt"):
        issues.append("ddf_cdt.reference_package_materials_entry_name must end with '.cdt'.")
    if constructions["allow_generator_before_reference_capture"]:
        issues.append("constructions.allow_generator_before_reference_capture must be false at this stage.")
    for mode_name in ("summary", "extract-reference", "analyse-schema", "analyse-input", "generate-cdt", "generate-ddf", "preflight"):
        if mode_name not in future_pipeline["current_supported_modes"]:
            issues.append(f"future_pipeline.current_supported_modes must include '{mode_name}'.")
    if not future_pipeline["generator_implemented"]:
        issues.append("future_pipeline.generator_implemented must be true once generate-cdt is implemented.")
    if not future_pipeline["package_generator_implemented"]:
        issues.append("future_pipeline.package_generator_implemented must be true once generate-ddf is implemented.")

    return issues


def validate_schema_file(schema: ReferenceSchema) -> list[str]:
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


def decode_loose(value: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def _read_non_empty_lines_bytes(file_path: Path) -> list[bytes]:
    return [line.rstrip(b"\r\n") for line in file_path.read_bytes().splitlines() if line.strip()]


def _split_cdt_line_bytes(line: bytes, delimiter: str) -> list[str]:
    delimiter_bytes = delimiter.encode("ascii")
    parts = line.split(delimiter_bytes)
    if parts and parts[0] == b"":
        parts = parts[1:]
    return [decode_loose(part.rstrip()) for part in parts]


def infer_cdt_structure(cdt_path: Path, delimiter: str) -> InferredCdtStructure:
    lines = _read_non_empty_lines_bytes(cdt_path)
    category_ids = _split_cdt_line_bytes(lines[0], delimiter)
    header_fields = _split_cdt_line_bytes(lines[1], delimiter)
    record_lines = lines[2:]
    record_field_counts = [len(_split_cdt_line_bytes(line, delimiter)) for line in record_lines]

    return {
        "line_count": len(lines),
        "category_id_count": len(category_ids),
        "field_count": len(header_fields),
        "record_count": len(record_lines),
        "record_field_counts_unique": sorted(set(record_field_counts)),
        "category_ids": category_ids,
        "fields": header_fields,
        "sample_file": cdt_path.name,
    }


def build_schema_from_cdt(cdt_path: Path, delimiter: str) -> ReferenceSchema:
    inferred = infer_cdt_structure(cdt_path, delimiter)
    return {
        "sample_file": inferred["sample_file"],
        "schema_type": "designbuilder_constructions_cdt",
        "delimiter": delimiter,
        "line_structure": [
            {
                "line_number": 1,
                "role": "category_ids",
                "count": inferred["category_id_count"],
            },
            {
                "line_number": 2,
                "role": "header",
                "count": inferred["field_count"],
            },
            {
                "line_number": "3..n",
                "role": "records",
                "count_at_capture": inferred["record_count"],
            },
        ],
        "counts": {
            "line_count_at_capture": inferred["line_count"],
            "category_id_count": inferred["category_id_count"],
            "field_count": inferred["field_count"],
            "record_count_at_capture": inferred["record_count"],
        },
        "category_ids": inferred["category_ids"],
        "fields": inferred["fields"],
        "notes": [
            f"This schema is captured directly from the sample file {inferred['sample_file']}.",
            f"Each record line is expected to preserve all {inferred['field_count']} fields, including empty values.",
            "The category_ids line and header line are part of the file structure and must be preserved.",
            "This schema is intended as the reference structure for future CSV-to-CDT generation.",
        ],
    }


def load_cdt_payload_from_lines(lines: list[bytes], delimiter: str) -> tuple[list[str], list[str], list[ConstructionRecord]]:
    if len(lines) < 2:
        raise ValueError("CDT content must contain at least category and header lines.")
    category_ids = _split_cdt_line_bytes(lines[0], delimiter)
    header_fields = _split_cdt_line_bytes(lines[1], delimiter)
    records: list[ConstructionRecord] = []
    for line in lines[2:]:
        parts = _split_cdt_line_bytes(line, delimiter)
        record = {
            field: parts[index] if index < len(parts) else ""
            for index, field in enumerate(header_fields)
        }
        records.append(record)
    return category_ids, header_fields, records


def load_cdt_records(cdt_path: Path, delimiter: str) -> tuple[list[str], list[ConstructionRecord]]:
    _, header_fields, records = load_cdt_payload_from_lines(_read_non_empty_lines_bytes(cdt_path), delimiter)
    return header_fields, records


def compare_cdt_structure_to_schema(inferred: InferredCdtStructure, schema: ReferenceSchema) -> list[str]:
    issues: list[str] = []
    schema_counts = schema["counts"]

    if inferred["category_id_count"] != schema_counts["category_id_count"]:
        issues.append(
            f"CDT category count mismatch: inferred {inferred['category_id_count']} vs schema {schema_counts['category_id_count']}."
        )
    if inferred["field_count"] != schema_counts["field_count"]:
        issues.append(
            f"CDT header field count mismatch: inferred {inferred['field_count']} vs schema {schema_counts['field_count']}."
        )
    if inferred["line_count"] < 3:
        issues.append("CDT must contain at least category/header/record lines.")
    if inferred["record_field_counts_unique"] != [schema_counts["field_count"]]:
        issues.append("CDT record field counts are inconsistent with schema field count.")
    if inferred["category_ids"] != schema["category_ids"]:
        issues.append("CDT category id line does not match schema category_ids.")
    if inferred["fields"] != schema["fields"]:
        issues.append("CDT header fields do not match schema fields.")

    return issues


def inspect_reference_ddf(paths: WorkspacePaths, config: dict) -> tuple[list[str], list[str]]:
    info: list[str] = []
    issues: list[str] = []

    if not paths.reference_ddf.is_file():
        info.append("Reference DDF not present yet.")
        return info, issues

    try:
        with zipfile.ZipFile(paths.reference_ddf) as archive:
            entry_names = archive.namelist()
    except zipfile.BadZipFile:
        issues.append("Reference DDF is not readable as a zip-compatible package.")
        return info, issues

    cdt_entries = sorted(name for name in entry_names if name.lower().endswith(".cdt"))
    if not cdt_entries:
        issues.append("Reference DDF does not contain any CDT entry.")
        return info, issues

    expected_entry = config["ddf_cdt"]["reference_package_cdt_entry_name"]
    if expected_entry not in cdt_entries:
        issues.append(
            f"Reference DDF does not contain configured package entry name '{expected_entry}'."
        )

    info.append(f"Reference DDF CDT entries: {', '.join(cdt_entries)}")
    return info, issues


def write_bytes_if_changed(path: Path, data: bytes) -> bool:
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def write_text_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def extract_reference_artifacts(paths: WorkspacePaths, config: dict) -> tuple[ReferenceSchema, bool, bool]:
    if not paths.reference_ddf.is_file():
        raise FileNotFoundError(f"Missing reference DDF: {paths.reference_ddf}")

    entry_name = config["ddf_cdt"]["reference_package_cdt_entry_name"]
    with zipfile.ZipFile(paths.reference_ddf) as archive:
        cdt_bytes = archive.read(entry_name)

    cdt_changed = write_bytes_if_changed(paths.reference_exported_cdt, cdt_bytes)
    schema = build_schema_from_cdt(paths.reference_exported_cdt, config["ddf_cdt"]["cdt_field_delimiter"])
    schema_text = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    schema_changed = write_text_if_changed(paths.reference_exported_schema, schema_text)
    return schema, cdt_changed, schema_changed


def detect_repeated_field_groups(fields: list[str]) -> tuple[dict[str, list[int]], list[str]]:
    groups: dict[str, list[int]] = defaultdict(list)
    non_repeated: list[str] = []

    for field in fields:
        match = REPEATED_FIELD_PATTERN.match(field)
        if match:
            groups[match.group("base")].append(int(match.group("index")))
        else:
            non_repeated.append(field)

    sorted_groups: dict[str, list[int]] = {
        base: sorted(indices)
        for base, indices in sorted(groups.items(), key=lambda item: item[0].lower())
    }
    return sorted_groups, non_repeated


def classify_non_repeated_fields(fields: list[str]) -> NonRepeatedFieldGroups:
    grouped: NonRepeatedFieldGroups = {
        "identity": [],
        "aggregate_thermal": [],
        "surface_boundary": [],
        "system_library": [],
        "advanced_optional": [],
    }

    for field in fields:
        if field in IDENTITY_FIELDS:
            grouped["identity"].append(field)
        elif field in AGGREGATE_THERMAL_FIELDS:
            grouped["aggregate_thermal"].append(field)
        elif field in SURFACE_BOUNDARY_FIELDS:
            grouped["surface_boundary"].append(field)
        elif (
            field in SYSTEM_LIBRARY_FIELDS
            or field.startswith("Library")
            or field.startswith("Inference")
        ):
            grouped["system_library"].append(field)
        elif (
            field.startswith("InternalSource")
            or field.startswith("RT")
            or field.startswith("PV")
            or field in {"InvolvesMetalCladding", "IsInternalSource", "CFactor", "FFactor"}
        ):
            grouped["advanced_optional"].append(field)
        else:
            grouped["advanced_optional"].append(field)

    return grouped


def ordered_non_repeated_field_groups(grouped: NonRepeatedFieldGroups) -> list[tuple[str, list[str]]]:
    return [
        ("identity", grouped["identity"]),
        ("aggregate_thermal", grouped["aggregate_thermal"]),
        ("surface_boundary", grouped["surface_boundary"]),
        ("system_library", grouped["system_library"]),
        ("advanced_optional", grouped["advanced_optional"]),
    ]


def parse_int_or_none(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def compress_indices(indices: list[int]) -> str:
    if not indices:
        return "-"
    sorted_indices = sorted(indices)
    ranges: list[str] = []
    start = sorted_indices[0]
    end = sorted_indices[0]
    for index in sorted_indices[1:]:
        if index == end + 1:
            end = index
            continue
        ranges.append(f"{start}-{end}" if start != end else str(start))
        start = end = index
    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ", ".join(ranges)


def summarize_repeated_group(
    records: list[ConstructionRecord],
    base: str,
    indices: list[int],
) -> RepeatedGroupSummary:
    placeholder_values = GROUP_PLACEHOLDER_VALUES.get(base, {"", "0"})
    varying_slots: list[int] = []
    constant_placeholder_slots: list[int] = []
    constant_value_slots: list[int] = []
    always_empty_slots: list[int] = []
    sparse_slots: list[int] = []

    for index in indices:
        field_name = f"{base} {index}"
        values = [record.get(field_name, "").strip() for record in records]
        non_empty_values = [value for value in values if value != ""]
        unique_values = sorted(set(values))

        if not non_empty_values:
            always_empty_slots.append(index)
            continue

        if len(unique_values) == 1:
            only_value = unique_values[0]
            if only_value in placeholder_values:
                constant_placeholder_slots.append(index)
            else:
                constant_value_slots.append(index)
            continue

        meaningful_values = {value for value in unique_values if value not in placeholder_values and value != ""}
        if meaningful_values and len(non_empty_values) != len(records):
            sparse_slots.append(index)
        else:
            varying_slots.append(index)

    return {
        "base": base,
        "slot_count": len(indices),
        "varying_slots": varying_slots,
        "constant_placeholder_slots": constant_placeholder_slots,
        "constant_value_slots": constant_value_slots,
        "always_empty_slots": always_empty_slots,
        "sparse_slots": sparse_slots,
    }


def summarize_field_population(
    fields: list[str],
    records: list[ConstructionRecord],
) -> FieldPopulationSummary:
    always_non_empty: list[str] = []
    always_empty: list[str] = []
    sometimes_non_empty: list[tuple[str, int]] = []

    for field in fields:
        non_empty_count = sum(1 for record in records if record.get(field, "").strip())
        if non_empty_count == len(records):
            always_non_empty.append(field)
        elif non_empty_count == 0:
            always_empty.append(field)
        else:
            sometimes_non_empty.append((field, non_empty_count))

    return {
        "always_non_empty": always_non_empty,
        "always_empty": always_empty,
        "sometimes_non_empty": sometimes_non_empty,
    }


def summarize_field_variation(
    fields: list[str],
    records: list[ConstructionRecord],
) -> FieldVariationSummary:
    constant_fields: list[tuple[str, str]] = []
    varying_fields: list[FieldVariationPair] = []

    for field in fields:
        values = [record.get(field, "") for record in records]
        unique_values = sorted(set(values))
        if len(unique_values) == 1:
            constant_fields.append((field, unique_values[0]))
        else:
            varying_fields.append((field, unique_values))

    return {
        "constant_fields": constant_fields,
        "varying_fields": varying_fields,
    }


def find_linked_field_clusters(fields: list[str], records: list[ConstructionRecord]) -> list[list[str]]:
    signatures: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for field in fields:
        signature = tuple(record.get(field, "") for record in records)
        if len(set(signature)) > 1:
            signatures[signature].append(field)
    return sorted(
        [sorted(cluster) for cluster in signatures.values() if len(cluster) > 1],
        key=lambda cluster: (len(cluster), cluster),
        reverse=True,
    )


def summarize_record_layers(records: list[ConstructionRecord]) -> list[RecordLayerSummary]:
    summaries: list[RecordLayerSummary] = []
    for record in records:
        number_layers = parse_int_or_none(record.get("NumberLayers", "")) or 0
        active_layers = [
            f"{index}:{record.get(f'Mat {index}', '').strip()}@{record.get(f'Thick {index}', '').strip()}"
            for index in range(1, number_layers + 1)
        ]

        overflow_slots: list[int] = []
        for index in range(number_layers + 1, 21):
            mat_value = record.get(f"Mat {index}", "").strip()
            thick_value = record.get(f"Thick {index}", "").strip()
            if mat_value not in {"", "1"} or thick_value not in {"", "0"}:
                overflow_slots.append(index)

        summaries.append(
            {
                "name": record.get("Name", ""),
                "category_id": record.get("CategoryId", ""),
                "number_layers": number_layers,
                "active_layers": active_layers,
                "overflow_slots": overflow_slots,
            }
        )
    return summaries


def build_input_preparation_guidance(records: list[ConstructionRecord]) -> list[str]:
    record_layers = summarize_record_layers(records)
    guidance = [
        "Dung mot dong input cho moi construction, voi cac cot loi gom Name, CategoryId, va NumberLayers.",
        "Du lieu layer phai duoc model hoa theo cap Mat i / Thick i cho i = 1..NumberLayers.",
        "Khong suy ra layer dang dung chi tu non-empty fields, vi sample cho thay slot vuot NumberLayers van co placeholder hoac gia tri seed.",
        "Nhom bridge fields BMat i / PercBridge i / Bridged i nen duoc xem la optional/advanced cho den khi co use case that.",
        "Id, IsSystem, RegionId, Locked, Scratch, va cac field library/system nen duoc generator hoac seed quan ly, khong nen bat user nhap tay ngay tu dau.",
        "Can xac minh bang import test xem cac aggregate thermal fields nhu U-Value, RValue, Thickness, BSUValue, BSRValue co phai duoc tinh lai tu layers hay phai giu dung theo CDT.",
    ]

    if any(summary["overflow_slots"] for summary in record_layers):
        guidance.append(
            "Sample hien tai co non-default values o mot so slot vuot NumberLayers; can uu tien rule active-layer theo NumberLayers, khong theo do dai chuoi Mat/Thick."
        )

    return guidance


def parse_positive_decimal_or_none(value: str) -> Decimal | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    if parsed <= 0:
        return None
    return parsed


def resolve_source_glob(root: Path, pattern: str) -> list[Path]:
    resolved_pattern = str((root / pattern).resolve())
    matches = [Path(path) for path in glob.glob(resolved_pattern)]
    return sorted(matches, key=lambda path: (path.stat().st_mtime, str(path)), reverse=True)


def build_material_catalog(
    source_label: str,
    category_ids: list[str],
    fields: list[str],
    records: list[ConstructionRecord],
) -> MaterialCatalog:
    records_by_name: dict[str, ConstructionRecord] = {}
    ordered_records: list[ConstructionRecord] = []
    for record in records:
        name = record.get("Name", "").strip()
        if not name or name in records_by_name:
            continue
        normalized = {field: record.get(field, "").strip() for field in fields}
        records_by_name[name] = normalized
        ordered_records.append(normalized)
    return MaterialCatalog(
        source=source_label,
        category_ids=category_ids,
        fields=fields,
        records=ordered_records,
        records_by_name=records_by_name,
    )


def load_material_catalog_from_cdt_path(cdt_path: Path, source_label: str) -> MaterialCatalog:
    category_ids, fields, records = load_cdt_payload_from_lines(_read_non_empty_lines_bytes(cdt_path), "#")
    return build_material_catalog(source_label, category_ids, fields, records)


def load_material_catalog_from_ddf_entry(ddf_path: Path, entry_name: str, source_label: str) -> MaterialCatalog:
    with zipfile.ZipFile(ddf_path) as archive:
        cdt_bytes = archive.read(entry_name)
    lines = [line.rstrip(b"\r\n") for line in cdt_bytes.splitlines() if line.strip()]
    category_ids, fields, records = load_cdt_payload_from_lines(lines, "#")
    return build_material_catalog(source_label, category_ids, fields, records)


def load_material_records_from_cdt_path(cdt_path: Path, source_label: str) -> dict[str, MaterialReference]:
    catalog = load_material_catalog_from_cdt_path(cdt_path, source_label)
    references: dict[str, MaterialReference] = {}
    for record in catalog.records:
        name = record.get("Name", "").strip()
        if not name:
            continue
        references[name] = MaterialReference(
            name=name,
            source=source_label,
            material_id=record.get("Id", "").strip(),
            default_thickness=record.get("DefaultThickness", "").strip(),
        )
    return references


def load_material_records_from_ddf_entry(ddf_path: Path, entry_name: str, source_label: str) -> dict[str, MaterialReference]:
    catalog = load_material_catalog_from_ddf_entry(ddf_path, entry_name, source_label)
    references: dict[str, MaterialReference] = {}
    for record in catalog.records:
        name = record.get("Name", "").strip()
        if not name:
            continue
        references[name] = MaterialReference(
            name=name,
            source=source_label,
            material_id=record.get("Id", "").strip(),
            default_thickness=record.get("DefaultThickness", "").strip(),
        )
    return references


def load_material_records_from_csv_path(csv_path: Path, source_label: str) -> dict[str, MaterialReference]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        references: dict[str, MaterialReference] = {}
        for row in reader:
            name = (row.get("Name", "") or "").strip()
            if not name:
                continue
            references[name] = MaterialReference(
                name=name,
                source=source_label,
                default_thickness=(row.get("DefaultThickness_m", "") or "").strip(),
            )
    return references


def load_material_id_catalog_candidates(config: dict, paths: WorkspacePaths) -> list[MaterialCatalog]:
    mapping_cfg = config["construction_csv_mapping"]["material_lookup"]
    catalogs: list[MaterialCatalog] = []
    for spec in mapping_cfg["id_priority"]:
        for source_kind, path, entry_name in resolve_material_source_paths(paths.root, spec):
            if source_kind == "ddf_embedded_cdt":
                if not path.is_file():
                    continue
                catalogs.append(
                    load_material_catalog_from_ddf_entry(path, cast(str, entry_name), f"{path.name}::{entry_name}")
                )
            else:
                if not path.is_file() or path.suffix.lower() == ".csv":
                    continue
                catalogs.append(load_material_catalog_from_cdt_path(path, str(path)))
    return catalogs


def select_material_id_catalog(catalogs: list[MaterialCatalog], required_names: set[str]) -> tuple[MaterialCatalog | None, list[str]]:
    issues: list[str] = []
    for catalog in catalogs:
        missing = sorted(required_names - set(catalog.records_by_name))
        if not missing:
            return catalog, issues
        issues.append(
            f"{catalog.source}: missing {len(missing)}/{len(required_names)} required materials "
            f"({', '.join(missing[:5])}{' ...' if len(missing) > 5 else ''})."
        )
    return None, issues


def resolve_material_source_paths(root: Path, spec: str) -> list[tuple[str, Path, str | None]]:
    if "::" in spec:
        path_text, entry_name = spec.split("::", 1)
        path = (root / path_text).resolve()
        return [("ddf_embedded_cdt", path, entry_name)]
    if any(token in spec for token in ("*", "?", "[")):
        paths = resolve_source_glob(root, spec)
        return [("path", path, None) for path in paths]
    return [("path", (root / spec).resolve(), None)]


def load_material_lookup(config: dict, paths: WorkspacePaths) -> tuple[dict[str, MaterialReference], dict[str, MaterialReference]]:
    mapping_cfg = config["construction_csv_mapping"]["material_lookup"]
    id_lookup: dict[str, MaterialReference] = {}
    thickness_lookup: dict[str, MaterialReference] = {}

    for spec in mapping_cfg["id_priority"]:
        for source_kind, path, entry_name in resolve_material_source_paths(paths.root, spec):
            if source_kind == "ddf_embedded_cdt":
                if not path.is_file():
                    continue
                records = load_material_records_from_ddf_entry(path, cast(str, entry_name), f"{path.name}::{entry_name}")
            else:
                if not path.is_file():
                    continue
                records = load_material_records_from_cdt_path(path, str(path))
            for name, reference in records.items():
                if name not in id_lookup and reference.material_id:
                    id_lookup[name] = reference

    for spec in mapping_cfg["default_thickness_priority"]:
        for source_kind, path, entry_name in resolve_material_source_paths(paths.root, spec):
            records: dict[str, MaterialReference] = {}
            if source_kind == "ddf_embedded_cdt":
                if not path.is_file():
                    continue
                records = load_material_records_from_ddf_entry(path, cast(str, entry_name), f"{path.name}::{entry_name}")
            else:
                if not path.is_file():
                    continue
                if path.suffix.lower() == ".csv":
                    records = load_material_records_from_csv_path(path, str(path))
                else:
                    records = load_material_records_from_cdt_path(path, str(path))
            for name, reference in records.items():
                if name not in thickness_lookup and reference.default_thickness.strip():
                    thickness_lookup[name] = reference

    return id_lookup, thickness_lookup


def collapse_text(value: str) -> str:
    return " ".join(value.replace("#", " ").split())


def load_construction_csv_rows(
    paths: WorkspacePaths,
    config: dict,
    selected_csv_names: tuple[str, ...] = (),
) -> tuple[list[CsvLayerInput], list[str]]:
    csv_mapping = config["construction_csv_mapping"]
    required_columns = csv_mapping["required_columns"]
    csv_files, discovery_issues = discover_csv_files(paths, config, selected_csv_names)
    issues: list[str] = list(discovery_issues)
    rows: list[CsvLayerInput] = []

    for csv_path in csv_files:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            fieldnames = [field.strip() for field in (reader.fieldnames or []) if field]
            missing_columns = [column for column in required_columns if column not in fieldnames]
            if missing_columns:
                issues.append(f"{csv_path.name}: missing required columns: {', '.join(missing_columns)}")
                continue

            for row_index, raw_row in enumerate(reader, start=2):
                cleaned_row = {key.strip(): (value or "").strip() for key, value in raw_row.items() if key}
                code = cleaned_row[csv_mapping["code_column"]]
                name = cleaned_row[csv_mapping["name_column"]]
                category_text = cleaned_row[csv_mapping["category_column"]]
                material_name = cleaned_row[csv_mapping["material_name_column"]]
                thickness_override = cleaned_row[csv_mapping["thickness_override_column"]]
                notes = collapse_text(cleaned_row[csv_mapping["notes_column"]])
                layer_order_text = cleaned_row[csv_mapping["sort_by_column"]]
                layer_order = parse_int_or_none(layer_order_text)

                if not code or not name or not category_text or not material_name:
                    issues.append(f"{csv_path.name}:{row_index} missing required value in group/name/category/material columns.")
                    continue
                if layer_order is None or layer_order <= 0:
                    issues.append(f"{csv_path.name}:{row_index} invalid layer_order '{layer_order_text}'.")
                    continue
                if thickness_override and parse_positive_decimal_or_none(thickness_override) is None:
                    issues.append(f"{csv_path.name}:{row_index} invalid thickness_override_m '{thickness_override}'.")
                    continue

                rows.append(
                    CsvLayerInput(
                        source_file=csv_path,
                        row_number=row_index,
                        construction_code=code,
                        construction_name=name,
                        category_text=category_text,
                        layer_order=layer_order,
                        material_name=material_name,
                        thickness_override_m=thickness_override,
                        notes=notes,
                    )
                )

    return rows, issues


def group_construction_rows(rows: list[CsvLayerInput]) -> dict[tuple[str, str, str], list[CsvLayerInput]]:
    grouped: dict[tuple[str, str, str], list[CsvLayerInput]] = defaultdict(list)
    for row in rows:
        key = (row.construction_code, row.construction_name, row.category_text)
        grouped[key].append(row)
    for key in grouped:
        grouped[key].sort(key=lambda row: (row.layer_order, row.row_number))
    return dict(sorted(grouped.items(), key=lambda item: item[0]))


def sanitize_output_stem(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return sanitized or "construction-input"


def derive_output_subdir_name(csv_files: list[Path]) -> str:
    unique_stems = list(dict.fromkeys(sanitize_output_stem(path.stem) for path in csv_files))
    base_name = "__".join(unique_stems) or "construction-input"
    if len(base_name) > 80:
        base_name = base_name[:80].rstrip("-")
    return base_name


def resolve_generated_output_dir(paths: WorkspacePaths, csv_files: list[Path]) -> Path:
    return paths.output / derive_output_subdir_name(csv_files)


def format_decimal_for_cdt(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if not text or text == "-0":
        text = "0"
    if text.startswith("0.") and text != "0":
        return text[1:]
    if text.startswith("-0."):
        return f"-{text[2:]}"
    return text


def serialize_cdt_line(values: list[str]) -> str:
    return "#" + "#".join(collapse_text(value) for value in values)


def build_cdt_bytes(
    category_ids: list[str],
    fields: list[str],
    records: list[ConstructionRecord],
) -> bytes:
    lines = [
        serialize_cdt_line(category_ids),
        serialize_cdt_line(fields),
    ]
    for record in records:
        lines.append(serialize_cdt_line([record.get(field, "") for field in fields]))
    return ("\r\n".join(lines) + "\r\n").encode("cp1252")


def build_seed_record_lookup(reference_records: list[ConstructionRecord]) -> dict[str, ConstructionRecord]:
    seed_lookup: dict[str, ConstructionRecord] = {}
    for record in reference_records:
        name = record.get("Name", "").strip()
        if name:
            seed_lookup[name] = record
    return seed_lookup


def reset_construction_layer_slots(record: ConstructionRecord) -> None:
    for slot_index in range(1, MAX_LAYER_SLOTS + 1):
        record[f"Mat {slot_index}"] = "1"
        record[f"Thick {slot_index}"] = "0"
        record[f"BMat {slot_index}"] = "1"
        record[f"PercBridge {slot_index}"] = "0"
        record[f"Bridged {slot_index}"] = "0"


def build_generation_plans(
    grouped_rows: dict[tuple[str, str, str], list[CsvLayerInput]],
    config: dict,
    id_lookup: Mapping[str, MaterialReference],
    thickness_lookup: Mapping[str, MaterialReference],
) -> tuple[list[GeneratedConstructionPlan], list[str]]:
    csv_mapping = config["construction_csv_mapping"]
    category_map = csv_mapping["category_text_to_id"]
    seed_map = csv_mapping["seed_records_by_category"]
    issues: list[str] = []
    plans: list[GeneratedConstructionPlan] = []

    grouped_by_name: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for group_key in grouped_rows:
        grouped_by_name[group_key[1]].append(group_key)
    for construction_name, keys in sorted(grouped_by_name.items()):
        if len(keys) > 1:
            issues.append(
                f"{construction_name}: duplicate construction_name appears in multiple groups {keys}; Name must be unique."
            )

    for (code, name, category_text), group_rows in grouped_rows.items():
        group_issue_count = len(issues)
        category_id = category_map.get(category_text, "")
        seed_name = seed_map.get(category_text, "")
        if not category_id:
            issues.append(f"{name}: category '{category_text}' is not mapped to CategoryId.")
        if not seed_name:
            issues.append(f"{name}: category '{category_text}' has no configured seed record.")

        if len(group_rows) > MAX_LAYER_SLOTS:
            issues.append(
                f"{name}: group has {len(group_rows)} layers but reference schema supports only {MAX_LAYER_SLOTS}."
            )

        layer_orders = [row.layer_order for row in group_rows]
        expected_orders = list(range(1, len(group_rows) + 1))
        if layer_orders != expected_orders:
            issues.append(f"{name}: layer_order sequence must be contiguous from 1..n; found {layer_orders}.")

        if len(issues) != group_issue_count:
            continue

        description = next((row.notes for row in group_rows if row.notes), "")
        resolved_layers: list[ResolvedConstructionLayer] = []

        for row in group_rows:
            id_reference = id_lookup.get(row.material_name)
            if not id_reference or not id_reference.material_id:
                issues.append(f"{name}: material '{row.material_name}' has no resolved material Id.")
                continue

            thickness_reference = thickness_lookup.get(row.material_name)
            thickness_text = row.thickness_override_m
            thickness_source = "csv override"
            if not thickness_text:
                thickness_text = thickness_reference.default_thickness if thickness_reference else ""
                thickness_source = thickness_reference.source if thickness_reference else "UNRESOLVED"

            thickness_decimal = parse_positive_decimal_or_none(thickness_text)
            if thickness_decimal is None:
                issues.append(
                    f"{name}: material '{row.material_name}' has no valid thickness after override/default lookup."
                )
                continue

            resolved_layers.append(
                ResolvedConstructionLayer(
                    slot_index=row.layer_order,
                    material_name=row.material_name,
                    material_id=id_reference.material_id,
                    thickness_decimal=thickness_decimal,
                    thickness_source=thickness_source,
                )
            )

        if len(resolved_layers) != len(group_rows):
            continue

        plans.append(
            GeneratedConstructionPlan(
                construction_code=code,
                construction_name=name,
                category_text=category_text,
                category_id=category_id,
                description=description,
                seed_name=seed_name,
                layers=resolved_layers,
                total_thickness=sum((layer.thickness_decimal for layer in resolved_layers), Decimal("0")),
            )
        )

    return plans, issues


def build_generated_construction_records(
    header_fields: list[str],
    reference_records: list[ConstructionRecord],
    plans: list[GeneratedConstructionPlan],
    config: dict,
) -> tuple[list[ConstructionRecord], list[str]]:
    csv_mapping = config["construction_csv_mapping"]
    seed_lookup = build_seed_record_lookup(reference_records)
    issues: list[str] = []
    existing_ids = [
        record_id
        for record_id in (parse_int_or_none(record.get("Id", "")) for record in reference_records)
        if record_id is not None
    ]
    next_id = max(existing_ids, default=0) + 1
    generated_records: list[ConstructionRecord] = []

    for plan in plans:
        seed_record = seed_lookup.get(plan.seed_name)
        if seed_record is None:
            issues.append(f"{plan.construction_name}: seed record '{plan.seed_name}' was not found in the reference CDT.")
            continue

        generated_record = dict(seed_record)
        reset_construction_layer_slots(generated_record)

        generated_record["Id"] = str(next_id)
        next_id += 1
        generated_record["Name"] = plan.construction_name
        generated_record["CategoryId"] = plan.category_id
        generated_record["Description"] = plan.description
        generated_record["Source"] = f"IBST CSV Input - {plan.construction_code}"
        generated_record["DefinitionMethod"] = csv_mapping["definition_method_fixed_value"]
        generated_record["NumberLayers"] = str(len(plan.layers))
        generated_record["Thickness"] = format_decimal_for_cdt(plan.total_thickness)
        generated_record["UseUserUValue"] = "0"
        generated_record["UserUValue"] = ""

        for layer in plan.layers:
            generated_record[f"Mat {layer.slot_index}"] = layer.material_id
            generated_record[f"Thick {layer.slot_index}"] = format_decimal_for_cdt(layer.thickness_decimal)

        generated_records.append({field: collapse_text(generated_record.get(field, "")) for field in header_fields})

    return generated_records, issues


def write_generated_cdt(
    output_path: Path,
    schema: ReferenceSchema,
    generated_records: list[ConstructionRecord],
) -> None:
    output_path.write_bytes(build_cdt_bytes(schema["category_ids"], schema["fields"], generated_records))


def build_packaged_material_records(
    material_catalog: MaterialCatalog,
    plans: list[GeneratedConstructionPlan],
) -> list[ConstructionRecord]:
    required_names: list[str] = []
    seen_names: set[str] = set()
    for plan in plans:
        for layer in plan.layers:
            if layer.material_name not in seen_names:
                seen_names.add(layer.material_name)
                required_names.append(layer.material_name)

    return [material_catalog.records_by_name[name] for name in required_names]


def resolve_generated_output_paths(
    paths: WorkspacePaths,
    csv_rows: list[CsvLayerInput],
) -> tuple[Path, Path, Path]:
    csv_files = sorted({row.source_file for row in csv_rows}, key=lambda path: path.name.lower())
    output_dir = resolve_generated_output_dir(paths, csv_files)
    output_cdt_path = output_dir / paths.generated_cdt.name
    output_ddf_path = output_dir / paths.generated_ddf.name
    return output_dir, output_cdt_path, output_ddf_path


def prepare_generated_output_artifacts(
    paths: WorkspacePaths,
    config: dict,
    selected_csv_names: tuple[str, ...] = (),
) -> tuple[GeneratedOutputArtifacts | None, list[str]]:
    issues: list[str] = []
    issues.extend(validate_config_structure(config))
    issues.extend(validate_config_logic(config))
    issues.extend(validate_workspace(paths, config, require_reference_files=True, selected_csv_names=selected_csv_names))

    csv_rows, csv_issues = load_construction_csv_rows(paths, config, selected_csv_names)
    issues.extend(csv_issues)
    if issues:
        return None, issues

    schema = cast(ReferenceSchema, json.loads(paths.reference_exported_schema.read_text(encoding="utf-8")))
    header_fields, reference_records = load_cdt_records(paths.reference_exported_cdt, config["ddf_cdt"]["cdt_field_delimiter"])
    grouped_rows = group_construction_rows(csv_rows)
    required_material_names = {row.material_name for row in csv_rows}
    id_catalog_candidates = load_material_id_catalog_candidates(config, paths)
    selected_id_catalog, catalog_issues = select_material_id_catalog(id_catalog_candidates, required_material_names)
    if selected_id_catalog is None:
        return (
            None,
            [
                "No single material Id catalog covers all materials required by the current construction CSV input.",
                *catalog_issues,
            ],
        )

    id_lookup = {
        name: MaterialReference(
            name=name,
            source=selected_id_catalog.source,
            material_id=record.get("Id", "").strip(),
            default_thickness=record.get("DefaultThickness", "").strip(),
        )
        for name, record in selected_id_catalog.records_by_name.items()
    }
    _, thickness_lookup = load_material_lookup(config, paths)
    plans, plan_issues = build_generation_plans(grouped_rows, config, id_lookup, thickness_lookup)
    if plan_issues:
        return None, plan_issues

    generated_records, generation_issues = build_generated_construction_records(
        header_fields,
        reference_records,
        plans,
        config,
    )
    if generation_issues:
        return None, generation_issues

    output_dir, output_cdt_path, output_ddf_path = resolve_generated_output_paths(paths, csv_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    replaced_existing_cdt = output_cdt_path.exists()

    try:
        write_generated_cdt(output_cdt_path, schema, generated_records)
    except UnicodeEncodeError as error:
        return (
            None,
            [
                f"Output contains characters that cannot be encoded to cp1252 at position {error.start}-{error.end}.",
                "DesignBuilder reference export appears to use cp1252; sanitize unsupported characters in CSV text fields first.",
            ],
        )

    inferred = infer_cdt_structure(output_cdt_path, config["ddf_cdt"]["cdt_field_delimiter"])
    issues.extend(compare_cdt_structure_to_schema(inferred, schema))

    return (
        GeneratedOutputArtifacts(
            schema=schema,
            plans=plans,
            generated_records=generated_records,
            material_id_catalog=selected_id_catalog,
            inferred_structure=inferred,
            output_dir=output_dir,
            output_cdt_path=output_cdt_path,
            output_ddf_path=output_ddf_path,
            replaced_existing_cdt=replaced_existing_cdt,
        ),
        issues,
    )


def print_generated_cdt_summary(artifacts: GeneratedOutputArtifacts) -> None:
    print("GENERATED CDT")
    print(f"- Output folder: {artifacts.output_dir}")
    print(f"- Output CDT: {artifacts.output_cdt_path.name}")
    print(
        f"- Output action: {'replaced existing file' if artifacts.replaced_existing_cdt else 'created new file'}"
    )
    print(f"- Generated records: {len(artifacts.generated_records)}")
    print(f"- Field count: {artifacts.inferred_structure['field_count']}")
    print(f"- Category ids preserved: {artifacts.inferred_structure['category_id_count']}")
    print(f"- Material Id catalog: {artifacts.material_id_catalog.source}")
    print("")

    print("GENERATED CONSTRUCTIONS")
    for generated_record, plan in zip(artifacts.generated_records, artifacts.plans, strict=False):
        print(
            f"- {generated_record['Id']} | {plan.construction_name} | "
            f"CategoryId={plan.category_id} | NumberLayers={len(plan.layers)} | "
            f"Thickness={generated_record['Thickness']} | Seed={plan.seed_name}"
        )
        for layer in plan.layers:
            print(
                f"  Layer {layer.slot_index} -> {layer.material_name} | "
                f"Mat {layer.slot_index}={layer.material_id} | "
                f"Thick {layer.slot_index}={format_decimal_for_cdt(layer.thickness_decimal)} "
                f"via {layer.thickness_source}"
            )
    print("")


def get_reference_package_entry_names(paths: WorkspacePaths, config: dict) -> tuple[str, str]:
    configured_construction_entry = config["ddf_cdt"]["reference_package_cdt_entry_name"]
    configured_materials_entry = config["ddf_cdt"]["reference_package_materials_entry_name"]
    with zipfile.ZipFile(paths.reference_ddf) as archive:
        entry_names = archive.namelist()

    if configured_construction_entry not in entry_names:
        raise ValueError(
            f"Reference DDF does not contain configured construction entry name '{configured_construction_entry}'."
        )
    if configured_materials_entry not in entry_names:
        raise ValueError(
            f"Reference DDF does not contain configured materials entry name '{configured_materials_entry}'."
        )

    return configured_construction_entry, configured_materials_entry


def package_generated_ddf(
    artifacts: GeneratedOutputArtifacts,
    output_cdt_path: Path,
    output_ddf_path: Path,
    paths: WorkspacePaths,
    config: dict,
) -> tuple[Path, bool]:
    if not output_cdt_path.is_file():
        raise ValueError(f"Generated CDT file does not exist yet and cannot be packaged: {output_cdt_path}")

    constructions_entry_name, materials_entry_name = get_reference_package_entry_names(paths, config)
    materials_records = build_packaged_material_records(artifacts.material_id_catalog, artifacts.plans)
    materials_payload = build_cdt_bytes(
        artifacts.material_id_catalog.category_ids,
        artifacts.material_id_catalog.fields,
        materials_records,
    )
    replaced_existing_ddf = output_ddf_path.exists()
    with zipfile.ZipFile(output_ddf_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(output_cdt_path, arcname=constructions_entry_name)
        archive.writestr(materials_entry_name, materials_payload)
    return output_ddf_path, replaced_existing_ddf


def validate_generated_ddf_package(
    artifacts: GeneratedOutputArtifacts,
    output_cdt_path: Path,
    output_ddf_path: Path,
    paths: WorkspacePaths,
    config: dict,
) -> list[str]:
    issues: list[str] = []
    if not output_ddf_path.is_file():
        return [f"Missing generated DDF: {output_ddf_path}"]
    if not output_cdt_path.is_file():
        return [f"Missing generated CDT required for DDF validation: {output_cdt_path}"]

    try:
        expected_constructions_entry, expected_materials_entry = get_reference_package_entry_names(paths, config)
    except ValueError as error:
        return [str(error)]

    try:
        with zipfile.ZipFile(output_ddf_path) as archive:
            entry_names = archive.namelist()
            cdt_entries = [name for name in entry_names if name.lower().endswith(".cdt")]
            if expected_constructions_entry not in entry_names:
                issues.append(
                    f"Generated DDF does not contain expected CDT entry '{expected_constructions_entry}'."
                )
            if expected_materials_entry not in entry_names:
                issues.append(
                    f"Generated DDF does not contain expected CDT entry '{expected_materials_entry}'."
                )
            if len(cdt_entries) != 2:
                issues.append(
                    f"Generated DDF should contain exactly two CDT entries, found {len(cdt_entries)}."
                )
            if expected_constructions_entry in entry_names:
                packaged_bytes = archive.read(expected_constructions_entry)
                generated_bytes = output_cdt_path.read_bytes()
                if packaged_bytes != generated_bytes:
                    issues.append("Generated DDF CDT entry content does not match Constructions_generated.cdt.")
            if expected_materials_entry in entry_names:
                packaged_bytes = archive.read(expected_materials_entry)
                expected_materials_bytes = build_cdt_bytes(
                    artifacts.material_id_catalog.category_ids,
                    artifacts.material_id_catalog.fields,
                    build_packaged_material_records(artifacts.material_id_catalog, artifacts.plans),
                )
                if packaged_bytes != expected_materials_bytes:
                    issues.append("Generated DDF Materials.cdt entry content does not match the packaged material catalog subset.")
    except zipfile.BadZipFile:
        issues.append("Generated DDF is not readable as a zip-compatible package.")

    return issues


def run_analyse_input(paths: WorkspacePaths, config: dict, selected_csv_names: tuple[str, ...] = ()) -> int:
    print(standard_workflow_text())

    issues: list[str] = []
    issues.extend(validate_config_structure(config))
    issues.extend(validate_config_logic(config))
    issues.extend(validate_workspace(paths, config, require_reference_files=True, selected_csv_names=selected_csv_names))

    csv_rows, csv_issues = load_construction_csv_rows(paths, config, selected_csv_names)
    issues.extend(csv_issues)

    if issues:
        print("ANALYSE-INPUT RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    csv_mapping = config["construction_csv_mapping"]
    category_map = csv_mapping["category_text_to_id"]
    seed_map = csv_mapping["seed_records_by_category"]
    id_lookup, thickness_lookup = load_material_lookup(config, paths)
    grouped_rows = group_construction_rows(csv_rows)

    analysis_issues: list[str] = []

    print("INPUT SUMMARY")
    print(f"- Active CSV rows: {len(csv_rows)}")
    print(f"- Construction groups: {len(grouped_rows)}")
    print(f"- Categories found: {', '.join(sorted({row.category_text for row in csv_rows}))}")
    print("")

    print("GROUP MAPPING")
    for (code, name, category_text), group_rows in grouped_rows.items():
        category_id = category_map.get(category_text, "")
        seed_name = seed_map.get(category_text, "")
        if not category_id:
            analysis_issues.append(f"{name}: category '{category_text}' is not mapped to CategoryId.")

        layer_orders = [row.layer_order for row in group_rows]
        expected_orders = list(range(1, len(group_rows) + 1))
        if layer_orders != expected_orders:
            analysis_issues.append(
                f"{name}: layer_order sequence must be contiguous from 1..n; found {layer_orders}."
            )

        description = next((row.notes for row in group_rows if row.notes), "")
        resolved_thicknesses: list[Decimal] = []

        print(
            f"- {code} | {name} | category='{category_text}' -> CategoryId={category_id or 'UNMAPPED'} "
            f"| seed={seed_name or 'MISSING'} | NumberLayers={len(group_rows)}"
        )
        if description:
            print(f"  Description <- {description}")

        for row in group_rows:
            id_reference = id_lookup.get(row.material_name)
            thickness_reference = thickness_lookup.get(row.material_name)
            if not id_reference:
                analysis_issues.append(
                    f"{name}: material '{row.material_name}' has no resolved material Id in lookup sources."
                )
            thickness_text = row.thickness_override_m
            thickness_source = "csv override"
            if not thickness_text:
                thickness_text = thickness_reference.default_thickness if thickness_reference else ""
                thickness_source = thickness_reference.source if thickness_reference else "UNRESOLVED"
            thickness_decimal = parse_positive_decimal_or_none(thickness_text)
            if thickness_decimal is None:
                analysis_issues.append(
                    f"{name}: material '{row.material_name}' has no valid thickness value after override/default lookup."
                )
            else:
                resolved_thicknesses.append(thickness_decimal)

            print(
                f"  Layer {row.layer_order} -> Mat {row.layer_order} name='{row.material_name}' "
                f"id='{id_reference.material_id if id_reference else 'UNRESOLVED'}' "
                f"| Thick {row.layer_order}='{thickness_text or 'UNRESOLVED'}' via {thickness_source}"
            )

        if csv_mapping["thickness_from_sum_of_layer_thicknesses"] and len(resolved_thicknesses) == len(group_rows):
            thickness_total = sum(resolved_thicknesses, Decimal("0"))
            print(f"  Aggregate Thickness -> {thickness_total.normalize()}")
        print("")

    print("LOOKUP COVERAGE")
    unique_material_names = sorted({row.material_name for row in csv_rows})
    resolved_ids = sum(1 for name in unique_material_names if name in id_lookup)
    resolved_thickness = sum(1 for name in unique_material_names if name in thickness_lookup)
    print(f"- Unique material names in CSV: {len(unique_material_names)}")
    print(f"- Resolved material Ids: {resolved_ids}/{len(unique_material_names)}")
    print(f"- Resolved default thicknesses: {resolved_thickness}/{len(unique_material_names)}")
    print("")

    if analysis_issues:
        print("ANALYSE-INPUT RESULT: FAIL")
        for issue in analysis_issues:
            print(f"- {issue}")
        return 1

    print("ANALYSE-INPUT RESULT: PASS")
    print("The CSV layout in 02_csv_input maps cleanly into the current construction CDT target model.")
    return 0


def validate_workspace(
    paths: WorkspacePaths,
    config: dict,
    require_reference_files: bool,
    selected_csv_names: tuple[str, ...] = (),
) -> list[str]:
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

    if require_reference_files:
        required_files = [
            paths.reference_ddf,
            paths.reference_exported_cdt,
            paths.reference_exported_schema,
        ]
        for file_path in required_files:
            if not file_path.is_file():
                issues.append(f"Missing required reference file: {file_path}")

    reference_info, reference_issues = inspect_reference_ddf(paths, config)
    issues.extend(reference_issues)

    csv_files, discovery_issues = discover_csv_files(paths, config, selected_csv_names)
    issues.extend(discovery_issues)

    if not require_reference_files and not csv_files:
        reference_info.append("No active CSV input files discovered yet.")

    if paths.reference_exported_schema.is_file():
        schema = cast(ReferenceSchema, json.loads(paths.reference_exported_schema.read_text(encoding="utf-8")))
        issues.extend(validate_schema_file(schema))
        if paths.reference_exported_cdt.is_file():
            inferred = infer_cdt_structure(paths.reference_exported_cdt, config["ddf_cdt"]["cdt_field_delimiter"])
            issues.extend(compare_cdt_structure_to_schema(inferred, schema))

    return issues


def print_workspace_summary(paths: WorkspacePaths, config: dict, selected_csv_names: tuple[str, ...] = ()) -> None:
    csv_files, discovery_issues = discover_csv_files(paths, config, selected_csv_names)
    reference_info, reference_issues = inspect_reference_ddf(paths, config)
    future_pipeline = config["future_pipeline"]

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
    for path in [paths.reference_ddf, paths.reference_exported_cdt, paths.reference_exported_schema]:
        status = "present" if path.is_file() else "missing"
        print(f"- {path.name}: {status}")
    for line in reference_info:
        print(f"- {line}")
    for issue in reference_issues:
        print(f"- Reference issue: {issue}")
    if paths.reference_exported_cdt.is_file():
        inferred = infer_cdt_structure(paths.reference_exported_cdt, config["ddf_cdt"]["cdt_field_delimiter"])
        print(f"- Extracted CDT line count: {inferred['line_count']}")
        print(f"- Extracted CDT field count: {inferred['field_count']}")
        print(f"- Extracted CDT record count: {inferred['record_count']}")
    print("")

    print("CSV INPUT FILES")
    if csv_files:
        for path in csv_files:
            print(f"- {path.name}")
    else:
        print("- No active CSV files discovered.")
    for issue in discovery_issues:
        print(f"- Discovery issue: {issue}")
    print("")

    print("ALLOWED OUTPUT FILES")
    for name in config["artifacts"]["allowed_output_files"]:
        print(f"- {name}")
    print("")

    print("FUTURE PIPELINE STATUS")
    print(f"- reference_capture_complete: {future_pipeline['reference_capture_complete']}")
    print(f"- mapping_rules_complete: {future_pipeline['mapping_rules_complete']}")
    print(f"- generator_implemented: {future_pipeline['generator_implemented']}")
    print(f"- package_generator_implemented: {future_pipeline['package_generator_implemented']}")
    print(f"- current_supported_modes: {', '.join(future_pipeline['current_supported_modes'])}")
    print("")


def run_summary(paths: WorkspacePaths, config: dict, selected_csv_names: tuple[str, ...] = ()) -> int:
    print(standard_workflow_text())
    print_workspace_summary(paths, config, selected_csv_names)

    issues: list[str] = []
    issues.extend(validate_config_structure(config))
    issues.extend(validate_config_logic(config))
    issues.extend(validate_workspace(paths, config, require_reference_files=False, selected_csv_names=selected_csv_names))

    structural_issues = [
        issue for issue in issues if issue.startswith("Missing required directory") or issue.startswith("Missing input directory")
    ]
    if structural_issues:
        print("SUMMARY RESULT: FAIL")
        for issue in structural_issues:
            print(f"- {issue}")
        return 1

    print("SUMMARY RESULT: PASS")
    print("Workspace structure is aligned with the standard construction-test layout.")
    print("Use analyse-schema and analyse-input to verify mapping before generating new CDT/DDF outputs.")
    return 0


def run_extract_reference(paths: WorkspacePaths, config: dict) -> int:
    issues: list[str] = []
    issues.extend(validate_config_structure(config))
    issues.extend(validate_config_logic(config))

    if issues:
        print("EXTRACT-REFERENCE RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(standard_workflow_text())

    try:
        schema, cdt_changed, schema_changed = extract_reference_artifacts(paths, config)
    except FileNotFoundError as error:
        print("EXTRACT-REFERENCE RESULT: FAIL")
        print(f"- {error}")
        return 1
    except KeyError as error:
        print("EXTRACT-REFERENCE RESULT: FAIL")
        print(f"- Missing DDF entry: {error}")
        return 1
    except zipfile.BadZipFile:
        print("EXTRACT-REFERENCE RESULT: FAIL")
        print("- Reference DDF is not readable as a zip-compatible package.")
        return 1

    schema_issues = validate_schema_file(schema)
    inferred = infer_cdt_structure(paths.reference_exported_cdt, config["ddf_cdt"]["cdt_field_delimiter"])
    schema_issues.extend(compare_cdt_structure_to_schema(inferred, schema))

    print("EXTRACTED REFERENCE")
    print(f"- Source DDF: {paths.reference_ddf.name}")
    print(f"- Extracted CDT: {paths.reference_exported_cdt.name}")
    print(f"- Extracted schema: {paths.reference_exported_schema.name}")
    print(f"- CDT updated: {'yes' if cdt_changed else 'no'}")
    print(f"- Schema updated: {'yes' if schema_changed else 'no'}")
    print(f"- Category count: {inferred['category_id_count']}")
    print(f"- Field count: {inferred['field_count']}")
    print(f"- Record count: {inferred['record_count']}")
    print(f"- Record field counts found: {inferred['record_field_counts_unique']}")
    print("")

    if schema_issues:
        print("EXTRACT-REFERENCE RESULT: FAIL")
        for issue in schema_issues:
            print(f"- {issue}")
        return 1

    print("EXTRACT-REFERENCE RESULT: PASS")
    print("The construction CDT and schema were captured directly from the current DesignBuilder DDF reference.")
    return 0


def run_analyse_schema(paths: WorkspacePaths, config: dict) -> int:
    print(standard_workflow_text())

    issues: list[str] = []
    issues.extend(validate_config_structure(config))
    issues.extend(validate_config_logic(config))
    issues.extend(validate_workspace(paths, config, require_reference_files=True))

    if issues:
        print("ANALYSE-SCHEMA RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        print("Run extract-reference after adding or updating the reference DDF.")
        return 1

    schema = cast(ReferenceSchema, json.loads(paths.reference_exported_schema.read_text(encoding="utf-8")))
    fields, records = load_cdt_records(paths.reference_exported_cdt, config["ddf_cdt"]["cdt_field_delimiter"])
    repeated_groups, non_repeated_fields = detect_repeated_field_groups(fields)
    classified_non_repeated = classify_non_repeated_fields(non_repeated_fields)
    population = summarize_field_population(fields, records)
    variation = summarize_field_variation(fields, records)
    varying_field_names = [field for field, _ in variation["varying_fields"]]
    linked_clusters = find_linked_field_clusters(varying_field_names, records)
    record_layers = summarize_record_layers(records)
    repeated_group_summaries = [
        summarize_repeated_group(records, base, indices)
        for base, indices in repeated_groups.items()
    ]
    used_categories = sorted({record.get("CategoryId", "").strip() for record in records if record.get("CategoryId", "").strip()})

    print("SCHEMA SUMMARY")
    print(f"- Sample file: {schema['sample_file']}")
    print(f"- Category ids in schema: {schema['counts']['category_id_count']}")
    print(f"- Field count: {schema['counts']['field_count']}")
    print(f"- Record count at capture: {schema['counts']['record_count_at_capture']}")
    print(f"- Category ids used in sample records: {', '.join(used_categories)}")
    print("")

    print("REPEATED FIELD GROUPS")
    for group_summary in repeated_group_summaries:
        print(
            f"- {group_summary['base']}: {group_summary['slot_count']} slots; "
            f"varying={compress_indices(group_summary['varying_slots'])}; "
            f"constant-placeholder={compress_indices(group_summary['constant_placeholder_slots'])}; "
            f"constant-value={compress_indices(group_summary['constant_value_slots'])}; "
            f"sparse={compress_indices(group_summary['sparse_slots'])}; "
            f"empty={compress_indices(group_summary['always_empty_slots'])}"
        )
    print("")

    print("NON-REPEATED FIELD GROUPS")
    for group_name, group_fields in ordered_non_repeated_field_groups(classified_non_repeated):
        print(f"- {group_name} ({len(group_fields)}): {', '.join(group_fields)}")
    print("")

    print("SAMPLE RECORDS")
    for summary in record_layers:
        print(
            f"- {summary['name']} | CategoryId={summary['category_id']} | "
            f"NumberLayers={summary['number_layers']} | "
            f"ActiveLayers={', '.join(summary['active_layers'])}"
        )
        if summary["overflow_slots"]:
            print(f"  Overflow non-default slots beyond NumberLayers: {compress_indices(summary['overflow_slots'])}")
    print("")

    print("FIELD POPULATION")
    print(f"- Always non-empty fields: {len(population['always_non_empty'])}")
    print(f"- Always empty fields: {len(population['always_empty'])}")
    if population["sometimes_non_empty"]:
        sample_text = ", ".join(
            f"{field} ({count}/{len(records)})"
            for field, count in population["sometimes_non_empty"][:20]
        )
        print(f"- Partially populated fields: {sample_text}")
    else:
        print("- No partially populated fields in the current sample.")
    print("")

    print("FIELD VARIATION")
    print(f"- Constant fields across sample records: {len(variation['constant_fields'])}")
    print(f"- Varying fields across sample records: {len(variation['varying_fields'])}")
    print(
        "- Varying fields: "
        + ", ".join(field for field, _ in variation["varying_fields"])
    )
    print("")

    print("LINKED FIELD CLUSTERS")
    if linked_clusters:
        for cluster in linked_clusters:
            print(f"- {', '.join(cluster)}")
    else:
        print("- No linked varying-field clusters found.")
    print("")

    print("INPUT PREPARATION GUIDANCE")
    for line in build_input_preparation_guidance(records):
        print(f"- {line}")
    print("")

    print("ANALYSE-SCHEMA RESULT: PASS")
    print("The reference schema/content has been analysed and is ready to guide the next input-design step.")
    return 0


def run_generate_cdt(paths: WorkspacePaths, config: dict, selected_csv_names: tuple[str, ...] = ()) -> int:
    print(standard_workflow_text())
    artifacts, issues = prepare_generated_output_artifacts(paths, config, selected_csv_names)
    if artifacts is not None:
        print_generated_cdt_summary(artifacts)

    if issues:
        print("GENERATE-CDT RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        if artifacts is not None:
            print(f"Generated CDT path: {artifacts.output_cdt_path}")
        return 1

    print("GENERATE-CDT RESULT: PASS")
    print(f"Generated CDT path: {artifacts.output_cdt_path}")
    print("The CSV input was converted into a schema-aligned Constructions_generated.cdt using the configured category seeds.")
    print("Seed-derived thermal/surface/library fields were preserved unless explicitly remapped by the CSV generator.")
    return 0


def run_generate_ddf(paths: WorkspacePaths, config: dict, selected_csv_names: tuple[str, ...] = ()) -> int:
    print(standard_workflow_text())

    artifacts, issues = prepare_generated_output_artifacts(paths, config, selected_csv_names)
    if artifacts is not None:
        print_generated_cdt_summary(artifacts)

    if issues:
        print("GENERATE-DDF RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        if artifacts is not None:
            print(f"Generated CDT path: {artifacts.output_cdt_path}")
        print("The CDT generation step failed rule/schema checks, so DDF packaging was not completed.")
        return 1

    try:
        output_ddf_path, replaced_existing_ddf = package_generated_ddf(
            artifacts,
            artifacts.output_cdt_path,
            artifacts.output_ddf_path,
            paths,
            config,
        )
    except ValueError as error:
        print("GENERATE-DDF RESULT: FAIL")
        print(f"- {error}")
        print(f"Generated CDT path: {artifacts.output_cdt_path}")
        return 1

    package_issues = validate_generated_ddf_package(
        artifacts,
        artifacts.output_cdt_path,
        output_ddf_path,
        paths,
        config,
    )
    constructions_entry_name, materials_entry_name = get_reference_package_entry_names(paths, config)

    print("GENERATED DDF")
    print(f"- Output folder: {artifacts.output_dir}")
    print(f"- Output DDF: {output_ddf_path.name}")
    print(f"- Output action: {'replaced existing file' if replaced_existing_ddf else 'created new file'}")
    print(f"- Internal package entries: {constructions_entry_name}, {materials_entry_name}")
    print("")

    if package_issues:
        print("GENERATE-DDF RESULT: FAIL")
        for issue in package_issues:
            print(f"- {issue}")
        print(f"Generated CDT path: {artifacts.output_cdt_path}")
        print(f"Generated DDF path: {output_ddf_path}")
        print("The DDF package was written but did not pass package validation.")
        return 1

    print("GENERATE-DDF RESULT: PASS")
    print(f"Generated CDT path: {artifacts.output_cdt_path}")
    print(f"Generated DDF path: {output_ddf_path}")
    print("The DDF package was generated from CSV, packaged with the reference internal CDT entry name, and passed validation.")
    return 0


def run_preflight(paths: WorkspacePaths, config: dict, selected_csv_names: tuple[str, ...] = ()) -> int:
    print(standard_workflow_text())
    print_workspace_summary(paths, config, selected_csv_names)

    issues: list[str] = []
    issues.extend(validate_config_structure(config))
    issues.extend(validate_config_logic(config))
    issues.extend(validate_workspace(paths, config, require_reference_files=True, selected_csv_names=selected_csv_names))

    if issues:
        print("PREFLIGHT RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        print("Run extract-reference after adding or updating the reference DDF.")
        return 1

    print("PREFLIGHT RESULT: PASS")
    print("The workspace structure and captured reference files are ready for the next construction-mapping step.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate IBST_Construction_Test workspace structure and analyse captured construction references."
    )
    parser.add_argument(
        "--mode",
        choices=["summary", "extract-reference", "analyse-schema", "analyse-input", "generate-cdt", "generate-ddf", "preflight"],
        default="summary",
        help="Supported modes: summary, extract-reference, analyse-schema, analyse-input, generate-cdt, generate-ddf, preflight.",
    )
    parser.add_argument(
        "--input-file",
        action="append",
        default=[],
        help="Optional CSV filename inside 02_csv_input to include. Repeat to include multiple files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    config = load_rules_config(root)
    paths = build_workspace_paths(Path(__file__), config)
    selected_csv_names = tuple(args.input_file)

    if args.mode == "summary":
        return run_summary(paths, config, selected_csv_names)
    if args.mode == "extract-reference":
        return run_extract_reference(paths, config)
    if args.mode == "analyse-schema":
        return run_analyse_schema(paths, config)
    if args.mode == "analyse-input":
        return run_analyse_input(paths, config, selected_csv_names)
    if args.mode == "generate-cdt":
        return run_generate_cdt(paths, config, selected_csv_names)
    if args.mode == "generate-ddf":
        return run_generate_ddf(paths, config, selected_csv_names)
    if args.mode == "preflight":
        return run_preflight(paths, config, selected_csv_names)

    print(f"Unsupported mode: {args.mode}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
