"""Write contract CSVs and centrally run database and domain validation.

Input: a JSON array of row objects. ``required`` headers must be present with a
value; ``required_nullable`` headers must be present but may be blank; optional
headers may be omitted. Missing values are
represented by empty cells (Python callers may use ``None``; JSON may use
``null``), and literal text such as ``"None"`` remains text. The API writes
missing values as empty CSV cells. Consolidate daily state observations to means
and additive event amounts to sums upstream; duplicate logical keys are rejected
here and the API does not calculate those aggregates. Fields marked
``required_nullable`` must remain in the input schema but may contain a blank
value. Soil-layer top and bottom boundaries must both be supplied or both be
blank, and every event phase must provide a date, phenology time, or event time.
Observation rows route to a timeseries table only when ``date_of_measurement``
is non-blank; otherwise they belong in the corresponding summary table.
``group_plot_season_ids`` is normalized to a trimmed, duplicate-free,
lexicographically sorted semicolon list and must include the row's primary
``plot_season_id`` when that field exists. Package validation checks every list
member against ``Plot_seasons``. Structural checks live in
``database_validation.py``; agronomic checks live in ``domain_validation.py``.
"""
import argparse
import csv
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from database_validation import (ContractValidationError, validate_database_dictionary_rows,
                                 validate_database_foreign_keys, validate_database_headers,
                                 validate_database_rows)
from domain_validation import (raise_domain_errors, validate_package_context,
                               validate_package_domains, validate_row_domains)

ROOT = Path(__file__).resolve().parent
CONTRACT_VERSION = "v8"
DICTIONARY_HEADERS = [
    'source_dataset', 'source_variable_name', 'source_variable_code',
    'source_definition', 'source_unit', 'target_table',
    'target_variable_name', 'target_code_display', 'target_definition',
    'target_unit', 'mapping_scheme', 'mapping_status', 'evidence',
    'error_type', 'error_example',
]
MAPPING_STATUSES = {
    'confirmed', 'review', 'mapping_review', 'unresolved',
    'not_observed', 'aggregation_review', 'conditional',
}

