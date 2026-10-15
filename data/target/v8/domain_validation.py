"""Deterministic domain-knowledge validation for the v8 API.

Database shape and type checks live in ``database_validation.py``. This module
checks deterministic agronomic relationships that require meaning within a
row or across related tables.
"""
from collections import defaultdict
from datetime import date

from database_validation import ContractValidationError


# Explicitly reviewed whitelist for every current Crop_codes.csv row whose
# Repro_type is Annual. Keep this list explicit so date-rule changes are
# visible in code review.
SINGLE_SEASON_CROP_CODES = frozenset({
    'ACK', 'AMR', 'BAR', 'BCR', 'BGR', 'BLW', 'BMG', 'BND', 'BNG', 'BWH',
    'CAM', 'CBG', 'CCB', 'CEL', 'CHI', 'CHP', 'CLF', 'CNL', 'COT', 'CRM',
    'CSV', 'CUC', 'CWP', 'EGP', 'END', 'FBN', 'FLX', 'FML', 'FMZ', 'FXM',
    'GAR', 'GUR', 'HMP', 'JBN', 'JUT', 'KNF', 'LAB', 'LBN', 'LEN', 'LET',
    'MAZ', 'MNG', 'OAT', 'OKR', 'PEA', 'PGP', 'PMK', 'PML', 'PNA', 'PNT',
    'POT', 'PPR', 'PPY', 'PRM', 'QUN', 'RAD', 'RAP', 'RGA', 'RIC', 'RYE',
    'SAF', 'SBN', 'SBT', 'SES', 'SGG', 'SHL', 'SPN', 'SQS', 'SQW', 'STB',
    'SUN', 'SWC', 'SWP', 'TAN', 'TAR', 'TBN', 'TEF', 'TNP', 'TOM', 'TRT',
    'VBN', 'VMG', 'WHB', 'WHD', 'WHT', 'WML', 'YAM',
})

def _field_headers(fields, headers):
    return {field['Variable_name']: header
            for field, header in zip(fields, headers)}


def _temporal_context_groups(fields):
    """Return event date/phenology/event triples present in one table."""
    names = {field['Variable_name'] for field in fields}
    groups = []
    for phenology in sorted(name for name in names if name.endswith('_phenology_time')):
        prefix = phenology[:-len('_phenology_time')]
        event = f'{prefix}_event_time'
        date_name = next((candidate for candidate in (
            f'{prefix}_date', f'{prefix}_operations_date'
        ) if candidate in names), None)
        if date_name and event in names:
            groups.append((date_name, phenology, event))
    return groups


def _date_value(value):
    return date.fromisoformat(value) if value else None


def _check_date_order(row, field_headers, before_name, after_name, errors, label):
    if before_name not in field_headers or after_name not in field_headers:
        return
    before = _date_value(row[field_headers[before_name]])
    after = _date_value(row[field_headers[after_name]])
    if before and after and before > after:
        errors.append(
            f'{label}: {before_name} {before.isoformat()} cannot be after '
            f'{after_name} {after.isoformat()}'
        )


def validate_row_domains(table, rows, fields, headers):
    """Return deterministic domain errors for already normalized rows."""
    field_headers = _field_headers(fields, headers)
    errors = []

    for n, row in enumerate(rows, 1):
        for top_name, bottom_name in (
            ('me_soil_layer_top_depth', 'me_soil_layer_bot_depth'),
            ('soil_layer_top_depth', 'soil_layer_base_depth'),
        ):
            if top_name not in field_headers or bottom_name not in field_headers:
                continue
            top = row[field_headers[top_name]]
            bottom = row[field_headers[bottom_name]]
            if bool(top) != bool(bottom):
                errors.append(
                    f'Row {n}, {table}: {top_name} and {bottom_name} must be provided together'
                )
                continue
            if top and float(top) > float(bottom):
                errors.append(
                    f'Row {n}, {table}: {top_name} cannot be greater than {bottom_name}'
                )

        for group in _temporal_context_groups(fields):
            if not any(row[field_headers[name]] for name in group):
                errors.append(
                    f'Row {n}, {table}: at least one of {", ".join(group)} must be provided'
                )

        if table == 'Planting_events':
            _check_date_order(row, field_headers, 'planting_date', 'transplant_date',
                              errors, f'Row {n}, {table}')
            _check_date_order(row, field_headers, 'planting_date', 'emergence_date',
                              errors, f'Row {n}, {table}')
        elif table == 'Auto_iIrrigation_events':
            _check_date_order(row, field_headers, 'auto_irrig_date', 'auto_irrig_end_date',
                              errors, f'Row {n}, {table}')
        elif table == 'Mulch_events':
            _check_date_order(row, field_headers, 'mulch_applic_date', 'mulch_removal_date',
                              errors, f'Row {n}, {table}')

    return errors


