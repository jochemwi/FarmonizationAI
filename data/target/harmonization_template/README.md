# target_template data contract

## General

target_template organizes source-supported agricultural data into plot-seasons, plots, treatments, genotypes, weather, soil, management events, observations, and variable mappings. Preserve agricultural meaning, record relationships, measurement basis, and uncertainty when reconstructing source data.

- **Definitions:** Use [table.csv](scheme/table.csv) for table scope, record grain, keys, and relationships; [variables.csv](scheme/variables.csv) for field meanings, units, types, requiredness, and storage; and the [code vocabularies](scheme/) for registered values. Consult `Supplementary_information` and the [ICASA adaptation decisions](scheme/icasa_variable.csv) when a definition or source-to-target relationship needs clarification.

- **Output:** Place every declared table, including [Dictionary.csv](template/Dictionary.csv), in the same `data/` directory. Dictionary describes the mappings used by the accompanying data and records explicit exclusions. Keep assessments and other reports outside that directory.

- **Source meaning:** Distinguish measurement object, tissue, chemical form, dry/fresh-weight basis, unit, date, soil layer, statistic, and represented scope before choosing a target. Similar names or compatible units alone do not establish equivalence. Preserve ICASA variable identities; `Variable_name` identifies the variable and `Target_column` identifies its output column.

- **Scope:** Represent field data and source-supported derived quantities. Exclude explicitly simulation-only quantities; a physical variable's use in a crop model does not by itself make it simulation-specific. Within a plot-season, the harvested crop is the linked genotype's crop; pest, disease, and lodging observations belong in Other observations.

- **Missing values and codes:** Preserve unknown values as empty cells and retain reported zero values. Required fields need a value; required-nullable fields remain present even when blank. Use declared types and field-specific bounds, dates in `YYYY-MM-DD`, and registered codes with their leading zeros. Descriptions do not replace code values.

- **Identity and relationships:** Distinct entities require distinct keys; references to the same entity reuse its key. A plot-season links one plot to its assigned treatment. Choose technical IDs from source identity, grain, and relationships, and preserve the source correspondence. IDs do not establish agricultural equivalence or resolve uncertain associations. Retained parent records must be used by a plot-season context.

- **Observation timing:** Put soil, crop, and Other observations in timeseries only when `date_of_measurement` is known; otherwise use summary. A date-valued measurement, configuration date, or inferred management date does not establish the observation's measurement date. Preserve distinct events and timing measures.

- **Observation selection:** Retain one selected row per complete observation key and one value per field. Resolve measured/derived alternatives and conflicting values from source evidence. Do not change dates, layers, or scope merely to store competing interpretations; explain the selection and preserve relevant evidence.

- **Shared observations:** Expand shared data into a row for each represented plot-season. Every copy retains the same complete `group_plot_season_ids` list, includes its own anchor, and has equal data values, including missing values. Different groups, dates, and layers remain distinct. Semicolons separate group members and cannot occur inside a plot-season ID.

- **Soil and initial configurations:** Soil profiles define the soil configuration selected by a plot; initial conditions define the starting configuration selected by a treatment. Their layer tables retain vertical structure. Store actual property/state values in observations and select them through configuration references, including categorical values and codes. IDs, relationships, configuration dates, boundaries, scope, and comments remain direct values. Determine configuration purpose from source evidence.

- **Configuration references:** Select an existing observation value by its complete primary key and field, including explicitly blank nullable key components. The selected value must exist, be nonblank, and represent the same physical variable, unit, and type. Keep references consistent when identities change. Configuration dates and boundaries need not equal measurement dates or sampled boundaries; preserve each one's source meaning.

- **Soil layers:** Preserve source-supported layer boundaries. Supply top and bottom together, with nonnegative depths and top no deeper than bottom; leave both blank for a profile-wide or aggregate observation. Do not invent a layer or replace a measurement date with an initial-state date.

- **Management events:** Preserve each table's declared event grain. Each event phase needs a date, phenology time, or event time. Consolidate only records sharing the same complete key; distinguish materials, within-day order, and start/end timing where declared. Sum compatible additive amounts, reconcile single-valued categories, and justify other consolidation from source evidence.

- **Crop-season context:** For crops covered by the single-season rule, dated crop observations require linked planting and harvest dates and fall within that interval. This crop-observation restriction does not apply indiscriminately to all Other observations.

- **Units:** Convert reported values to the target field's unit while preserving chemical, tissue, mass, area, and time bases. Ground-area mass uses kg/ha and daily mass flux uses kg/(ha.d); per-plant quantities, concentrations, counts, radiation, and other quantities retain their declared units. Apply a conversion only to values actually reported on the corresponding source basis.

- **Fertilizer amounts:** `fertilizer_total_amount` is product mass. Reported elemental N/P/K amounts do not establish product mass and must not be summed to fill it. Leave product mass blank when unknown; derive it only from source-supported composition.