# Explicit code sources. Add a mapping here when a code vocabulary is approved.
# Values are (file relative to scheme/, value column). Unmapped code fields fail.
CODE_SOURCES = {
    ("Irrigation_treatments", "irrig_applied", "IRRIG"): ("Management_codes.csv", "Code"),
    ("Irrigation_events", "irrig_applied", "IRRIG"): ("Management_codes.csv", "Code"),
    ("Organic_material_application_events", "organic_material", "OMCD"): ("Management_codes.csv", "Code"),
    ("Mulch_events", "mulch_color", "MLCOL"): ("Management_codes.csv", "Code"),
    ("Chemical_application_event", "chemical_applic_material", "CHCD"): ("Management_codes.csv", "Code"),
    ("Tillage_event", "tillage_implement", "TIIMP"): ("Management_codes.csv", "Code"),
    ("Harvest_events", "harvest_operat_component", "HACOM"): ("Management_codes.csv", "Code"),
    ("Harvest_events", "harv_operat_size_categor", "HASIZ"): ("Management_codes.csv", "Code"),
    ("Planting_events", "planting_material", "PLMA"): ("Management_codes.csv", "Code"),
    ("Planting_events", "planting_method", "PLME"): ("Management_codes.csv", "Code"),
    ("Planting_events", "planting_distribution", "PLDS"): ("Management_codes.csv", "Code"),
    ("Plots", "drainage_type", "FL_DRNTYPE"): ("Management_codes.csv", "Code"),
    ("Genotypes", "crop_id", "CRID"): ("Crop_codes.csv", "Crop_code"),
    ("Chemical_application_event", "chemical_applic_target", "CH_TARGETS"): ("Pest_codes.csv", "Pest_code"),
    ("Weather_stations", "flag_for_summary_data", "FLAGA"): ("Other_codes.csv", "Code"),
    ("Soil_profiles", "soil_drainage_class", "DRAINAGE"): ("Other_codes.csv", "Code"),
    ("Soil_profiles", "soil_texture", "SLTX"): ("Other_codes.csv", "Code"),
    ("Plots", "field_landscape_position", "FL_LAND"): ("Other_codes.csv", "Code"),
    ("Plots", "field_soil_texture", "FL_SLTX"): ("Other_codes.csv", "Code"),
    # Candidate lists extracted from the frozen ICASA workbook. These are
    # validation vocabularies; they do not infer crop or site applicability.
    ("Soil_layer_observations_summary", "master_horizon", "SLMH"): ("ICASA_master_horizon_options.csv", "Code"),
    ("Soil_layer_observations_timeseries", "master_horizon", "SLMH"): ("ICASA_master_horizon_options.csv", "Code"),
    ("Soil_profile_layers", "master_horizon", "SLMH"): ("ICASA_master_horizon_options.csv", "Code"),
    ("Crop_observations_summary", "growth_stage_BBCH", "GSTBD"): ("BBCH_codes.csv", "Code"),
    ("Crop_observations_timeseries", "growth_stage_BBCH", "GSTBD"): ("BBCH_codes.csv", "Code"),
    ("Irrigation_events", "irrigation_operation", "IROP"): ("ICASA_irrigation_operation_options.csv", "Code"),
    ("Auto_iIrrigation_events", "method_auto_applications", "IAME"): ("ICASA_application_method_options.csv", "Code"),
    ("Irrigation_events", "method_auto_applications", "IAME"): ("ICASA_application_method_options.csv", "Code"),
    ("Fertilization_treatments", "fert_applied", "FERTILIZER"): ("ICASA_logical_options.csv", "Code"),
    ("Fertilization_treatments", "fertiliz_code_other_elem", "FEOCD_TOT"): ("ICASA_element_options.csv", "Code"),
    ("Fertilization_events", "fertilizer_applic_method", "FEACD"): ("ICASA_application_method_options.csv", "Code"),
    ("Fertilization_events", "fertiliz_code_other_elem", "FEOCD"): ("ICASA_element_options.csv", "Code"),
    ("Organic_material_application_events", "org_material_applic_meth", "OMACD"): ("ICASA_application_method_options.csv", "Code"),
    ("Mulch_events", "mulch_type", "MLTP"): ("ICASA_mulch_type_options.csv", "Code"),
    ("Chemical_application_event", "chemical_applic_method", "CHACD"): ("ICASA_application_method_options.csv", "Code"),
    ("Tillage_event", "tillage_practice", "TI_PRACTICE"): ("ICASA_tillage_practice_options.csv", "Code"),
    ("Environmental_modification", "environ_mod_code_daylen", "ECDYL"): ("ICASA_envmodif_code_options.csv", "Code"),
    ("Environmental_modification", "environ_mod_code_radiat", "ECRAD"): ("ICASA_envmodif_code_options.csv", "Code"),
    ("Environmental_modification", "environ_mod_code_tmax", "ECMAX"): ("ICASA_envmodif_code_options.csv", "Code"),
    ("Environmental_modification", "environ_mod_code_tmin", "ECMIN"): ("ICASA_envmodif_code_options.csv", "Code"),
    ("Environmental_modification", "environ_modif_code_rain", "ECRAI"): ("ICASA_envmodif_code_options.csv", "Code"),
    ("Environmental_modification", "environ_modif_code_CO2", "ECCO2"): ("ICASA_envmodif_code_options.csv", "Code"),
    ("Environmental_modification", "environ_mod_code_dewpt", "ECDEW"): ("ICASA_envmodif_code_options.csv", "Code"),
    ("Environmental_modification", "environ_modif_code_wind", "ECWND"): ("ICASA_envmodif_code_options.csv", "Code"),
    ("Harvest_events", "harvest_method", "HARM"): ("ICASA_harvest_method_options.csv", "Code"),
    ("Initial_conditions", "residue_nature_prev_crop", "ICPCR"): ("ICASA_crop_options.csv", "Code"),
    ("Plots", "harvest_method_plot", "PLTHM"): ("ICASA_harvest_method_options.csv", "Code"),
    ("Plots", "field_history", "FL_HIST"): ("ICASA_field_history_options.csv", "Code"),
}

