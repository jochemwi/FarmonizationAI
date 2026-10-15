"""Deterministic database-contract validation for the v8 API.

This module validates the shape and representation of rows: field identity,
requiredness, scalar values, dates, numbers, code vocabularies, logical
duplicate keys, and declared scalar or collection-valued foreign keys.
Cross-table agronomic meaning belongs in ``domain_validation.py``.
"""
import json
import math
import re
from datetime import date


HAUN_STAGE_PATTERN = re.compile(r"^(0|[1-9]\d*)\.\d$")
ZADOKS_STAGE_PATTERN = re.compile(r"^(0|[1-9]\d?)$")

# Stored as a canonical semicolon list in the CSV contract.  Each member is
# still an independent reference to the parent key.
COLLECTION_FOREIGN_KEY_FIELDS = frozenset({'group_plot_season_ids'})


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


def validate_database_rows(table, rows, fields, headers, keys, options):
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
        if missing_required:
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
                    if field['Unit_or_type'] == 'date' or field['Data_type'] == 'date':
                        if date.fromisoformat(value).isoformat() != value:
                            raise ValueError('expected YYYY-MM-DD')
                    elif field['Data_type'] in ('single', 'int'):
                        number = float(value)
                        if not math.isfinite(number) or (field['Data_type'] == 'int' and not number.is_integer()):
                            raise ValueError('expected finite number')
                        bounds = (_numeric_range(table, field)
                                  if field['Requirement'] in {'required', 'required_nullable'}
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
            if field['Requirement'] == 'required' and not value:
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
        if key in seen:
            duplicate = {
                'table': table,
                'logical_key': list(key),
                'rows': [key_rows[key], n],
                'action': 'aggregate_upstream',
                'message': 'duplicate logical key; aggregate upstream before registration.'
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


def validate_database_dictionary_rows(rows, headers, identities, mapping_statuses):
    """Validate dictionary structure and target identities."""
    errors = []
    clean_rows = []
    for n, row in enumerate(rows, 1):
        extra = set(row) - set(headers)
        missing = set(headers) - set(row)
        if extra:
            errors.append({'row': n, 'type': 'unknown_field', 'fields': sorted(extra)})
            continue
        if missing:
            errors.append({'row': n, 'type': 'missing_field', 'fields': sorted(missing)})
            continue
        clean = {h: '' if row[h] is None else str(row[h]).strip() for h in headers}
        for field in ('source_dataset', 'source_variable_name', 'source_definition',
                      'target_definition', 'mapping_scheme', 'mapping_status'):
            if not clean[field]:
                errors.append({'row': n, 'type': 'missing_dictionary_value', 'field': field})
        if clean['mapping_status'] not in mapping_statuses:
            errors.append({'row': n, 'type': 'invalid_mapping_status',
                           'field': 'mapping_status', 'value': clean['mapping_status']})
        target_values = (clean['target_table'], clean['target_variable_name'], clean['target_code_display'])
        any_target = any(target_values)
        if any_target and not all(target_values):
            errors.append({'row': n, 'type': 'incomplete_target_identity',
                           'fields': ['target_table', 'target_variable_name', 'target_code_display']})
        if clean['mapping_status'] in {'confirmed', 'conditional', 'review', 'mapping_review', 'aggregation_review'} and not all(target_values):
            errors.append({'row': n, 'type': 'mapped_row_requires_target_identity',
                           'fields': ['target_table', 'target_variable_name', 'target_code_display']})
        if all(target_values) and target_values not in identities:
            errors.append({'row': n, 'type': 'unknown_target_variable',
                           'target': list(target_values)})
        if clean['mapping_status'] in {'unresolved', 'not_observed'} and not clean['error_type']:
            errors.append({'row': n, 'type': 'unresolved_row_requires_error_type', 'field': 'error_type'})
        clean_rows.append(clean)
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
