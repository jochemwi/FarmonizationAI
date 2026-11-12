"""Deterministic database-contract validation for the target_template API.

This module validates the shape and representation of rows: field identity,
requiredness, scalar values, dates, numbers, code vocabularies, logical
duplicate keys, and declared scalar or collection-valued foreign keys.
Cross-table agronomic meaning belongs in ``domain_validation.py``.
"""
import json
import math
import re
from collections import defaultdict
from datetime import date


HAUN_STAGE_PATTERN = re.compile(r"^(0|[1-9]\d*)\.\d$")
ZADOKS_STAGE_PATTERN = re.compile(r"^(0|[1-9]\d?)$")

# Stored as a canonical semicolon list in the CSV contract.  Each member is
# still an independent reference to the parent key.
COLLECTION_FOREIGN_KEY_FIELDS = frozenset({'group_plot_season_ids'})


def storage_sources(field):
    """Read declared cross-table source columns; blank storage means direct values."""
    storage = field.get('Storage', '')
    if not storage:
        return []
    sources = storage.split(';')
    if any(source != source.strip() or '.' not in source for source in sources) or len(set(sources)) != len(sources):
        raise ValueError('Storage must contain distinct Table.Target_column sources separated by semicolons')
    pairs = [tuple(source.split('.', 1)) for source in sources]
    if any(not table or not column for table, column in pairs):
        raise ValueError('Storage sources require a table and output column')
    return pairs


def is_value_reference(field):
    return bool(field.get('Storage')) and not field.get('FK_Reference')


class ContractValidationError(ValueError):
    """Validation failure with machine-readable diagnostics."""

    def __init__(self, message, diagnostics=None):
        super().__init__(message)
        self.diagnostics = diagnostics or []


# Conservative defaults for fields whose valid numeric domain is inherent in
# their unit or identity. Table-specific constraints can be added here without
# changing the CSV contract format.
DEFAULT_NUMERIC_RANGES = {
    ('Weather_monthly', 'year'): (1000, 9999),
    ('Weather_monthly', 'month'): (1, 12),
    ('Weather_stations', 'weather_sta_latitude'): (-90, 90),
    ('Weather_stations', 'weather_sta_longitude'): (-180, 180),
    ('Plots', 'field_latitude'): (-90, 90),
    ('Plots', 'field_longitude'): (-180, 180),
}

DEFAULT_UNIT_RANGES = {
    '%': (0, 100),
    'percent': (0, 100),
    'fraction': (0, 1),
    'doy': (1, 366),
    'arc_degrees': (0, 360),
}


def _numeric_range(table, field):
    return DEFAULT_NUMERIC_RANGES.get((table, field['Variable_name'])) or \
        DEFAULT_UNIT_RANGES.get(field['Unit_or_type'])


def validate_database_headers(table, actual, fields, headers):
    """Validate a CSV header while allowing optional columns to be omitted."""
    if len(actual) != len(set(actual)):
        raise ValueError(f'{table}: duplicate CSV headers')
    unknown = sorted(set(actual) - set(headers))
    if unknown:
        raise ValueError(f'{table}: unknown CSV headers: {unknown}')
    missing = [header for header, field in zip(headers, fields)
               if field['Requirement'] in {'required', 'required_nullable'} and header not in actual]
    if missing:
        raise ValueError(f'{table}: missing required CSV headers: {missing}')