OBSERVATION_TABLES = {
    'Soil_layer_observations': (
        'Soil_layer_observations_summary',
        'Soil_layer_observations_timeseries',
    ),
    'Crop_observations': (
        'Crop_observations_summary',
        'Crop_observations_timeseries',
    ),
    'Other_observations': (
        'Other_observations_summary',
        'Other_observations_timeseries',
    ),
}

# Event-time fields keep their source-specific names, but share the v8 vocabularies.
for _table, _variable, _display in (
    ("Irrigation_events", "irrigation_phenology_time", "IRRPHENT"),
    ("Auto_iIrrigation_events", "auto_irrig_phenology_time", "AUTOIRRP"),
    ("Auto_iIrrigation_events", "auto_irrig_end_phenology_time", "AU_AIE3"),
    ("Fertilization_events", "fertilization_phenology_time", "FERTPHEN"),
    ("Organic_material_application_events", "org_material_applic_phenology_time", "OR_OME2"),
    ("Mulch_events", "mulch_applic_phenology_time", "MULAPPPH"),
    ("Mulch_events", "mulch_removal_phenology_time", "MULREMOV"),
    ("Chemical_application_event", "chemical_applic_phenology_time", "CHEMAPPP"),
    ("Tillage_event", "tillage_phenology_time", "TILPHENT"),
    ("Environmental_modification", "environ_modificat_phenology_time", "ENVMODPH"),
    ("Harvest_events", "harvest_phenology_time", "HARVPHEN"),
):
    CODE_SOURCES[(_table, _variable, _display)] = ("BBCH_codes.csv", "Code")
for _table, _variable, _display in (
    ("Irrigation_events", "irrigation_event_time", "IRREVETI"),
    ("Auto_iIrrigation_events", "auto_irrig_event_time", "AUTOIRRE"),
    ("Auto_iIrrigation_events", "auto_irrig_end_event_time", "AU_AIE4"),
    ("Fertilization_events", "fertilization_event_time", "FERTEVET"),
    ("Organic_material_application_events", "org_material_applic_event_time", "OR_OME3"),
    ("Mulch_events", "mulch_applic_event_time", "MULAPPEV"),
    ("Mulch_events", "mulch_removal_event_time", "MULRE_MU"),
    ("Chemical_application_event", "chemical_applic_event_time", "CHEMAPPE"),
    ("Tillage_event", "tillage_event_time", "TILEVETI"),
    ("Environmental_modification", "environ_modificat_event_time", "ENVMODEV"),
    ("Harvest_events", "harvest_event_time", "HARVEVET"),
):
    CODE_SOURCES[(_table, _variable, _display)] = ("Event_time_codes.csv", "Code")


def contract(table):
    with (ROOT / 'scheme/variables.csv').open(newline='', encoding='utf-8-sig') as f:
        fields = [r for r in csv.DictReader(f) if r['Sheet_name'] == table]
    if not fields:
        raise ValueError(f'Unknown table: {table}')
    headers = [r['Target_column'] for r in fields]
    if len(set(headers)) != len(headers):
        raise ValueError(f'Ambiguous field identities in {table}')
    with (ROOT / 'scheme/table.csv').open(newline='', encoding='utf-8-sig') as f:
        meta = next(r for r in csv.DictReader(f) if r['Table_name'] == table)
    keys = []
    for name in meta['Primary_key'].split(' + '):
        matches = [h for h, r in zip(headers, fields) if r['Variable_name'] == name]
        if len(matches) != 1:
            raise ValueError(f'Ambiguous or missing key: {table}.{name}')
        keys.extend(matches)
    return fields, headers, keys


def route_observation_rows(table, rows):
    """Route solely by non-blank date_of_measurement; phenological value dates do not route rows."""
    try:
        summary_table, timeseries_table = OBSERVATION_TABLES[table]
    except KeyError as exc:
        raise ValueError(f'Unknown observation table: {table}') from exc
    routed = {summary_table: [], timeseries_table: []}
    for row in rows:
        value = row.get('date_of_measurement', '')
        if value is not None and str(value).strip():
            routed[timeseries_table].append(row)
        else:
            summary_row = dict(row)
            summary_row.pop('date_of_measurement', None)
            routed[summary_table].append(summary_row)
    return routed


