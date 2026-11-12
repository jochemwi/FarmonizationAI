"""Declared selections of directly stored cross-table values."""
from collections import defaultdict
import re
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit

from harmonization_template.database_validation import (
    ContractValidationError, is_value_reference, storage_sources, validate_database_rows,
)
from harmonization_template.domain_validation import raise_domain_errors, validate_row_domains

CONFIGURATION_TABLES = frozenset({
    'Initial_conditions', 'Initial_conditions_layer', 'Soil_profiles', 'Soil_profile_layers',
})
OBSERVATION_TABLES = frozenset(
    f'{family}_observations_{kind}'
    for family in ('Soil_layer', 'Crop', 'Other') for kind in ('summary', 'timeseries')
)


def observation_reference(table, key, column):
    """Address a cell by its table, complete existing primary key and column."""
    if not isinstance(key, dict) or not key:
        raise ValueError('Provide the complete observation primary key as a mapping')
    if any(not isinstance(name, str) or isinstance(value, bool)
           or not isinstance(value, (str, int, float, type(None))) for name, value in key.items()):
        raise ValueError('Primary-key values must be scalar strings, numbers or null')
    values = sorted((name, '' if value is None else str(value).strip()) for name, value in key.items())
    return f'obs:{table}?{urlencode(values, quote_via=quote)}#{quote(column, safe="")}'


def parse_reference(value):
    try:
        parsed = urlsplit(value)
        table, column = parsed.path, unquote(parsed.fragment)
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        key = dict(pairs)
        if (parsed.scheme != 'obs' or parsed.netloc or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', table)
                or not column or not key or len(key) != len(pairs)):
            raise ValueError()
    except (AttributeError, TypeError, ValueError):
        raise ValueError('Expected obs:<source_table>?<complete primary-key query>#<encoded column>') from None
    return table, key, column


def same_variable(target, source):
    identity = ('ICASA_var_uid',) if target['ICASA_var_uid'] else ('Variable_name', 'Description')
    return all(target[key] == source[key] for key in (*identity, 'Unit_or_type', 'Data_type'))


def reference_error(message, **details):
    raise ContractValidationError(message, [dict(error='invalid_observation_reference', message=message, **details)])


def resolve_configurations(tables, contract, options):
    """Resolve declared cross-table value references, leaving foreign keys as IDs."""
    contracts = {table: contract(table) for table in tables}
    index = defaultdict(list)
    for table in tables:
        keys = contracts[table][2]
        for row in tables.get(table, []):
            index[table, tuple(row.get(key, '') for key in keys)].append(row)
    resolved = {}
    for table in tables:
        fields, headers, keys = contracts[table]
        definitions = dict(zip(headers, fields))
        output = []
        for row in tables.get(table, []):
            materialized = {header: row.get(header, '') for header in headers}
            refs = [(header, row.get(header), definitions[header]) for header in headers
                    if is_value_reference(definitions[header]) and row.get(header)]
            for header, ref, target in refs:
                source_table, source_key, column = parse_reference(ref)
                if (source_table, column) not in storage_sources(target):
                    reference_error(f'{table}.{header}: reference uses an undeclared Storage source',
                                    table=table, field=header, reference=ref)
                if source_table not in contracts:
                    reference_error(f'{table}.{header}: source table {source_table} is absent',
                                    table=table, field=header, reference=ref)
                source_fields, source_headers, source_keys = contracts[source_table]
                if set(source_key) != set(source_keys):
                    reference_error(f'{table}: reference {ref!r} must contain the complete primary key {source_keys}',
                                    table=table, field=header, reference=ref)
                key_fields = [field for field in source_fields if field['Target_column'] in source_keys]
                _, normalized = validate_database_rows(source_table, [source_key], key_fields,
                                                       source_keys, source_keys, options)
                record = tuple(normalized[0][key] for key in source_keys)
                matches = index[source_table, record]
                if len(matches) != 1:
                    reference_error(f'{table}: reference {ref!r} resolves to {len(matches)} records; expected exactly one',
                                    table=table, field=header, reference=ref)
                source = dict(zip(source_headers, source_fields)).get(column)
                if source is None or source.get('Storage') or source.get('Role') in {'id', 'context', 'source_comments', 'ai_comments', 'mapping'}:
                    reference_error(f'{table}: reference {ref!r} must select a directly stored data field',
                                    table=table, field=header, reference=ref)
                if not same_variable(target, source):
                    reference_error(f'{table}.{header}: reference {ref!r} selects the wrong variable, unit or type',
                                    table=table, field=header, reference=ref)
                value = matches[0].get(column, '')
                if not value:
                    reference_error(f'{table}: reference {ref!r} selects a blank value',
                                    table=table, field=header, reference=ref)
                materialized[header] = value
                # Validate the selected value using its observation vocabulary.
                validate_database_rows(source_table, [{column: value}],
                                       [dict(source, Requirement='optional')], [column], [column], options)
            physical_fields = [dict(field, Storage='') for field in fields]
            physical_headers = [field['Target_column'] for field in physical_fields]
            _, clean = validate_database_rows(table, [materialized], physical_fields, physical_headers, keys, options)
            raise_domain_errors(validate_row_domains(table, clean, physical_fields, physical_headers))
            output.extend(clean)
        resolved[table] = output
    return resolved