def validate_database_rows(table, rows, fields, headers, keys, options, *, partial=False):
    """Normalize and validate row structure without applying domain rules."""
    result, seen, key_rows = [], set(), {}
    errors = []
    for n, row in enumerate(rows, 1):
        extra = set(row) - set(headers)
        missing = set(headers) - set(row)
        if extra:
            raise ValueError(f'Row {n}: unknown fields: {extra}')
        missing_required = [h for h, f in zip(headers, fields)
                            if h in missing and f['Requirement'] in {'required', 'required_nullable'}]
        if missing_required and not partial:
            required = [h for h in missing_required
                        if next(f for h2, f in zip(headers, fields) if h2 == h)['Requirement'] == 'required']
            nullable = [h for h in missing_required
                        if next(f for h2, f in zip(headers, fields) if h2 == h)['Requirement'] == 'required_nullable']
            details = []
            if required:
                details.append(f"fields {required} must be provided with a non-empty value")
            if nullable:
                details.append(f"fields {nullable} must be included, but may be blank")
            raise ValueError(f"Row {n}: missing required input fields; " + '; '.join(details))

        clean = {}
        variable_headers = {field['Variable_name']: header
                            for field, header in zip(fields, headers)}
        for h, field in zip(headers, fields):
            value = row.get(h, '')
            if value is None:
                value = ''
            elif isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise ValueError(f'Row {n}, {h}: expected a scalar string or number')
            else:
                value = str(value).strip()
            if field['Variable_name'] == 'plot_season_id' and ';' in value:
                raise ValueError(f'Row {n}, {h}: semicolons are reserved for group_plot_season_ids separators')
            if field['Variable_name'] == 'group_plot_season_ids' and value:
                parts = [part.strip() for part in value.split(';')]
                if any(not part for part in parts):
                    raise ValueError(
                        'expected a semicolon-separated list with no empty plot-season IDs'
                    )
                if len(parts) != len(set(parts)):
                    raise ValueError('group_plot_season_ids contains duplicate plot-season IDs')
                value = ';'.join(sorted(parts))
            if value:
                try:
                    if is_value_reference(field):
                        from harmonization_template.observation_references import parse_reference
                        source_table, _, source_column = parse_reference(value)
                        if (source_table, source_column) not in storage_sources(field):
                            raise ValueError('Reference does not use a declared Storage source')
                        clean[h] = value
                        continue
                    if field['Unit_or_type'] == 'date' or field['Data_type'] == 'date':
                        if date.fromisoformat(value).isoformat() != value:
                            raise ValueError('expected YYYY-MM-DD')
                    elif field['Data_type'] in ('single', 'int'):
                        number = float(value)
                        if not math.isfinite(number) or (field['Data_type'] == 'int' and not number.is_integer()):
                            raise ValueError('expected finite number')
                        bounds = (_numeric_range(table, field)
                                  if (field['Requirement'] in {'required', 'required_nullable'}
                                      or field.get('Role') == 'context')
                                  else None)
                        if bounds and not bounds[0] <= number <= bounds[1]:
                            raise ValueError(f'expected value between {bounds[0]} and {bounds[1]}')
                        value = str(int(number)) if number.is_integer() else repr(number)
                    if field['Unit_or_type'] == 'code':
                        source_key = (table, field['Variable_name'], field['Code_Display'])
                        if source_key not in options:
                            raise ValueError('code field has no explicit CODE_SOURCES mapping')
                        if value not in options[source_key]:
                            raise ValueError('unknown code')
                    if (table in {'Crop_observations_summary', 'Crop_observations_timeseries'} and
                            field['Variable_name'] in {'growth_stage_Haun', 'leaf_number_as_haun_stg'} and
                            not HAUN_STAGE_PATTERN.fullmatch(value)):
                        raise ValueError('expected Haun stage format N.d')
                    if (table in {'Crop_observations_summary', 'Crop_observations_timeseries'} and
                            field['Variable_name'] == 'growth_stage_Zadoks' and
                            not ZADOKS_STAGE_PATTERN.fullmatch(value)):
                        raise ValueError('expected Zadoks stage integer from 0 to 99')
                except (ValueError, OverflowError) as exc:
                    raise ValueError(f'Row {n}, {h}: invalid value {value!r}') from exc
            if not partial and field['Requirement'] == 'required' and not value:
                errors.append(f'Row {n}, {h}: required field is blank')
            clean[h] = value

        group_header = variable_headers.get('group_plot_season_ids')
        anchor_header = variable_headers.get('plot_season_id')
        if group_header and anchor_header:
            group_value = clean[group_header]
            anchor = clean[anchor_header]
            if group_value and anchor and anchor not in group_value.split(';'):
                raise ValueError(
                    f'group_plot_season_ids must include plot_season_id {anchor!r}'
                )

        key = tuple(clean[h] for h in keys)
        if key in seen and not partial:
            observation = table in {f'{family}_observations_{kind}'
                                    for family in ('Soil_layer', 'Crop', 'Other')
                                    for kind in ('summary', 'timeseries')}
            duplicate = {
                'table': table,
                'logical_key': list(key),
                'rows': [key_rows[key], n],
                'action': 'select_record_upstream' if observation else 'aggregate_upstream',
                'message': ('duplicate logical key; the caller must select one record before registration; '
                            'do not aggregate alternative values automatically.' if observation else
                            'duplicate logical key; aggregate upstream before registration.')
            }
            errors.append(json.dumps(duplicate, ensure_ascii=False, sort_keys=True))
            continue
        seen.add(key)
        key_rows[key] = n
        result.append(clean)

    if errors:
        diagnostics = []
        for item in errors:
            try:
                diagnostics.append(json.loads(item))
            except json.JSONDecodeError:
                diagnostics.append({'message': item})
        raise ContractValidationError('\n'.join(errors), diagnostics)
    return headers, result