- **Environmental modifiers:** Pair each supplied value with its operation. Add/subtract represent a change in the declared unit; replace represents an absolute value; multiply represents a source-supported factor. Temperature changes are intervals, while replacement temperatures are absolute. A known operation with an unknown value needs an explanation and remains incomplete. Zero is a supplied value.

- **Mapping records:** Record one source-to-target relationship or explicit exclusion per Dictionary row. Split one-to-many mappings; for many-to-one derivations, record each contributing relationship and the complete rule. Preserve source file, variable identifiers, definitions, and units. Source filenames are relative to the dataset root. Dictionary coverage must correspond to the actual reconstructed data.

- **Mapping targets:** For an existing target_template variable, copy the exact table, variable name, code, definition and unit from the scheme. For a proposed variable, provide complete target metadata under the proposal requirements below. All five target fields are required except for exclusions. `target_code_display` identifies the variable, not a category value.

- **Mapping judgments:** Use the [registered mapping statuses](scheme/Dictionary_mapping_status_codes.csv) for the relationships actually applied. Record applicability conditions for conditional mappings and write values only where those conditions are established.

- **Exclusions:** Use `excluded` for an explicit decision not to collect a source variable or when the source variable has no observed values. Preserve source metadata, leave target fields and ontology ID blank, and explain the reason in `mapping_scheme`. A missing cell does not exclude an otherwise collected variable. The same source identity cannot be both excluded and mapped.

- **New variables, codes, and ontology links:** Prefer a suitable existing variable. Propose a new code when only a source category is missing, or a needed new variable when Dictionary does not cover the physical meaning. Provide an identifiable ontology reference or clearly proposed identifier, complete target metadata, source evidence and intended table. When source meaning, definition, type, unit, table scope, grain and relationships meet template requirements, write the source-supported values into the appropriate table and record the mapping as `proposed`; pending registration does not prevent writing eligible data. Similar labels do not establish equivalence.

- **Comments:** Keep original comments in `source_comments`; explain applied non-standard transformations, assumptions and their basis in `ai_comments`. Leave comments blank when unnecessary.

## Writing and validation

`write_table` and `write_dictionary` save partial content so filling and correction can proceed incrementally. Missing fields become blank cells; supplied values still undergo field-name, type, format and code checks. Incomplete keys and metadata can be saved, but merge requires explicitly supplied complete, unique keys and still rejects conflicting records. Use replace when correcting unfinished records. Saving does not establish that a table or package is valid.

`validate_rows`, `validate_dictionary_rows`, `validate_dictionary_file` and `validate_package` remain strict. They check required values, complete metadata and applicable relationships. Run `validate_package(..., complete=True, final=True)` before delivery to check file coverage, references, shared groups and final context requirements.

Dictionary has 17 columns, including `target_data_type` and `target_storage`. Data types are `text`, `int`, `single` and `date`. Leave `target_storage` blank for direct values; otherwise provide source fields as `Table.Target_column`, separated by semicolons. Existing-variable metadata must match the scheme. Proposed variables use their target variable name as the output column and extend an existing table without changing its keys or relationships.

Write `data/Dictionary.csv` before tables that use proposed variables. `write_table` reads the colocated Dictionary automatically; Python callers may instead pass `dictionary=rows`, and CLI writers may use `--dictionary <path>`. Package validation reads its own Dictionary and uses the same local field definitions. The global scheme is unchanged.

Incomplete Dictionary rows do not block writing existing fields. A proposed column becomes writable once its table, column name, proposed status and data type are declared; blank Storage declares direct values, while nonblank Storage must identify valid sources. Explanatory metadata can be completed later. Supplied definitions cannot contradict each other or the base scheme.

```python
from harmonization_template.fill_api import write_dictionary, write_table, validate_package

write_dictionary(mapping_rows, output / "Dictionary.csv")
write_table("Other_observations_summary", observation_rows, output / "Other_observations_summary.csv")
validate_package(output, complete=True, final=True)
```

Foreign-key references retain their ordinary IDs or declared ID lists. Value-reference cells use `obs:<source_table>?<complete primary-key query>#<column>` and must select one of the field's declared Storage sources. Sources must be directly stored fields in another table with matching variable identity, unit and data type. Final validation checks that the selected record and nonempty value exist. Group observations retain their existing shared-copy rules.

For proposed category codes, `mapping_scheme` supplies an explicit vocabulary as JSON, for example `{"codes": {"FARMONIZER:inland": "Inland category"}, "rule": "Map the documented source category to this proposed code."}`. Use namespaced identifiers and nonempty definitions. The vocabulary applies only to the current package, including when it extends an existing variable. A reference to a code field uses its source vocabulary.
