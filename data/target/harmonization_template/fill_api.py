"""Write contract CSVs and centrally run database and domain validation.

Input: a JSON array of row objects. Writers allow partial rows and supply blank
cells for missing fields. Supplied values must have valid types and formats.
Explicit validators require values for ``required`` fields and present headers
for ``required_nullable`` fields; optional headers may be omitted. Missing values are
represented by empty cells (Python callers may use ``None``; JSON may use
``null``), and literal text such as ``"None"`` remains text. The API writes
missing values as empty CSV cells. Consolidate repeated observations and events
within each table's declared key upstream; explicit validation rejects duplicate
logical keys and the API does not calculate aggregates. Partial writes preserve
unfinished records rather than deduplicating them. Merge requires complete,
unique keys. Full validation requires soil-layer top and bottom together and a
date, phenology time or event time for each event phase.
Observation rows route to a timeseries table only when ``date_of_measurement``
is non-blank; otherwise they belong in the corresponding summary table.
``group_plot_season_ids`` is normalized to a trimmed, duplicate-free,
lexicographically sorted semicolon list and must include the row's primary
``plot_season_id`` when that field exists. Package validation checks every list
member against ``Plot_seasons``. Final package validation additionally rejects
parent records not used by any plot-season context; ordinary writes and package
validation allow these intermediate records. Structural checks live in
``database_validation.py``; agronomic checks live in ``domain_validation.py``.
Storage is blank for direct values or lists source fields as Table.Target_column.
Foreign keys retain IDs; other reference fields accept only
obs:<source_table>?<complete primary-key query>#<encoded column>.
Writes accept unresolved references; --final resolves and checks them.
Final checks also require complete shared observation copies with equal data fields.
--export-configurations exports current physical values to a separate new
--output directory. Observation rows use their existing complete primary keys.
"""
import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

from harmonization_template.database_validation import (ContractValidationError, validate_database_dictionary_rows,
                                 validate_database_foreign_keys, validate_database_headers,
                                 validate_database_rows, validate_database_usage,
                                 validate_shared_observations, storage_sources)
from harmonization_template.domain_validation import (raise_domain_errors, validate_package_context,
                               validate_package_domains, validate_row_domains)
from harmonization_template.observation_references import (CONFIGURATION_TABLES, resolve_configurations,
                                                              same_variable)

ROOT = Path(__file__).resolve().parent
CONTRACT_VERSION = "target_template"