def validate_database_dictionary_rows(rows, headers, identities, mapping_statuses, required_fields,
                                      optional_fields=(), *, partial=False):
    """Validate dictionary structure and target identities."""
    errors = []
    clean_rows = []
    target_fields = ('target_file', 'target_variable_name', 'target_code_display', 'target_definition',
                     'target_unit', 'target_data_type')
    source_statuses = defaultdict(set)
    predefined_meanings = {
        (field['Variable_name'].strip(), field['Description'].strip(), field['Unit_or_type'].strip())
        for field in identities.values()
    }
    for n, row in enumerate(rows, 1):
        extra = set(row) - set(headers)
        missing = set(headers) - set(row) - set(optional_fields)
        if extra:
            errors.append({'row': n, 'type': 'unknown_field', 'fields': sorted(extra)})
            continue
        if missing and not partial:
            errors.append({'row': n, 'type': 'missing_field', 'fields': sorted(missing)})
            continue
        if any(isinstance(value, bool) or value is not None and not isinstance(value, (str, int, float))
               for value in row.values()):
            errors.append({'row': n, 'type': 'invalid_dictionary_scalar'})
            continue
        clean = {h: '' if row.get(h) is None else str(row[h]).strip() for h in headers}
        excluded = clean['mapping_status'] == 'excluded'
        required = set(required_fields) - set(target_fields) if excluded else set(required_fields) | set(target_fields)
        for field in sorted(required):
            if not clean[field] and not partial:
                errors.append({'row': n, 'type': 'missing_dictionary_value', 'field': field})
        if clean['mapping_status'] not in mapping_statuses and (clean['mapping_status'] or not partial):
            errors.append({'row': n, 'type': 'invalid_mapping_status',
                           'field': 'mapping_status', 'value': clean['mapping_status']})
        source_key = (clean['Source_file'], clean['source_variable_name'], clean['source_variable_code'])
        if not partial or all(source_key):
            source_statuses[source_key].add(clean['mapping_status'])
        if excluded:
            nonempty = [field for field in (*target_fields, 'target_storage', 'Closest Crop Ontology ID') if clean[field]]
            if nonempty:
                errors.append({'row': n, 'type': 'excluded_source_has_target', 'fields': nonempty})
            if not clean['mapping_scheme'] and not partial:
                errors.append({'row': n, 'type': 'excluded_source_requires_reason', 'field': 'mapping_scheme'})
            clean_rows.append(clean)
            continue
        if not partial and clean['mapping_status'] == 'conditional' and not clean['mapping_scheme']:
            errors.append({'row': n, 'type': 'conditional_mapping_requires_conditions',
                           'field': 'mapping_scheme'})
        target_values = (clean['target_file'], clean['target_variable_name'], clean['target_code_display'])
        proposed = clean['mapping_status'] == 'proposed'
        if clean['target_data_type'] not in {'text', 'int', 'single', 'date'} and (clean['target_data_type'] or not partial):
            errors.append({'row': n, 'type': 'invalid_target_data_type', 'field': 'target_data_type'})
        if all(target_values) and target_values not in identities and not proposed:
            errors.append({'row': n, 'type': 'unknown_target_variable',
                           'target': list(target_values)})
        definition = identities.get(target_values)
        if definition is None and partial and not clean['target_code_display']:
            definition = next((value for key, value in identities.items() if key[:2] == target_values[:2]), None)
        if definition is not None:
            for field, contract_field in (('target_definition', 'Description'),
                                          ('target_unit', 'Unit_or_type'),
                                          ('target_data_type', 'Data_type'),
                                          ('target_storage', 'Storage')):
                expected = definition[contract_field].strip()
                storage_declared = field == 'target_storage' and all(clean[key] for key in target_fields)
                if clean[field] != expected and (clean[field] or not partial or storage_declared):
                    errors.append({'row': n, 'type': 'target_contract_mismatch', 'field': field,
                                   'expected': expected, 'actual': clean[field]})
        if proposed and target_values not in identities and (clean['target_variable_name'], clean['target_definition'], clean['target_unit']) in predefined_meanings:
            errors.append({'row': n, 'type': 'predefined_target_required',
                           'message': 'Use the predefined target_template target for this variable definition and unit.'})
        if proposed and target_values not in identities and (clean['target_code_display'] or not partial) and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*:[^\s]+', clean['target_code_display']):
            errors.append({'row': n, 'type': 'ontology_target_requires_term_identifier',
                           'field': 'target_code_display'})
        if not partial and clean['Closest Crop Ontology ID'] and not clean['ai_comments']:
            errors.append({'row': n, 'type': 'ontology_link_requires_comments', 'field': 'ai_comments'})
        clean_rows.append(clean)
    for source, statuses in source_statuses.items():
        if 'excluded' in statuses and len(statuses) > 1:
            errors.append({'type': 'conflicting_source_exclusion', 'source': list(source), 'statuses': sorted(statuses)})
    if errors:
        raise ContractValidationError(
            '\n'.join(json.dumps(e, ensure_ascii=False, sort_keys=True) for e in errors), errors)
    return headers, clean_rows