def validate_rows(table, rows):
    """Run database-structure validation, then deterministic domain validation."""
    fields, headers, keys = contract(table)
    _, clean = validate_database_rows(table, rows, fields, headers, keys, code_options())
    raise_domain_errors(validate_row_domains(table, clean, fields, headers))
    return headers, clean


def code_options():
    """Return codes from explicit sources; unmapped code fields are rejected."""
    options = {}
    for source_key, (filename, column) in CODE_SOURCES.items():
        table, variable, display = source_key
        path = ROOT / 'scheme' / filename
        with path.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'Variable_name' in (reader.fieldnames or []):
                    # A code list row without an owning variable is metadata,
                    # not a wildcard for every target field.
                    variables = {x.strip() for x in (row.get('Variable_name') or '').split(';') if x.strip()}
                    if variable not in variables:
                        continue
                if row.get('Code_display') and filename != 'column_code_option.csv':
                    displays = {x.strip() for x in row['Code_display'].split(',')}
                    if display not in displays:
                        continue
                if row.get(column):
                    options.setdefault(source_key, set()).add(row[column])
    return options


def validate_contract_integrity():
    """Fail fast when table, variable, or code-source contracts drift."""
    table_path = ROOT / 'scheme/table.csv'
    variables_path = ROOT / 'scheme/variables.csv'
    errors = []
    with table_path.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    table_header = rows[0] if rows else []
    table_rows = rows[1:]
    if any(len(row) != 6 for row in table_rows):
        errors.append('table.csv: every data row must contain exactly six columns')
    if table_header == ['Table_name', 'Description', 'Primary_key', 'Foreign_keys',
                        'Accepts', 'Rejects']:
        metadata = [dict(zip(table_header, row)) for row in table_rows if len(row) == 6]
    else:
        metadata = []
    if table_header != ['Table_name', 'Description', 'Primary_key', 'Foreign_keys',
                        'Accepts', 'Rejects']:
        errors.append('table.csv: expected six-column header')
    if len({row[0] for row in table_rows if row}) != len(table_rows):
        errors.append('table.csv: Table_name values must be unique')
    with variables_path.open(newline='', encoding='utf-8-sig') as f:
        variable_reader = csv.reader(f)
        variable_rows = list(variable_reader)
    variable_header = variable_rows[0] if variable_rows else []
    if any(len(row) != len(variable_header) for row in variable_rows[1:]):
        errors.append('variables.csv: every data row must contain exactly the header column count')
    variables = [dict(zip(variable_header, row)) for row in variable_rows[1:]
                 if len(row) == len(variable_header)]

    icasa_path = ROOT / 'scheme/icasa_variable.csv'
    icasa_by_uid = {}
    if not icasa_path.exists():
        errors.append('icasa_variable.csv: source contract is missing')
    else:
        with icasa_path.open(newline='', encoding='utf-8-sig') as f:
            icasa_rows = list(csv.DictReader(f))
        icasa_by_uid = {row.get('var_uid', '').strip(): row for row in icasa_rows
                        if row.get('var_uid', '').strip()}
        for row in variables:
            uid = row.get('ICASA_var_uid', '').strip()
            if not uid:
                continue
            source = icasa_by_uid.get(uid)
            if source is None:
                errors.append(
                    f"variables.csv: unknown ICASA_var_uid {uid!r} for "
                    f"{row.get('Sheet_name', '')}.{row.get('Variable_name', '')}"
                )
            elif row.get('Variable_name', '') != source.get('Variable_Name', '').strip():
                errors.append(
                    f"variables.csv: {row.get('Sheet_name', '')}.{row.get('Variable_name', '')} "
                    f"does not preserve ICASA variable {source.get('Variable_Name', '').strip()!r} "
                    f"for UID {uid}"
                )

    required_variable_columns = {
        'Sheet_name', 'Variable_name', 'Target_column', 'Requirement', 'PK',
        'FK_Reference', 'Unit_or_type', 'Code_Display',
    }
    if variables and not required_variable_columns <= set(variables[0]):
        errors.append('variables.csv: missing required contract columns')

    table_names = {row.get('Table_name', '') for row in metadata}
    variables_by_table = {}
    for row in variables:
        table = row.get('Sheet_name', '')
        variables_by_table.setdefault(table, []).append(row)
        for column in ('Variable_name', 'Target_column'):
            value = row.get(column, '')
            if value != value.strip():
                errors.append(f'variables.csv: {column} has surrounding whitespace: {value!r}')
        if not row.get('Target_column', '').strip():
            errors.append(f'variables.csv: missing Target_column for {table}.{row.get("Variable_name", "")}')

    if table_names != set(variables_by_table):
        errors.append(
            f'table/variables table mismatch: table-only={sorted(table_names - set(variables_by_table))}, '
            f'variables-only={sorted(set(variables_by_table) - table_names)}'
        )

    for meta in metadata:
        table = meta.get('Table_name', '')
        rows = variables_by_table.get(table, [])
        target_columns = [row.get('Target_column', '') for row in rows]
        if len(target_columns) != len(set(target_columns)):
            errors.append(f'{table}: duplicate Target_column values')
        variable_pks = [row['Variable_name'] for row in rows if row.get('PK') == 'yes']
        declared_pks = [name.strip() for name in meta.get('Primary_key', '').split('+') if name.strip()]
        if variable_pks != declared_pks:
            errors.append(
                f'{table}: Primary_key disagrees with variables.csv PK flags '
                f'({declared_pks!r} != {variable_pks!r})'
            )

        variable_fks = sorted(
            (row['Variable_name'], row['FK_Reference'])
            for row in rows if row.get('FK_Reference', '').strip()
        )
        table_fks = []
        for relation in filter(None, (x.strip() for x in meta.get('Foreign_keys', '').split(';'))):
            try:
                child, target = [x.strip() for x in relation.split('->', 1)]
            except ValueError:
                errors.append(f"{table}: malformed foreign-key relation {relation!r}")
                continue
            table_fks.append((child, target))
        if sorted(table_fks) != variable_fks:
            errors.append(
                f'{table}: Foreign_keys disagrees with variables.csv FK_Reference '
                f'({sorted(table_fks)!r} != {variable_fks!r})'
            )

    primary_keys = {
        meta['Table_name']: {name.strip() for name in meta['Primary_key'].split('+') if name.strip()}
        for meta in metadata
    }
    for meta in metadata:
        for relation in filter(None, (x.strip() for x in meta.get('Foreign_keys', '').split(';'))):
            try:
                _, target = [x.strip() for x in relation.split('->', 1)]
                parent_table, parent_column = [x.strip() for x in target.split('.', 1)]
            except ValueError:
                errors.append(f"{meta['Table_name']}: malformed foreign-key relation {relation!r}")
                continue
            if parent_table not in table_names:
                errors.append(f"{meta['Table_name']}: foreign-key parent table {parent_table!r} is undefined")
            elif parent_column not in primary_keys.get(parent_table, set()):
                errors.append(
                    f"{meta['Table_name']}: foreign-key target {parent_table}.{parent_column} "
                    'is not declared as a parent primary-key field'
                )

    code_fields = {
        (row['Sheet_name'], row['Variable_name'], row['Code_Display'])
        for row in variables if row.get('Unit_or_type') == 'code'
    }
    mapped_code_fields = set(CODE_SOURCES)
    if code_fields != mapped_code_fields:
        errors.append(
            f'code-source coverage mismatch: unmapped={sorted(code_fields - mapped_code_fields)}, '
            f'extra={sorted(mapped_code_fields - code_fields)}'
        )
    for filename, column in CODE_SOURCES.values():
        path = ROOT / 'scheme' / filename
        if not path.exists():
            errors.append(f'missing code source: {filename}')
            continue
        with path.open(newline='', encoding='utf-8-sig') as f:
            if column not in (csv.DictReader(f).fieldnames or []):
                errors.append(f'{filename}: missing code column {column}')
    available_code_options = code_options()
    for source_key in CODE_SOURCES:
        values = available_code_options.get(source_key, set())
        if not values:
            errors.append(f'code source has no values after field scoping: {source_key!r}')

    if errors:
        raise ContractValidationError('\n'.join(errors), [{'message': e} for e in errors])
    return True