# Explicit code sources. Add a mapping here when a code vocabulary is approved.
# Values are (file relative to scheme/, value column). Unmapped code fields fail.
CODE_SOURCES = {
    ("Dictionary", "mapping_status", ""): ("Dictionary_mapping_status_codes.csv", "Code"),
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
    ("Soil_profiles", "soil_drainage_class", "DRAINAGE"): ("Other_codes.csv", "Code"),
    ("Soil_profiles", "soil_texture", "SLTX"): ("Other_codes.csv", "Code"),
    ("Plots", "field_landscape_position", "FL_LAND"): ("Other_codes.csv", "Code"),
    ("Plots", "field_soil_texture", "FL_SLTX"): ("Other_codes.csv", "Code"),
    # Canonical code tables scope choices by Variable_name; supplementary
    # options cover vocabularies without an original encoded list.
    ("Soil_profile_layers", "master_horizon", "SLMH"): ("ICASA_master_horizon_options.csv", "Code"),
    ("Soil_layer_observations_summary", "master_horizon", "SLMH"): ("ICASA_master_horizon_options.csv", "Code"),
    ("Soil_layer_observations_timeseries", "master_horizon", "SLMH"): ("ICASA_master_horizon_options.csv", "Code"),
    ("Crop_observations_summary", "growth_stage_BBCH", "GSTBD"): ("BBCH_codes.csv", "Code"),
    ("Crop_observations_timeseries", "growth_stage_BBCH", "GSTBD"): ("BBCH_codes.csv", "Code"),
    ("Irrigation_events", "irrigation_operation", "IROP"): ("Management_codes.csv", "Code"),
    ("Auto_iIrrigation_events", "method_auto_applications", "IAME"): ("Management_codes.csv", "Code"),
    ("Irrigation_events", "method_auto_applications", "IAME"): ("Management_codes.csv", "Code"),
    ("Fertilization_treatments", "fert_applied", "FERTILIZER"): ("ICASA_logical_options.csv", "Code"),
    ("Fertilization_treatments", "fertiliz_code_other_elem", "FEOCD_TOT"): ("Management_codes.csv", "Code"),
    ("Fertilization_events", "fertilizer_applic_method", "FEACD"): ("Management_codes.csv", "Code"),
    ("Fertilization_events", "fertiliz_code_other_elem", "FEOCD"): ("Management_codes.csv", "Code"),
    ("Organic_material_application_events", "org_material_applic_meth", "OMACD"): ("Management_codes.csv", "Code"),
    ("Mulch_events", "mulch_type", "MLTP"): ("Management_codes.csv", "Code"),
    ("Chemical_application_event", "chemical_applic_method", "CHACD"): ("Management_codes.csv", "Code"),
    ("Tillage_event", "tillage_practice", "TI_PRACTICE"): ("ICASA_tillage_practice_options.csv", "Code"),
    ("Environmental_modification", "environ_mod_code_daylen", "ECDYL"): ("Management_codes.csv", "Code"),
    ("Environmental_modification", "environ_mod_code_radiat", "ECRAD"): ("Management_codes.csv", "Code"),
    ("Environmental_modification", "environ_mod_code_tmax", "ECMAX"): ("Management_codes.csv", "Code"),
    ("Environmental_modification", "environ_mod_code_tmin", "ECMIN"): ("Management_codes.csv", "Code"),
    ("Environmental_modification", "environ_modif_code_rain", "ECRAI"): ("Management_codes.csv", "Code"),
    ("Environmental_modification", "environ_modif_code_CO2", "ECCO2"): ("Management_codes.csv", "Code"),
    ("Environmental_modification", "environ_mod_code_dewpt", "ECDEW"): ("Management_codes.csv", "Code"),
    ("Environmental_modification", "environ_modif_code_wind", "ECWND"): ("Management_codes.csv", "Code"),
    ("Harvest_events", "harvest_method", "HARM"): ("Management_codes.csv", "Code"),
    ("Initial_conditions", "residue_nature_prev_crop", "ICPCR"): ('Crop_codes.csv', 'Crop_code'),
    **{(table, name, code): source
       for table in ('Soil_layer_observations_summary', 'Soil_layer_observations_timeseries')
       for name, code, source in (
           ('residue_nature_prev_crop', 'ICPCR', ('Crop_codes.csv', 'Crop_code')),
           ('soil_drainage_class', 'DRAINAGE', ('Other_codes.csv', 'Code')),
           ('soil_texture', 'SLTX', ('Other_codes.csv', 'Code')))},
    ("Plots", "harvest_method_plot", "PLTHM"): ("Management_codes.csv", "Code"),
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

# Event-time fields keep their source-specific names, but share the target_template vocabularies.
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
    if table == 'Dictionary':
        return fields, headers, []
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


def storage_errors(variables, *, partial=False):
    """Check declared reference sources without selecting records for the caller."""
    fields = {(field['Sheet_name'], field['Target_column']): field for field in variables}
    errors = []
    for field in variables:
        label = f"{field['Sheet_name']}.{field['Target_column']}"
        try:
            sources = storage_sources(field)
        except ValueError as error:
            errors.append(f'{label}: {error}')
            continue
        foreign = field.get('FK_Reference', '')
        if foreign:
            parent_table, parent_name = foreign.split('.', 1)
            parents = [value for value in variables
                       if value['Sheet_name'] == parent_table and value['Variable_name'] == parent_name]
            expected = [(parent_table, parents[0]['Target_column'])] if len(parents) == 1 else []
            if not expected or sources != expected:
                errors.append(f'{label}: Storage must match its foreign-key source')
        elif field['Sheet_name'] in CONFIGURATION_TABLES and not field.get('Role') and not sources:
            errors.append(f'{label}: configuration properties require a declared observation source')
        for source in sources:
            target = fields.get(source)
            if target is None:
                errors.append(f'{label}: unknown Storage source {source[0]}.{source[1]}')
            elif source[0] == field['Sheet_name'] or target.get('Storage'):
                errors.append(f'{label}: Storage source must be a directly stored field in another table')
            elif foreign:
                if target['Data_type'] != field['Data_type']:
                    errors.append(f'{label}: foreign-key source data type differs')
            else:
                if not partial or field['Description'] and field['Unit_or_type']:
                    matches = same_variable(field, target)
                else:
                    matches = field['Data_type'] == target['Data_type'] and (
                        not field['Unit_or_type'] or field['Unit_or_type'] == target['Unit_or_type'])
                if target.get('Role') or not matches:
                    errors.append(f'{label}: Storage source must represent the same data variable, unit and type')
    return errors


def validate_rows(table, rows, *, dictionary=()):
    """Validate structure, types, reviewed numeric bounds, and domain relationships."""
    if table == 'Dictionary':
        return validate_dictionary_rows(rows)
    lookup = package_contract(dictionary) if dictionary else contract
    return _validate_data_rows(table, rows, lookup, package_code_options(dictionary, lookup))


def _validate_data_rows(table, rows, lookup, options, *, partial=False):
    fields, headers, keys = lookup(table)
    _, clean = validate_database_rows(table, rows, fields, headers, keys, options, partial=partial)
    raise_domain_errors(validate_row_domains(table, clean, fields, headers, partial=partial))
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
                if row.get('Code_display'):
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
    icasa_rows = []
    if not icasa_path.exists():
        errors.append('icasa_variable.csv: source contract is missing')
    else:
        with icasa_path.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            required = {'var_uid', 'Variable_Name', 'Description', 'Code_Display',
                        'Unit_or_type', 'Data_type', 'Target_Sheet', 'Requirement',
                        'adapt_operation', 'Decision_reason'}
            if not required <= set(reader.fieldnames or []):
                errors.append('icasa_variable.csv: missing required catalog columns')
            raw_rows = list(reader)
            if any(None in row or None in row.values() for row in raw_rows):
                errors.append('icasa_variable.csv: row column counts disagree with the header')
            icasa_rows = [row for row in raw_rows if None not in row and None not in row.values()]
        uids = [row.get('var_uid', '').strip() for row in icasa_rows]
        if not all(uids) or len(uids) != len(set(uids)):
            errors.append('icasa_variable.csv: var_uid must be nonempty and unique')
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
            elif row.get('Code_Display', '') != source.get('Code_Display', ''):
                errors.append(f'variables.csv: Code_Display disagrees with source UID {uid}')

    required_variable_columns = {
        'Sheet_name', 'Variable_name', 'Target_column', 'Requirement', 'PK',
        'FK_Reference', 'Unit_or_type', 'Code_Display', 'ICASA_var_uid',
        'Description', 'Supplementary_information', 'Data_type', 'Storage',
    }
    if variables and not required_variable_columns <= set(variables[0]):
        errors.append('variables.csv: missing required contract columns')

    table_names = {row.get('Table_name', '') for row in metadata}
    variables_by_table = {}
    variables_by_uid = {}
    for row in variables:
        table = row.get('Sheet_name', '')
        variables_by_table.setdefault(table, []).append(row)
        if row.get('ICASA_var_uid'):
            variables_by_uid.setdefault(row['ICASA_var_uid'], []).append(row)
        for column in ('Variable_name', 'Target_column'):
            value = row.get(column, '')
            if value != value.strip():
                errors.append(f'variables.csv: {column} has surrounding whitespace: {value!r}')
        if not row.get('Target_column', '').strip():
            errors.append(f'variables.csv: missing Target_column for {table}.{row.get("Variable_name", "")}')
    errors.extend(storage_errors(variables))

    expected_tables = table_names
    if expected_tables != set(variables_by_table):
        errors.append(
            f'table/variables table mismatch: table-only={sorted(expected_tables - set(variables_by_table))}, '
            f'variables-only={sorted(set(variables_by_table) - expected_tables)}'
        )

    target_refs = {(r.get('Sheet_name', ''), r.get('Variable_name', ''),
                    r.get('ICASA_var_uid', '')) for r in variables}
    requirements = {'optional': 0, 'required_nullable': 1, 'required': 2}
    for source in icasa_rows:
        uid = source.get('var_uid', '')
        label = f'icasa_variable.csv UID {uid}'
        operation = source.get('adapt_operation', '')
        reason = source.get('Decision_reason', '').strip()
        declared = {t.strip() for t in source.get('Target_Sheet', '').split('|') if t.strip()}
        positions = variables_by_uid.get(uid, [])
        if operation not in {'keep', 'map', 'adapt_fix', 'reject'}:
            errors.append(f'{label}: invalid adapt_operation {operation!r}')
        if not reason:
            errors.append(f'{label}: Decision_reason must be nonempty')
        if declared - expected_tables:
            errors.append(f'{label}: unknown target tables {sorted(declared - expected_tables)}')
        if operation == 'reject':
            if positions or declared or source.get('Requirement'):
                errors.append(f'{label}: rejected variable still has target fields or requirements')
        elif operation in {'keep', 'map', 'adapt_fix'}:
            if not declared:
                errors.append(f'{label}: Target_Sheet must be nonempty')
            if operation == 'keep' and not positions:
                errors.append(f'{label}: kept variable has no target field')
        if positions:
            actual = {r['Sheet_name'] for r in positions}
            if actual != declared:
                errors.append(f'{label}: Target_Sheet disagrees with variables.csv: {sorted(actual)}')
            field_requirements = {r['Requirement'] for r in positions}
            if field_requirements <= requirements.keys():
                expected = min(field_requirements, key=requirements.get)
                if source.get('Requirement') != expected:
                    errors.append(f'{label}: Requirement must be {expected!r}')
            else:
                errors.append(f'{label}: target has invalid Requirement values')
            metadata_changed = any(
                    r.get(key) != source.get(key) for r in positions
                    for key in ('Description', 'Unit_or_type', 'Data_type'))
            if operation == 'keep' and metadata_changed:
                errors.append(f'{label}: definition/unit/type changes require map or adapt_fix')
            if operation == 'map' and not metadata_changed:
                errors.append(f'{label}: unchanged retained variable requires keep; placement and reference storage do not require map')
        elif source.get('Requirement'):
            errors.append(f'{label}: Requirement has no directly retained target field')
        unknown_uids = set(re.findall(r'var_uid (\d+)', reason)) - icasa_by_uid.keys()
        if unknown_uids:
            errors.append(f'{label}: unknown reason UIDs {sorted(unknown_uids)}')
        refs = re.findall(
            r'([A-Z][A-Za-z_]+)\.([^\s;]+) \((?:var_uid (\d+)|project field; no ICASA UID)\)', reason)
        for ref in refs:
            if ref not in target_refs:
                errors.append(f'{label}: unknown target field reference {ref!r}')
        if operation in {'map', 'adapt_fix'} and not declared <= {r[0] for r in refs}:
            errors.append(f'{label}: reason must name a target field in every Target_Sheet')

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


DICTIONARY_HEADERS = contract('Dictionary')[1]
validate_contract_integrity()


def validate_dictionary_rows(rows, *, partial=False):
    """Validate applied mappings and complete package-local variable declarations."""
    fields, headers, _ = contract('Dictionary')
    variables_path = ROOT / 'scheme/variables.csv'
    with variables_path.open(newline='', encoding='utf-8-sig') as f:
        variables = list(csv.DictReader(f))
    identities = {
        (r['Sheet_name'] + '.csv', r['Variable_name'], r['Code_Display']): r
        for r in variables if r['Sheet_name'] != 'Dictionary'
    }
    required = [r['Target_column'] for r in fields if r['Requirement'] == 'required']
    optional = [r['Target_column'] for r in fields if r['Requirement'] == 'optional']
    statuses = code_options()['Dictionary', 'mapping_status', '']
    headers, clean = validate_database_dictionary_rows(rows, headers, identities, statuses, required, optional,
                                                       partial=partial)
    additions = proposed_fields(clean, variables, partial=partial)
    errors = storage_errors([*variables, *additions], partial=partial)
    if errors:
        raise ContractValidationError('\n'.join(errors), [{'message': error} for error in errors])
    # Code proposals need an explicit vocabulary rather than free-form category guesses.
    package_code_options(clean, _contract_with_fields(additions), partial=partial)
    return headers, clean


def proposed_fields(rows, variables, *, partial=False):
    by_position = {(field['Sheet_name'], field['Variable_name']): field for field in variables}
    identities = {(field['Sheet_name'] + '.csv', field['Variable_name'], field['Code_Display'])
                  for field in variables}
    columns = {(field['Sheet_name'], field['Target_column']) for field in variables}
    tables = {field['Sheet_name'] for field in variables} - {'Dictionary'}
    additions = {}
    declarations = {}
    for row in rows:
        if row['mapping_status'] == 'excluded':
            continue
        if (row['target_file'], row['target_variable_name'], row['target_code_display']) in identities:
            continue
        table = row['target_file'].removesuffix('.csv')
        name = row['target_variable_name']
        if partial:
            storage_sources({'Storage': row['target_storage']})
            if not row['target_file']:
                continue
            if row['target_file'] != table + '.csv' or table not in tables:
                raise ValueError('Proposed variables require an existing target table CSV filename')
            if not name:
                continue
            if (table, name) in by_position and not row['target_code_display']:
                continue
            if not row['mapping_status']:
                continue
        if row['mapping_status'] != 'proposed' or row['target_file'] != table + '.csv' or table not in tables:
            raise ValueError('Proposed variables require an existing target table CSV filename')
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            raise ValueError(f'Proposed variable requires a valid output column name: {name}')
        if (table, name) in by_position or (table, name) in columns:
            raise ValueError(f'Proposed variable conflicts with an existing field: {table}.{name}')
        declared = declarations.setdefault((table, name), {})
        for attribute in ('target_code_display', 'target_definition', 'target_unit', 'target_data_type', 'target_storage'):
            value = row[attribute]
            if value:
                if declared.get(attribute) and declared[attribute] != value:
                    raise ValueError(f'Conflicting proposed variable definitions: {table}.{name}')
                declared[attribute] = value
        if partial and not row['target_data_type']:
            continue
        field = {key: '' for key in variables[0]}
        field.update(Sheet_name=table, Variable_name=name, Target_column=name, Requirement='optional',
                     Code_Display=row['target_code_display'], Description=row['target_definition'],
                     Unit_or_type=row['target_unit'], Data_type=row['target_data_type'], Storage=row['target_storage'])
        key = table, name
        if key in additions and additions[key] != field:
            previous = additions[key]
            if not partial or previous['Storage'] != field['Storage'] or any(
                    previous[key] and value and previous[key] != value for key, value in field.items()):
                raise ValueError(f'Conflicting proposed variable definitions: {table}.{name}')
            field = {key: value or previous[key] for key, value in field.items()}
        additions[key] = field
    return list(additions.values())


def _contract_with_fields(additions):
    cache = {}

    def lookup(table):
        if table not in cache:
            fields, headers, keys = contract(table)
            extra = [field for field in additions if field['Sheet_name'] == table]
            cache[table] = fields + extra, headers + [field['Target_column'] for field in extra], keys
        return cache[table]
    return lookup


def package_contract(dictionary, *, partial=False):
    """Build a fixed local field view; never register proposals in the global scheme."""
    _, clean = validate_dictionary_rows(dictionary, partial=partial)
    with (ROOT / 'scheme/variables.csv').open(newline='', encoding='utf-8-sig') as stream:
        variables = list(csv.DictReader(stream))
    return _contract_with_fields(proposed_fields(clean, variables, partial=partial))


def package_code_options(dictionary, lookup, *, partial=False):
    options = code_options()
    meanings = {}
    for row in dictionary:
        if row['mapping_status'] != 'proposed' or row['target_unit'] != 'code':
            continue
        if row['target_storage']:
            continue
        table = row['target_file'].removesuffix('.csv')
        if partial and (not table or not row['target_variable_name']):
            continue
        try:
            declaration = json.loads(row['mapping_scheme'])
        except ValueError:
            if partial:
                continue
            raise ValueError('Proposed code vocabularies require mapping_scheme JSON with a codes object') from None
        codes = declaration.get('codes') if isinstance(declaration, dict) else None
        if partial and (not isinstance(codes, dict) or not codes):
            continue
        if not isinstance(codes, dict) or not codes or any(
                not isinstance(code, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*:[^\s]+', code)
                or not isinstance(meaning, str) or not meaning.strip() for code, meaning in codes.items()):
            raise ValueError('Proposed codes require namespaced identifiers and nonempty definitions')
        field = next((field for field in lookup(table)[0] if field['Variable_name'] == row['target_variable_name']), None)
        if field is None and partial:
            continue
        for code, meaning in codes.items():
            key = table, field['Target_column'], code
            if key in meanings and meanings[key] != meaning:
                raise ValueError(f'Conflicting proposed code definitions: {table}.{field["Target_column"]} {code}')
            meanings[key] = meaning
        options.setdefault((table, field['Variable_name'], field['Code_Display']), set()).update(codes)
    for row in dictionary:
        if row['mapping_status'] == 'excluded' or row['target_unit'] != 'code' or not row['target_storage']:
            continue
        table = row['target_file'].removesuffix('.csv')
        if partial and (not table or not row['target_variable_name']):
            continue
        field = next((field for field in lookup(table)[0] if field['Variable_name'] == row['target_variable_name']), None)
        if field is None and partial:
            continue
        values = set()
        for source_table, column in storage_sources(field):
            source = next(field for field in lookup(source_table)[0] if field['Target_column'] == column)
            values.update(options.get((source_table, source['Variable_name'], source['Code_Display']), set()))
        if not values and not partial:
            raise ValueError(f'No declared source vocabulary for {table}.{field["Target_column"]}')
        options.setdefault((table, field['Variable_name'], field['Code_Display']), set()).update(values)
    return options


def write_dictionary(rows, output):
    """Save partial mapping rows; explicit validation requires complete metadata."""
    headers, clean = validate_dictionary_rows(rows, partial=True)
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


def write_table(table, rows, output, mode='replace', *, dictionary=None):
    """Save partial rows while checking supplied values and declared columns."""
    if table == 'Dictionary':
        if mode != 'replace':
            raise ValueError('Dictionary supports replace mode only; no unique mapping key is declared')
        return write_dictionary(rows, output)
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Output must be outside the contract directory')
    if dictionary is None:
        path = output.parent / 'Dictionary.csv'
        dictionary = _read_dictionary(path, partial=True) if path.exists() else []
    lookup = package_contract(dictionary, partial=True) if dictionary else contract
    options = package_code_options(dictionary, lookup, partial=True)
    headers, clean = _validate_data_rows(table, rows, lookup, options, partial=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    if mode not in {'replace', 'append', 'merge'}:
        raise ValueError('mode must be replace, append, or merge')
    fields, _, keys = lookup(table)
    required = {field['Target_column'] for field in fields if field['Requirement'] == 'required'}
    def check_merge_keys(batch, normalized):
        if any(key not in row or key in required and (row[key] is None or not str(row[key]).strip())
               for row in batch for key in keys):
            raise ValueError('Merge requires explicitly supplied complete primary keys; use replace for unfinished keys')
        identities = [tuple(row[key] for key in keys) for row in normalized]
        if len(set(identities)) != len(identities):
            raise ValueError('Merge requires unique primary keys; resolve duplicate records with replace first')
    if mode == 'merge':
        check_merge_keys(rows, clean)
    if mode != 'replace' and output.exists():
        fields, contract_headers, _ = lookup(table)
        with output.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            validate_database_headers(table, reader.fieldnames or [], fields, contract_headers)
            existing_input = list(reader)
        _, existing = _validate_data_rows(table, existing_input, lookup, options, partial=True)
        if mode == 'append':
            rows = existing + clean
        else:
            check_merge_keys(existing_input, existing)
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
        headers, clean = _validate_data_rows(table, rows, lookup, options, partial=True)
    fields, contract_headers, _ = lookup(table)
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


def _read_dictionary(path, *, partial=False):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != DICTIONARY_HEADERS:
            raise ContractValidationError('Dictionary header does not match the contract',
                [{'table': 'Dictionary', 'error': 'header_mismatch', 'expected': DICTIONARY_HEADERS,
                  'actual': reader.fieldnames}])
        return validate_dictionary_rows(list(reader), partial=partial)[1]


def validate_dictionary_file(path):
    """Validate the mapping artifact, including headers for empty files."""
    _read_dictionary(path)
    return True


def validate_package(directory, complete=False, *, final=False):
    """Check saved rows; final also checks shared copies, references and context-linked use."""
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
    dictionary_path = directory / 'Dictionary.csv'
    dictionary = _read_dictionary(dictionary_path) if dictionary_path.exists() else []
    lookup = package_contract(dictionary) if dictionary else contract
    options = package_code_options(dictionary, lookup)
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
            if meta['Table_name'] == 'Dictionary':
                continue
            fields, headers, _ = lookup(meta['Table_name'])
            with path.open(newline='', encoding='utf-8-sig') as f:
                actual_headers = next(csv.reader(f), [])
            validate_database_headers(meta['Table_name'], actual_headers, fields, headers)
            with path.open(newline='', encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            _, clean = _validate_data_rows(meta['Table_name'], rows, lookup, options)
            tables[meta['Table_name']] = clean
        elif complete:
            missing.append(meta['Table_name'])
    if missing:
        raise ContractValidationError(
            json.dumps({'missing_tables': missing}, ensure_ascii=False, sort_keys=True),
            [{'missing_tables': missing}],
        )
    errors = validate_database_foreign_keys(tables, metadata, lookup)
    errors.extend(validate_package_context(tables))
    errors.extend(validate_package_domains(tables))
    if errors:
        raise ContractValidationError('\n'.join(errors), [{'message': e} for e in errors])
    if final:
        diagnostics = validate_shared_observations(tables, lookup)
        if diagnostics:
            raise ContractValidationError('\n'.join(d['message'] for d in diagnostics), diagnostics)
        resolve_configurations(tables, lookup, options)
        diagnostics = validate_database_usage(tables, metadata, lookup)
        if diagnostics:
            raise ContractValidationError('\n'.join(d['message'] for d in diagnostics), diagnostics)
    return True


def export_configurations(directory, output):
    """Export a derived value view after final validation; never overwrite source data."""
    directory, output = Path(directory).resolve(), Path(output).resolve()
    if output == directory or output.is_relative_to(directory) or directory.is_relative_to(output) or output.is_relative_to(ROOT):
        raise ValueError('Export must be separate from the source package and contract')
    if output.exists():
        raise FileExistsError('Use a new export directory; exported values are derived views')
    validate_package(directory, final=True)
    dictionary_path = directory / 'Dictionary.csv'
    dictionary = _read_dictionary(dictionary_path) if dictionary_path.exists() else []
    lookup = package_contract(dictionary) if dictionary else contract
    options = package_code_options(dictionary, lookup)
    tables = {}
    with (ROOT / 'scheme/table.csv').open(newline='', encoding='utf-8-sig') as stream:
        names = [row['Table_name'] for row in csv.DictReader(stream) if row['Table_name'] != 'Dictionary']
    for table in names:
        path = directory / f'{table}.csv'
        if path.exists():
            with path.open(newline='', encoding='utf-8-sig') as stream:
                _, tables[table] = _validate_data_rows(table, list(csv.DictReader(stream)), lookup, options)
    resolved = resolve_configurations(tables, lookup, options)
    output.mkdir(parents=True)
    for table in CONFIGURATION_TABLES & tables.keys():
        headers = lookup(table)[1]
        with (output / f'{table}.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()
            writer.writerows(resolved[table])
    return sum(len(resolved[table]) for table in CONFIGURATION_TABLES & tables.keys())


def create_templates():
    destination = ROOT / 'template'
    destination.mkdir(exist_ok=True)
    with (ROOT / 'scheme/table.csv').open(newline='', encoding='utf-8-sig') as f:
        tables = [r['Table_name'] for r in csv.DictReader(f)]
    for table in tables:
        _, headers, _ = contract(table)
        with (destination / f'{table}.csv').open('w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(headers)
    return len(tables)


def check_templates():
    """Check that generated template headers still match the current contract."""
    errors = []
    with (ROOT / 'scheme/table.csv').open(newline='', encoding='utf-8-sig') as f:
        tables = [r['Table_name'] for r in csv.DictReader(f)]
    for table in tables:
        path = ROOT / 'template' / f'{table}.csv'
        if path.name not in {entry.name for entry in path.parent.glob('*.csv')}:
            errors.append({'table': table, 'error': 'missing_template'})
            continue
        with path.open(newline='', encoding='utf-8-sig') as f:
            actual = next(csv.reader(f), [])
        _, expected, _ = contract(table)
        if actual != expected:
            errors.append({'table': table, 'error': 'header_mismatch',
                           'expected': expected, 'actual': actual})
    if errors:
        raise ContractValidationError('\n'.join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in errors), errors)
    return len(tables)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--templates', action='store_true')
    parser.add_argument('--table')
    parser.add_argument('--input', type=Path, help='JSON array of row objects')
    parser.add_argument('--dictionary', type=Path, help='Dictionary defining package-local proposed fields; defaults to the output directory Dictionary.csv')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--mode', choices=('replace', 'append', 'merge'), default='replace')
    parser.add_argument('--validate-package', type=Path)
    parser.add_argument('--validate-dictionary', type=Path, help='validate a mapping Dictionary.csv independently of the data package')
    parser.add_argument('--complete', action='store_true', help='require every target_template table and Dictionary.csv in package validation')
    parser.add_argument('--final', action='store_true', help='with --validate-package, resolve declared value references and reject records unused by plot-season contexts')
    parser.add_argument('--check-templates', action='store_true')
    parser.add_argument('--export-configurations', type=Path, metavar='PACKAGE',
                        help='final-check PACKAGE and export resolved configuration values to a new --output directory')
    args = parser.parse_args()
    if args.final and not args.validate_package:
        parser.error('--final requires --validate-package')
    if args.export_configurations:
        if not args.output:
            parser.error('--export-configurations requires --output')
        print(f'Exported {export_configurations(args.export_configurations, args.output)} configuration rows')
    elif args.check_templates:
        print(f'Checked {check_templates()} templates')
    elif args.validate_dictionary:
        validate_dictionary_file(args.validate_dictionary)
        print('Dictionary is valid')
    elif args.validate_package:
        validate_package(args.validate_package, complete=args.complete, final=args.final)
        package_label = 'Final package' if args.final else 'Package'
        print(f'{package_label} is valid' if args.complete else
              f'{package_label} is valid for the supplied partial tables')
    elif args.templates:
        print(f'Created {create_templates()} templates')
    else:
        if not all((args.table, args.input, args.output)):
            parser.error('--table, --input and --output are required')
        data = json.loads(args.input.read_text(encoding='utf-8'))
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            parser.error('Input must be a JSON array of row objects')
        dictionary = _read_dictionary(args.dictionary, partial=True) if args.dictionary else None
        print(f'Wrote {write_table(args.table, data, args.output, args.mode, dictionary=dictionary)} rows')