def validate_database_foreign_keys(tables, metadata, contract_lookup):
    """Return package-level foreign-key errors after row validation."""
    errors = []
    for meta in metadata:
        for relation in filter(None, (x.strip() for x in meta['Foreign_keys'].split(';'))):
            child, target = [x.strip() for x in relation.split('->', 1)]
            parent_table, parent_column = [x.strip() for x in target.split('.', 1)]
            child_fields, child_headers, _ = contract_lookup(meta['Table_name'])
            child_matches = [
                (field, header) for field, header in zip(child_fields, child_headers)
                if field['Variable_name'] == child
            ]
            if len(child_matches) != 1:
                errors.append(
                    f"{meta['Table_name']}: foreign-key field {child!r} is ambiguous or missing"
                )
                continue
            parent_fields, parent_headers, _ = contract_lookup(parent_table)
            parent_matches = [
                header for field, header in zip(parent_fields, parent_headers)
                if field['Variable_name'] == parent_column
            ]
            if len(parent_matches) != 1:
                errors.append(
                    f"{meta['Table_name']}: foreign-key target {parent_table}.{parent_column} "
                    'is ambiguous or missing'
                )
                continue
            parents = {row.get(parent_matches[0], '') for row in tables.get(parent_table, [])}
            child_field, child_header = child_matches[0]
            for n, row in enumerate(tables.get(meta['Table_name'], []), 2):
                value = row.get(child_header, '')
                if not value and child_field['Requirement'] == 'required':
                    errors.append(f"{meta['Table_name']} row {n}: required foreign key {child} is blank")
                if child in COLLECTION_FOREIGN_KEY_FIELDS:
                    values = [part.strip() for part in value.split(';') if part.strip()]
                else:
                    values = [value] if value else []
                if child == 'group_plot_season_ids':
                    anchor = row.get('plot_season_id', '')
                    if anchor and anchor not in values:
                        errors.append(
                            f"{meta['Table_name']} row {n}: group_plot_season_ids "
                            f"must include plot_season_id {anchor!r}"
                        )
                for candidate in values:
                    if candidate not in parents:
                        errors.append(
                            f"{meta['Table_name']} row {n}: {child} member {candidate!r} "
                            f"has no {parent_table}.{parent_column}; define it in {parent_table} first"
                        )
    return errors