validate_contract_integrity()


def validate_dictionary_rows(rows):
    """Validate source-to-v8 variable definitions through the database layer."""
    variables_path = ROOT / 'scheme/variables.csv'
    with variables_path.open(newline='', encoding='utf-8-sig') as f:
        variables = list(csv.DictReader(f))
    identities = {
        (r['Sheet_name'], r['Variable_name'], r['Code_Display']): r
        for r in variables
    }
    return validate_database_dictionary_rows(rows, DICTIONARY_HEADERS, identities, MAPPING_STATUSES)


def write_dictionary(rows, output):
    """Write a validated source-to-v8 dictionary CSV."""
    headers, clean = validate_dictionary_rows(rows)
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Output must be outside the contract directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', newline='', encoding='utf-8', dir=output.parent, delete=False) as f:
            temporary = Path(f.name)
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(clean)
        os.replace(temporary, output)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return len(clean)


def write_table(table, rows, output, mode='replace'):
    """Write a validated batch; mode is replace, append, or merge."""
    supplied_headers = set()
    for row in rows:
        supplied_headers.update(row)
    headers, clean = validate_rows(table, rows)
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Output must be outside the contract directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    if mode not in {'replace', 'append', 'merge'}:
        raise ValueError('mode must be replace, append, or merge')
    if mode != 'replace' and output.exists():
        with output.open(newline='', encoding='utf-8-sig') as f:
            existing_input = list(csv.DictReader(f))
        for row in existing_input:
            supplied_headers.update(row)
        _, existing = validate_rows(table, existing_input)
        if mode == 'append':
            rows = existing + clean
        else:
            _, _, keys = contract(table)
            by_key = {tuple(r.get(k, '') for k in keys): r for r in existing}
            conflicts = []
            for row in clean:
                key = tuple(row[k] for k in keys)
                if key in by_key and by_key[key] != row:
                    conflicts.append({'table': table, 'logical_key': list(key), 'action': 'resolve_upstream'})
                else:
                    by_key[key] = row
            if conflicts:
                raise ContractValidationError(
                    '\n'.join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in conflicts),
                    conflicts,
                )
            rows = list(by_key.values())
        headers, clean = validate_rows(table, rows)
    fields, contract_headers, _ = contract(table)
    requirements = {h: field['Requirement'] for h, field in zip(contract_headers, fields)}
    required_headers = {h for h, requirement in requirements.items()
                        if requirement in {'required', 'required_nullable'}}
    used_optional = {
        h for h, requirement in requirements.items()
        if requirement == 'optional'
        and any(str(row.get(h, '') or '').strip() for row in clean)
    }
    headers = [h for h in contract_headers if h in required_headers or h in used_optional]
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', newline='', encoding='utf-8', dir=output.parent, delete=False) as f:
            temporary = Path(f.name)
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(clean)
        os.replace(temporary, output)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return len(clean)