def validate_package_context(tables):
    """Return errors when package-level domain context is not available."""
    errors = []
    if tables.get('Crop_observations_timeseries'):
        required = {
            'Plot_seasons', 'Treatments', 'Genotypes',
            'Planting_events', 'Harvest_events',
        }
        missing = sorted(required - set(tables))
        if missing:
            errors.append(
                'Crop_observations_timeseries requires '
                f'{", ".join(missing)} for cross-table date validation; '
                'define these tables before registering the package'
            )
    return errors


def validate_package_domains(tables):
    """Return cross-table agronomic errors for a normalized package."""
    errors = []
    plot_seasons = {row.get('plot_season_id', ''): row
                    for row in tables.get('Plot_seasons', [])}
    treatments = {row.get('treatment_id', ''): row
                  for row in tables.get('Treatments', [])}
    genotypes = {row.get('genotype_id', ''): row
                 for row in tables.get('Genotypes', [])}
    planting_events = {row.get('planting_treatment_id', ''): row
                       for row in tables.get('Planting_events', [])}
    harvest_dates = defaultdict(list)
    harvest_rows = defaultdict(list)
    for row in tables.get('Harvest_events', []):
        harvest_rows[row.get('harvest_treatment_id', '')].append(row)
        value = row.get('harvest_operations_date', '')
        if value:
            harvest_dates[row.get('harvest_treatment_id', '')].append(_date_value(value))

    for row_number, observation in enumerate(tables.get('Crop_observations_timeseries', []), 2):
        plot_season_id = observation.get('plot_season_id', '')
        plot_season = plot_seasons.get(plot_season_id)
        if not plot_season:
            continue
        treatment = treatments.get(plot_season.get('treatment_id', ''))
        if not treatment:
            continue
        genotype = genotypes.get(treatment.get('genotype_id', ''))
        if not genotype or genotype.get('crop_id', '') not in SINGLE_SEASON_CROP_CODES:
            continue

        planting = planting_events.get(treatment.get('planting_treatment_id', ''))
        planting_date = _date_value(planting.get('planting_date', '')) if planting else None
        harvest_treatment_id = treatment.get('harvest_treatment_id', '')
        linked_harvest_rows = harvest_rows.get(harvest_treatment_id, [])
        linked_harvests = harvest_dates.get(harvest_treatment_id, [])
        if not planting_date:
            errors.append(
                f'Crop_observations_timeseries row {row_number}, plot_season_id={plot_season_id}: '
                'single-season crop requires a concrete planting_date for date validation'
            )
        if not linked_harvest_rows or len(linked_harvests) != len(linked_harvest_rows):
            errors.append(
                f'Crop_observations_timeseries row {row_number}, plot_season_id={plot_season_id}: '
                'single-season crop requires a concrete harvest_operations_date for date validation'
            )
        if not planting_date or not linked_harvests:
            continue
        harvest_date = max(linked_harvests)
        if planting_date > harvest_date:
            errors.append(
                f'Plot_seasons {plot_season_id}: planting date {planting_date.isoformat()} '
                f'is after harvest date {harvest_date.isoformat()}'
            )
            continue

        observation_date = _date_value(observation.get('date_of_measurement', ''))
        if observation_date and not (planting_date <= observation_date <= harvest_date):
            errors.append(
                f'Crop_observations_timeseries row {row_number}, plot_season_id={plot_season_id}: '
                f'date_of_measurement {observation_date.isoformat()} is outside '
                f'{planting_date.isoformat()}..{harvest_date.isoformat()} for single-season crop '
                f'{genotype.get("crop_id", "")}'
            )

    return errors


def raise_domain_errors(errors):
    """Raise one shared contract error for domain diagnostics, if needed."""
    if errors:
        raise ContractValidationError('\n'.join(errors), [{'message': error} for error in errors])
