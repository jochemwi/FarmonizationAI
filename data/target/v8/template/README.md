# Target data structure contract

This contract defines CSV tables for daily crop-model inputs: plot-season context, weather, soil, treatments, management events, and observations.

Use [fill_api.py](../fill_api.py) to write tables and validate packages. It **enforces the schema and deterministic constraints summarized below**. Row checks run when writing a table; cross-table checks run during package validation.

Complete packages must include all declared tables; partial packages must still provide the linked records and cross-table context required by their data. Unit conversion, daily aggregation, and source-to-target interpretation must be completed upstream and are not guaranteed by API validation.

## Design

- **Observation timing:** soil-layer, crop, and other observations each have `*_summary` and `*_timeseries` tables with the same measurement variables. Only an explicit `date_of_measurement` places an observation in timeseries. Measurements such as `anthesis_date` do not establish the observation date.
- **Daily resolution:** consolidate repeated source records upstream. Use daily means for numeric state observations and daily sums for additive application amounts, preserving the meaning of dates, methods, materials, and codes.
- **Variable identity:** preserve ICASA variable names and UIDs. `Variable_name` identifies the semantic variable; `Target_column` names the CSV/API column. Contract-specific fields have no ICASA UID.

## Filling rules enforced by the API

| Topic | Rule |
| --- | --- |
| Required fields | `required` columns must be present and non-blank. `required_nullable` columns must be present but may be blank. `optional` columns may be omitted. |
| Missing values | Use empty CSV cells. Python `None` and JSON `null` are normalized to empty cells; literal text such as `"None"` is not a missing-value marker. |
| Value formats | Use declared types, dates in `YYYY-MM-DD`, and field-specific codes. Preserve code leading zeros, such as BBCH `00`. |
| Record identity | Each table's primary key must be unique. Duplicate logical records are rejected. |
| Relationships | Referenced IDs must exist in the package. `group_plot_season_ids` is a semicolon-separated list of unique existing plot-season IDs and must include the row's own `plot_season_id` when present. The API trims and sorts the list. |
| Soil and event context | Supply soil boundaries together, with top depth no greater than bottom depth. Each event phase requires a date, phenology-time, or event-time value. |
| Crop-season dates | For crops subject to the single-season rule, dated crop observations require linked planting and harvest dates and must fall within that interval. |

Field meanings and units are listed in [scheme/variables.csv](../scheme/variables.csv); locate a field by `Sheet_name` and `Target_column`. Convert source values to the stated unit before filling. Record uncertain mappings as `unresolved` in the mapping dictionary.

## Where to find details

| Need | File |
| --- | --- |
| Choose a table; check row grain, keys, and relationships | [scheme/table.csv](../scheme/table.csv) |
| Look up field meaning, unit, type, and requiredness | [scheme/variables.csv](../scheme/variables.csv) |
| Start filling or document source-to-target mappings | [template/](./) and [mapping dictionary](dictionary.csv) |
| Look up code vocabularies and original ICASA definitions | [scheme/](../scheme/) and [scheme/icasa_variable.csv](../scheme/icasa_variable.csv) |
| Use writing and validation commands | [fill_api.py](../fill_api.py) |
| Inspect the full implemented checks | [database_validation.py](../database_validation.py) and [domain_validation.py](../domain_validation.py) |

## Submission for this test

Submit the 35 table CSVs using the supplied filenames and headers. Keep this README and `dictionary.csv` outside `submission/`; the dictionary documents mappings rather than target records. Keep processing code and uncertainty notes outside the submitted CSV directory. Preserve uncertain mappings as unresolved rather than inventing measurements.

Keep source identifiers consistent across related tables. For workbook-local plot-season IDs, use field scopes F01–F06 for SYNF01–SYNF06 and qualify each local ID, for example `F01::11`. A source field alias followed by `::` is also accepted. Use the same qualified IDs in references and semicolon-separated group lists. Global source aliases are accepted; controlled vocabulary fields such as `crop_id` require the canonical contract code.