def validate_package(directory, complete=False):
    """Run both validation layers over supplied CSV files and their relationships."""
    directory = Path(directory)
    if not directory.is_dir():
        diagnostic = {
            'directory': str(directory),
            'error': 'missing_package_directory',
        }
        raise ContractValidationError(
            f"Package directory does not exist or is not a directory: {directory}",
            [diagnostic],
        )
    tables = {}
    with (ROOT / 'scheme/table.csv').open(newline='', encoding='utf-8-sig') as f:
        metadata = list(csv.DictReader(f))
    if complete:
        allowed = {f"{m['Table_name']}.csv" for m in metadata}
        unknown = sorted(
            p.name for p in directory.iterdir()
            if p.is_file() and p.name != '.DS_Store' and p.name not in allowed
        )
        if unknown:
            raise ContractValidationError(
                json.dumps({'unknown_files': unknown}, ensure_ascii=False, sort_keys=True),
                [{'unknown_files': unknown}],
            )
    missing = []
    for meta in metadata:
        path = directory / f"{meta['Table_name']}.csv"
        if path.exists():
            fields, headers, _ = contract(meta['Table_name'])
            with path.open(newline='', encoding='utf-8-sig') as f:
                actual_headers = next(csv.reader(f), [])
            validate_database_headers(meta['Table_name'], actual_headers, fields, headers)
            with path.open(newline='', encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            _, clean = validate_rows(meta['Table_name'], rows)
            tables[meta['Table_name']] = clean
        elif complete:
            missing.append(meta['Table_name'])
    if missing:
        raise ContractValidationError(
            json.dumps({'missing_tables': missing}, ensure_ascii=False, sort_keys=True),
            [{'missing_tables': missing}],
        )
    errors = validate_database_foreign_keys(tables, metadata, contract)
    errors.extend(validate_package_context(tables))
    errors.extend(validate_package_domains(tables))
    if errors:
        raise ContractValidationError('\n'.join(errors), [{'message': e} for e in errors])
    return True


def create_templates():
    destination = ROOT / 'template'
    destination.mkdir(exist_ok=True)
    with (ROOT / 'scheme/table.csv').open(newline='', encoding='utf-8-sig') as f:
        tables = [r['Table_name'] for r in csv.DictReader(f)]
    for table in tables:
        _, headers, _ = contract(table)
        with (destination / f'{table}.csv').open('w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(headers)
    with (destination / 'dictionary.csv').open('w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(DICTIONARY_HEADERS)
    return len(tables)


def check_templates():
    """Check that generated template headers still match the current contract."""
    errors = []
    with (ROOT / 'scheme/table.csv').open(newline='', encoding='utf-8-sig') as f:
        tables = [r['Table_name'] for r in csv.DictReader(f)]
    for table in tables:
        path = ROOT / 'template' / f'{table}.csv'
        if not path.exists():
            errors.append({'table': table, 'error': 'missing_template'})
            continue
        with path.open(newline='', encoding='utf-8-sig') as f:
            actual = next(csv.reader(f), [])
        _, expected, _ = contract(table)
        if actual != expected:
            errors.append({'table': table, 'error': 'header_mismatch',
                           'expected': expected, 'actual': actual})
    dictionary_path = ROOT / 'template' / 'dictionary.csv'
    if not dictionary_path.exists():
        errors.append({'table': 'dictionary', 'error': 'missing_template'})
    else:
        with dictionary_path.open(newline='', encoding='utf-8-sig') as f:
            actual = next(csv.reader(f), [])
        if actual != DICTIONARY_HEADERS:
            errors.append({'table': 'dictionary', 'error': 'header_mismatch',
                           'expected': DICTIONARY_HEADERS, 'actual': actual})
    if errors:
        raise ContractValidationError('\n'.join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in errors), errors)
    return len(tables)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--templates', action='store_true')
    parser.add_argument('--table')
    parser.add_argument('--input', type=Path, help='JSON array of row objects')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--mode', choices=('replace', 'append', 'merge'), default='replace')
    parser.add_argument('--validate-package', type=Path)
    parser.add_argument('--complete', action='store_true', help='require every v8 table in package validation')
    parser.add_argument('--check-templates', action='store_true')
    args = parser.parse_args()
    if args.check_templates:
        print(f'Checked {check_templates()} templates')
    elif args.validate_package:
        validate_package(args.validate_package, complete=args.complete)
        print('Package is valid' if args.complete else
              'Package is valid for the supplied partial tables')
    elif args.templates:
        print(f'Created {create_templates()} templates')
    else:
        if not all((args.table, args.input, args.output)):
            parser.error('--table, --input and --output are required')
        data = json.loads(args.input.read_text(encoding='utf-8'))
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            parser.error('Input must be a JSON array of row objects')
        print(f'Wrote {write_table(args.table, data, args.output, args.mode)} rows')