def validate_shared_observations(tables, contract_lookup):
    """Check shared observation copies after package rows have been normalized."""
    diagnostics = []
    for table, rows in tables.items():
        if table not in {f'{family}_observations_{kind}'
                         for family in ('Soil_layer', 'Crop', 'Other')
                         for kind in ('summary', 'timeseries')}:
            continue
        fields, headers, keys = contract_lookup(table)
        scope_keys = [key for key in keys if key != 'plot_season_id']
        data_headers = [header for field, header in zip(fields, headers) if not field.get('Role')]
        groups = defaultdict(list)
        for number, row in enumerate(rows, 2):
            if ';' in row['group_plot_season_ids']:
                groups[tuple(row[key] for key in scope_keys)].append((number, row))
        for key, copies in groups.items():
            scope = dict(zip(scope_keys, key))
            expected = set(copies[0][1]['group_plot_season_ids'].split(';'))
            missing = sorted(expected - {row['plot_season_id'] for _, row in copies})
            if missing:
                diagnostics.append(dict(
                    error='missing_shared_observation_copies', table=table, scope=scope,
                    missing_plot_season_ids=missing,
                    message=f'{table}: shared observation {scope} is missing copies for {missing}'))
            for header in data_headers:
                values = {row['plot_season_id']: row[header] for _, row in copies}
                if len(set(values.values())) > 1:
                    diagnostics.append(dict(
                        error='conflicting_shared_observation_values', table=table, scope=scope,
                        field=header, values=values, rows=[number for number, _ in copies],
                        message=f'{table}: shared observation {scope} has conflicting {header} values {values}'))
    return diagnostics


def validate_database_usage(tables, metadata, contract_lookup):
    """Return unused parent-record diagnostics for final plot-season packages."""
    columns = {}
    for meta in metadata:
        table = meta['Table_name']
        fields, headers, _ = contract_lookup(table)
        columns[table] = {field['Variable_name']: header
                          for field, header in zip(fields, headers)}

    relations, parent_columns = {}, {}
    for meta in metadata:
        table = meta['Table_name']
        relations[table] = []
        for relation in filter(None, (x.strip() for x in meta['Foreign_keys'].split(';'))):
            child, target = [x.strip() for x in relation.split('->', 1)]
            parent_table, parent_column = [x.strip() for x in target.split('.', 1)]
            parent_columns[parent_table] = columns[parent_table][parent_column]
            relations[table].append((columns[table][child], parent_table,
                                     child in COLLECTION_FOREIGN_KEY_FIELDS))

    records = {(table, row[column]): row
               for table, column in parent_columns.items()
               for row in tables.get(table, [])}
    pending = [('Plot_seasons', row['plot_season_id'])
               for row in tables.get('Plot_seasons', [])]
    used = set()
    while pending:
        node = pending.pop()
        if node in used or node not in records:
            continue
        used.add(node)
        for column, parent_table, collection in relations[node[0]]:
            value = records[node].get(column, '')
            values = value.split(';') if collection else [value]
            pending.extend((parent_table, value) for value in values if value)

    # Only context dependencies establish use; a resource's own detail rows do not.
    diagnostics = []
    for table, column in parent_columns.items():
        for n, row in enumerate(tables.get(table, []), 2):
            value = row[column]
            if (table, value) not in used:
                diagnostics.append({
                    'error': 'unreferenced_record', 'table': table, 'row': n,
                    'field': column, 'value': value,
                    'message': f'{table} row {n}: {column} {value!r} has no reference '
                               'path from Plot_seasons; resolve its context or retain it outside the final package',
                })
    return diagnostics
