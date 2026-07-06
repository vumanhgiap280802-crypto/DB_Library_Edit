#!/usr/bin/env python
"""
IBST_Glazing - build Glazing CDT/DDF from CSV input.

This is a narrow generator for the current glazing test workflow. It uses the
captured DesignBuilder Glazing.cdt reference as the schema/seed source, then
packages the generated CDT with the companion Panes.cdt and WindowGas.cdt
reference tables when they are available.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import zipfile


CORE_REQUIRED_COLUMNS = [
    "glazing_name",
    "category_id",
    "definition_method",
    "layers",
    "u_value",
    "visible_transmittance",
    "solar_transmittance_or_shgc",
    "direct_solar_transmittance",
    "mat_1_ref",
]

PANE_REQUIRED_COLUMNS = [
    "pane_name",
    "category_id",
    "thickness",
    "solar_transmittance",
    "front_solar_reflectance",
    "back_solar_reflectance",
    "visible_transmittance",
    "front_visible_reflectance",
    "back_visible_reflectance",
    "conductivity",
]

CSV_TO_CDT_FIELDS = {
    "glazing_name": "Name",
    "category_id": "CategoryId",
    "definition_method": "DefinitionMethod",
    "source": "Source",
    "region_id": "RegionId",
    "description": "Description",
    "colour": "Colour",
    "layers": "Layers",
    "u_value": "U-Value",
    "visible_transmittance": "TransLight",
    "solar_transmittance_or_shgc": "TransSolar",
    "direct_solar_transmittance": "TransDirectSolar",
    "frame_fraction": "FrameFraction",
    "cost_per_area": "CostPerArea",
    "is_display_window": "IsDisplayWindow",
    "hide_in_lists": "HideInLists",
    "is_diffusing": "IsDiffusing",
    "diffuse_fraction": "DiffuseFraction",
    "using_enhanced_surface_coeffs": "UsingEnhancedSurfaceCoeffs",
    "hci": "HCI",
    "radi": "RadI",
    "sri": "SRI",
    "hco": "HCO",
    "rado": "RadO",
    "sro": "SRO",
}

PANE_CSV_TO_CDT_FIELDS = {
    "pane_name": "Name",
    "category_id": "CategoryId",
    "source_id": "SourceId",
    "thickness": "Thickness",
    "solar_transmittance": "SolarTransmittance",
    "front_solar_reflectance": "FrontSolarReflectance",
    "back_solar_reflectance": "BackSolarReflectance",
    "visible_transmittance": "VisibleTransmittance",
    "front_visible_reflectance": "FrontVisibleReflectance",
    "back_visible_reflectance": "BackVisibleReflectance",
    "infrared_transmittance": "InfraRedTransmittance",
    "front_infrared_reflectance": "FrontInfraRedReflectance",
    "back_infrared_reflectance": "BackInfraRedReflectance",
    "conductivity": "Conductivity",
    "region_id": "RegionId",
    "source": "Source",
    "description": "Description",
    "nfrc_id": "NFRCID",
    "colour": "Colour",
    "data_type": "DataType",
    "use_flipped": "UseFlipped",
    "igdb_name": "IGDBName",
    "spectral_data": "SpectralData",
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Glazing_generated.cdt and Glazing_generated.ddf from a glazing CSV input."
    )
    parser.add_argument(
        "--input-file",
        required=True,
        help="CSV filename inside 02_csv_input, with or without .csv extension.",
    )
    parser.add_argument(
        "--panes-input-file",
        help="Optional panes CSV filename inside 02_csv_input. If omitted, a single panes_*.csv file is auto-detected.",
    )
    parser.add_argument(
        "--output-subdir",
        help="Optional subfolder inside 03_output. Defaults to input stem plus timestamp.",
    )
    return parser.parse_args()


def sanitize_stem(value: str) -> str:
    stem = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    while "__" in stem:
        stem = stem.replace("__", "_")
    return stem.strip("_") or "run"


def parse_cdt_line(line: str) -> list[str]:
    line = line.rstrip("\r\n")
    if line.startswith("#"):
        line = line[1:]
    return [part.strip() for part in line.split("#")]


def format_cdt_line(values: list[str]) -> str:
    return "#" + "  #".join(values) + "  \r\n"


def format_cdt_header_line(values: list[str]) -> str:
    return "#" + " #".join(values) + " \r\n"


def decode_cdt_bytes(data: bytes, fallback_encoding: str) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    return data.decode(fallback_encoding)


def read_reference_cdt(path: Path, encoding: str) -> tuple[list[str], list[str], list[dict[str, str]]]:
    text = decode_cdt_bytes(path.read_bytes(), encoding)
    lines = text.splitlines()
    if len(lines) < 3:
        raise ValueError("Reference Glazing CDT must contain category ids, header, and at least one record.")
    category_ids = parse_cdt_line(lines[0])
    fields = parse_cdt_line(lines[1])
    records = []
    for line in lines[2:]:
        if not line.strip():
            continue
        values = parse_cdt_line(line)
        if len(values) != len(fields):
            raise ValueError(
                f"Reference record has {len(values)} fields but schema expects {len(fields)}."
            )
        records.append(dict(zip(fields, values)))
    return category_ids, fields, records


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
        return list(reader.fieldnames or []), rows


def resolve_input_csv_path(input_dir: Path, input_name: str) -> Path:
    name = input_name
    if not name.lower().endswith(".csv"):
        name += ".csv"
    return input_dir / name


def auto_detect_panes_input(input_dir: Path) -> Path | None:
    candidates = sorted(
        path for path in input_dir.glob("panes_*.csv")
        if path.is_file()
    )
    if not candidates:
        return None
    if len(candidates) > 1:
        raise ValueError(
            "Multiple panes input CSV files found; pass --panes-input-file explicitly: "
            + ", ".join(path.name for path in candidates)
        )
    return candidates[0]


def uses_material_layers(rows: list[dict[str, str]]) -> bool:
    return any(row.get("definition_method", "") == "1-Material layers" for row in rows)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("#", " ")).strip()


def normalize_bool(value: str, field_name: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"", "0", "false", "no"}:
        return "0"
    if lowered in {"1", "true", "yes"}:
        return "1"
    raise ValueError(f"{field_name} must be 0/1/true/false/yes/no, got '{value}'.")


def require_decimal(value: str, field_name: str, *, allow_zero: bool = True) -> str:
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be numeric, got '{value}'.") from error
    if number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"{field_name} must be positive, got '{value}'.")
    return value


def require_unit_interval(value: str, field_name: str) -> str:
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be numeric between 0 and 1, got '{value}'.") from error
    if number < 0 or number > 1:
        raise ValueError(f"{field_name} must be between 0 and 1, got '{value}'.")
    return value


def choose_seed(records: list[dict[str, str]], row: dict[str, str]) -> dict[str, str]:
    definition_method = row.get("definition_method", "")
    method_matches = [record for record in records if record.get("DefinitionMethod") == definition_method]
    if definition_method == "2-Simple" and method_matches:
        return dict(method_matches[0])

    layers = row.get("layers", "")
    exact = [record for record in method_matches if record.get("Layers") == layers]
    if exact:
        return dict(exact[0])
    exact = [record for record in records if record.get("Layers") == layers]
    if exact:
        return dict(exact[0])
    return dict(records[0])


def max_numeric_id(records: list[dict[str, str]]) -> int:
    ids = [int(record["Id"]) for record in records if record.get("Id", "").isdigit()]
    if not ids:
        raise ValueError("Reference CDT does not contain any numeric Id values.")
    return max(ids)


def build_component_lookup(records: list[dict[str, str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for record in records:
        component_id = clean_text(record.get("Id", ""))
        if not component_id:
            continue
        source_id = clean_text(record.get("SourceId", ""))
        preferred_reference = source_id or component_id
        for key in ("Id", "SourceId"):
            value = clean_text(record.get(key, ""))
            if value:
                lookup[value.lower()] = value
        name = clean_text(record.get("Name", ""))
        if name:
            lookup[name.lower()] = preferred_reference
    return lookup


def resolve_material_ref(
    value: str,
    slot_index: int,
    pane_lookup: dict[str, str],
    gas_lookup: dict[str, str],
    field_name: str,
) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    if cleaned.isdigit():
        return cleaned

    lookup = pane_lookup if slot_index % 2 == 1 else gas_lookup
    component_type = "Pane" if slot_index % 2 == 1 else "WindowGas"
    resolved = lookup.get(cleaned.lower())
    if resolved:
        return resolved
    raise ValueError(
        f"{field_name} must be a numeric DesignBuilder id or match a {component_type} record in the reference DDF; got '{value}'."
    )


def validate_csv(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    pane_lookup: dict[str, str],
    gas_lookup: dict[str, str],
) -> list[str]:
    issues: list[str] = []
    missing_columns = [name for name in CORE_REQUIRED_COLUMNS if name not in fieldnames]
    if missing_columns:
        issues.append("Missing required input columns: " + ", ".join(missing_columns))
    if not rows:
        issues.append("Input CSV has no data rows.")
        return issues

    seen_names: dict[str, int] = {}
    for row_number, row in enumerate(rows, start=2):
        name = clean_text(row.get("glazing_name", ""))
        if not name:
            issues.append(f"Row {row_number}: glazing_name is required.")
        elif name in seen_names:
            issues.append(f"Row {row_number}: duplicate glazing_name '{name}' also found at row {seen_names[name]}.")
        else:
            seen_names[name] = row_number

        definition_method = row.get("definition_method", "")
        if definition_method not in {"1-Material layers", "2-Simple"}:
            issues.append(
                f"Row {row_number}: definition_method must be '1-Material layers' or '2-Simple'; got '{definition_method}'."
            )
        if definition_method == "2-Simple":
            for field_name in ("visible_transmittance", "solar_transmittance_or_shgc"):
                if not row.get(field_name, ""):
                    issues.append(f"Row {row_number}: {field_name} is required for 2-Simple.")

        if definition_method == "1-Material layers":
            try:
                layers = int(row.get("layers", ""))
                if layers < 1 or layers > 4:
                    issues.append(f"Row {row_number}: layers must be 1..4 for Mat 1..7 layout.")
            except ValueError:
                issues.append(f"Row {row_number}: layers must be an integer.")

            if not row.get("mat_1_ref", ""):
                issues.append(f"Row {row_number}: mat_1_ref is required.")
            for index in range(1, 8):
                mat_value = row.get(f"mat_{index}_ref", "")
                if mat_value:
                    try:
                        resolve_material_ref(mat_value, index, pane_lookup, gas_lookup, f"mat_{index}_ref")
                    except ValueError as error:
                        issues.append(f"Row {row_number}: {error}")

        numeric_fields = ["u_value"]
        for field_name in numeric_fields:
            try:
                require_decimal(row.get(field_name, ""), field_name, allow_zero=False)
            except ValueError as error:
                issues.append(f"Row {row_number}: {error}")

        unit_fields = [
            "visible_transmittance",
            "solar_transmittance_or_shgc",
            "direct_solar_transmittance",
            "frame_fraction",
            "diffuse_fraction",
        ]
        for field_name in unit_fields:
            value = row.get(field_name, "")
            if value:
                try:
                    require_unit_interval(value, field_name)
                except ValueError as error:
                    issues.append(f"Row {row_number}: {error}")

    return issues


def validate_panes_csv(rows: list[dict[str, str]], fieldnames: list[str]) -> list[str]:
    issues: list[str] = []
    missing_columns = [name for name in PANE_REQUIRED_COLUMNS if name not in fieldnames]
    if missing_columns:
        issues.append("Missing required panes input columns: " + ", ".join(missing_columns))
    if not rows:
        issues.append("Panes input CSV has no data rows.")
        return issues

    seen_names: dict[str, int] = {}
    for row_number, row in enumerate(rows, start=2):
        name = clean_text(row.get("pane_name", ""))
        if not name:
            issues.append(f"Panes row {row_number}: pane_name is required.")
        elif name in seen_names:
            issues.append(f"Panes row {row_number}: duplicate pane_name '{name}' also found at row {seen_names[name]}.")
        else:
            seen_names[name] = row_number

        for field_name in ("thickness", "conductivity"):
            try:
                require_decimal(row.get(field_name, ""), field_name, allow_zero=False)
            except ValueError as error:
                issues.append(f"Panes row {row_number}: {error}")

        for field_name in (
            "solar_transmittance",
            "front_solar_reflectance",
            "back_solar_reflectance",
            "visible_transmittance",
            "front_visible_reflectance",
            "back_visible_reflectance",
            "infrared_transmittance",
            "front_infrared_reflectance",
            "back_infrared_reflectance",
        ):
            value = row.get(field_name, "")
            if value:
                try:
                    require_unit_interval(value, field_name)
                except ValueError as error:
                    issues.append(f"Panes row {row_number}: {error}")

        use_flipped = row.get("use_flipped", "")
        if use_flipped:
            try:
                normalize_bool(use_flipped, "use_flipped")
            except ValueError as error:
                issues.append(f"Panes row {row_number}: {error}")

    return issues


def apply_pane_csv_row_to_record(
    row: dict[str, str],
    fields: list[str],
    seed: dict[str, str],
    new_id: int,
) -> dict[str, str]:
    record = dict(seed)
    record["Id"] = str(new_id)
    record["SourceId"] = clean_text(row.get("source_id", "")) or str(new_id)
    record["Locked"] = "0"
    record["Scratch"] = "0"
    record["IsSystem"] = "0"

    for csv_field, cdt_field in PANE_CSV_TO_CDT_FIELDS.items():
        value = clean_text(row.get(csv_field, ""))
        if not value:
            continue
        if csv_field == "use_flipped":
            value = normalize_bool(value, csv_field)
        record[cdt_field] = value

    return {field: record.get(field, "") for field in fields}


def apply_csv_row_to_record(
    row: dict[str, str],
    fields: list[str],
    seed: dict[str, str],
    new_id: int,
    pane_lookup: dict[str, str],
    gas_lookup: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    record = dict(seed)
    warnings: list[str] = []
    record["Id"] = str(new_id)
    definition_method = row.get("definition_method", "")

    for csv_field, cdt_field in CSV_TO_CDT_FIELDS.items():
        value = clean_text(row.get(csv_field, ""))
        if value:
            if csv_field in {"is_display_window", "hide_in_lists", "is_diffusing", "using_enhanced_surface_coeffs"}:
                value = normalize_bool(value, csv_field)
            record[cdt_field] = value
    if definition_method == "2-Simple" and not clean_text(row.get("direct_solar_transmittance", "")):
        record["TransDirectSolar"] = record.get("TransSolar", "")

    if definition_method == "1-Material layers":
        layers = int(row["layers"])
        active_slots = set(range(1, min(2 * layers - 1, 7) + 1))
        for index in range(1, 8):
            mat_field = f"Mat {index}"
            flip_field = f"Flip {index}"
            mat_value = clean_text(row.get(f"mat_{index}_ref", ""))
            flip_value = clean_text(row.get(f"flip_{index}", ""))

            if index in active_slots:
                if mat_value:
                    record[mat_field] = resolve_material_ref(
                        mat_value,
                        index,
                        pane_lookup,
                        gas_lookup,
                        f"mat_{index}_ref",
                    )
                if flip_value:
                    record[flip_field] = normalize_bool(flip_value, f"flip_{index}")
        for index in (1, 3, 5, 7):
            matdef_value = clean_text(row.get(f"matdef_{index}", ""))
            altmat_value = clean_text(row.get(f"altmat_{index}", ""))
            if matdef_value:
                record[f"MatDef {index}"] = matdef_value
            if altmat_value:
                record[f"AltMat {index}"] = altmat_value

    return {field: record.get(field, "") for field in fields}, warnings


def output_subdir_name(input_path: Path) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{sanitize_stem(input_path.stem)}_{timestamp}"


def write_cdt(path: Path, category_ids: list[str], fields: list[str], records: list[dict[str, str]], encoding: str) -> None:
    lines = [format_cdt_header_line(category_ids), format_cdt_header_line(fields)]
    for record in records:
        lines.append(format_cdt_line([record[field] for field in fields]))
    path.write_bytes("".join(lines).encode(encoding, errors="replace"))


def package_ddf(entries: list[tuple[Path, str]], ddf_path: Path) -> None:
    with zipfile.ZipFile(ddf_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, internal_entry_name in entries:
            archive.write(path, arcname=internal_entry_name)


def validate_generated_cdt(path: Path, schema: dict, encoding: str) -> list[str]:
    issues: list[str] = []
    text = path.read_bytes().decode(encoding)
    lines = text.splitlines()
    if len(lines) < 3:
        return ["Generated CDT must have category/header/record lines."]
    fields = parse_cdt_line(lines[1])
    records = [parse_cdt_line(line) for line in lines[2:] if line.strip()]
    expected_count = schema["counts"]["field_count"]
    if fields != schema["fields"]:
        issues.append("Generated CDT fields do not match schema field order.")
    bad_counts = sorted({len(record) for record in records if len(record) != expected_count})
    if bad_counts:
        issues.append(f"Generated CDT contains record field counts outside {expected_count}: {bad_counts}")
    names = [record[1] for record in records]
    if len(names) != len(set(names)):
        issues.append("Generated CDT contains duplicate names.")
    return issues


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    config = json.loads((root / "workspace_rules.json").read_text(encoding="utf-8"))
    paths_cfg = config["paths"]
    ref_cfg = config["reference_files"]
    ddf_cfg = config["ddf_cdt"]
    encoding = config["glazing"]["reference_cdt_encoding"]

    input_dir = root / paths_cfg["input"]
    input_path = resolve_input_csv_path(input_dir, args.input_file)
    if not input_path.is_file():
        print(f"GENERATE-DDF RESULT: FAIL")
        print(f"- Input CSV not found: {input_path}")
        return 1

    fieldnames, csv_rows = read_csv_rows(input_path)
    needs_companion_tables = uses_material_layers(csv_rows)
    try:
        panes_input_path = (
            resolve_input_csv_path(input_dir, args.panes_input_file)
            if args.panes_input_file
            else (auto_detect_panes_input(input_dir) if needs_companion_tables else None)
        )
    except ValueError as error:
        print("GENERATE-DDF RESULT: FAIL")
        print(f"- {error}")
        return 1
    if panes_input_path and not panes_input_path.is_file():
        print("GENERATE-DDF RESULT: FAIL")
        print(f"- Panes input CSV not found: {panes_input_path}")
        return 1

    ref_dir = root / paths_cfg["reference"]
    ref_cdt = ref_dir / ref_cfg["reference_exported_cdt"]
    schema_path = ref_dir / ref_cfg["reference_exported_schema"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    category_ids, fields, seed_records = read_reference_cdt(ref_cdt, encoding)
    pane_records: list[dict[str, str]] = []
    gas_records: list[dict[str, str]] = []
    panes_ref = ref_cfg.get("panes_reference_exported_cdt")
    gas_ref = ref_cfg.get("window_gas_reference_exported_cdt")
    if panes_ref:
        panes_path = ref_dir / panes_ref
        if panes_path.is_file():
            pane_categories, pane_fields, pane_records = read_reference_cdt(panes_path, encoding)
        else:
            pane_categories = []
            pane_fields = []
    else:
        pane_categories = []
        pane_fields = []
    if gas_ref:
        gas_path = ref_dir / gas_ref
        if gas_path.is_file():
            _gas_categories, _gas_fields, gas_records = read_reference_cdt(gas_path, encoding)

    generated_pane_records: list[dict[str, str]] = []
    if panes_input_path:
        pane_fieldnames, pane_csv_rows = read_csv_rows(panes_input_path)
        pane_issues = validate_panes_csv(pane_csv_rows, pane_fieldnames)
        if pane_issues:
            print("GENERATE-DDF RESULT: FAIL")
            for issue in pane_issues:
                print(f"- {issue}")
            return 1
        if not pane_records or not pane_categories or not pane_fields:
            print("GENERATE-DDF RESULT: FAIL")
            print("- Cannot generate Panes.cdt because Panes reference data is missing.")
            return 1
        next_pane_id = max_numeric_id(pane_records) + 1
        pane_seed = dict(pane_records[0])
        for offset, row in enumerate(pane_csv_rows):
            generated_pane_records.append(
                apply_pane_csv_row_to_record(row, pane_fields, pane_seed, next_pane_id + offset)
            )
        pane_records_for_lookup = generated_pane_records
    else:
        pane_records_for_lookup = pane_records

    pane_lookup = build_component_lookup(pane_records_for_lookup)
    gas_lookup = build_component_lookup(gas_records)

    issues = validate_csv(csv_rows, fieldnames, pane_lookup, gas_lookup)
    if issues:
        print("GENERATE-DDF RESULT: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    output_subdir = args.output_subdir or output_subdir_name(input_path)
    output_dir = root / paths_cfg["output"] / output_subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_cdt = output_dir / "Glazing_generated.cdt"
    output_panes_cdt = output_dir / "Panes_generated.cdt"
    output_ddf = output_dir / "Glazing_generated.ddf"

    next_id = max_numeric_id(seed_records) + 1
    generated_records: list[dict[str, str]] = []
    warnings: list[str] = []
    for offset, row in enumerate(csv_rows):
        seed = choose_seed(seed_records, row)
        record, row_warnings = apply_csv_row_to_record(
            row,
            fields,
            seed,
            next_id + offset,
            pane_lookup,
            gas_lookup,
        )
        generated_records.append(record)
        warnings.extend(row_warnings)

    write_cdt(output_cdt, category_ids, fields, generated_records, encoding)
    if generated_pane_records:
        write_cdt(output_panes_cdt, pane_categories, pane_fields, generated_pane_records, encoding)
    validation_issues = validate_generated_cdt(output_cdt, schema, encoding)
    if generated_pane_records:
        panes_schema_path = ref_dir / ref_cfg["panes_reference_exported_schema"]
        panes_schema = json.loads(panes_schema_path.read_text(encoding="utf-8"))
        validation_issues.extend(validate_generated_cdt(output_panes_cdt, panes_schema, encoding))
    if validation_issues:
        print("GENERATE-DDF RESULT: FAIL")
        for issue in validation_issues:
            print(f"- {issue}")
        print(f"Generated CDT path: {output_cdt}")
        return 1

    package_entries = [(output_cdt, ddf_cfg["reference_package_cdt_entry_name"])]
    if generated_pane_records:
        package_entries.append((output_panes_cdt, ddf_cfg.get("reference_package_panes_entry_name", "Panes.cdt")))
    elif panes_ref and needs_companion_tables:
        panes_path = ref_dir / panes_ref
        if panes_path.is_file():
            package_entries.append((panes_path, ddf_cfg.get("reference_package_panes_entry_name", "Panes.cdt")))
    if gas_ref and needs_companion_tables:
        gas_path = ref_dir / gas_ref
        if gas_path.is_file():
            package_entries.append((gas_path, ddf_cfg.get("reference_package_window_gas_entry_name", "WindowGas.cdt")))
    package_ddf(package_entries, output_ddf)

    with zipfile.ZipFile(output_ddf) as archive:
        entry_names = archive.namelist()
    expected_entry_names = [internal_entry_name for _path, internal_entry_name in package_entries]
    missing_entry_names = [name for name in expected_entry_names if name not in entry_names]
    if missing_entry_names:
        print("GENERATE-DDF RESULT: FAIL")
        print(f"- DDF does not contain expected entries: {', '.join(missing_entry_names)}.")
        return 1

    print("GENERATED GLAZING SUMMARY")
    print(f"- Input CSV: {input_path}")
    print(f"- Records: {len(generated_records)}")
    print(f"- Id range: {generated_records[0]['Id']} -> {generated_records[-1]['Id']}")
    print(f"- Output CDT: {output_cdt}")
    if generated_pane_records:
        print(f"- Output Panes CDT: {output_panes_cdt}")
        print(f"- Panes input CSV: {panes_input_path}")
        print(f"- Panes records: {len(generated_pane_records)}")
    print(f"- Output DDF: {output_ddf}")
    print(f"- Internal DDF entries: {', '.join(entry_names)}")
    if warnings:
        print("")
        print("WARNINGS")
        for warning in warnings:
            print(f"- {warning}")
    print("")
    print("GENERATE-DDF RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
