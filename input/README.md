# Agricultural data harmonization task

This task tests whether noisy agricultural source data can be reconstructed into a consistent set of target CSV tables. Interpret the source records, resolve supported inconsistencies, and organize the data using the supplied harmonization template. The dataset contains 10 experiments and 100 plot-seasons.


## Locations

| Location | Purpose |
| --- | --- |
| `/app/input/noise_data/` | Input workbooks, weather files and soil records to process. |
| `/app/data/target/harmonization_template/README.md` | The data contract: field, mapping, Dictionary and validation rules. Read it fully before building. |
| `/app/data/target/harmonization_template/template/` | Target CSV templates (35 tables plus `Dictionary.csv`). |
| `/app/data/target/harmonization_template/scheme/` | Field meanings, units, table relationships and code lists. |
| `/app/output/submission/` | Put the 35 tables and `Dictionary.csv` here. |
| `/app/workspace/` | Your working area: processing code, mapping notes and uncertainty notes. |

## Workflow

1. Read the files in `/app/input/noise_data/` and `/app/data/target/harmonization_template/README.md`. Use the source context and field definitions to understand records, units and relationships.
2. Copy all 36 CSVs from `/app/data/target/harmonization_template/template/` (the 35 tables and `Dictionary.csv`) into `/app/output/submission/`, keeping the template filenames.
3. Fill `Dictionary.csv` first, before any table that uses a proposed variable. Then fill the 35 tables. Convert units and consolidate records where the template requires it. Keep missing values as missing, and document unresolved interpretations instead of inventing answers.
4. Keep code, notes and reports in `/app/workspace/`, outside the submission folder. The submission folder holds only the 36 CSVs.

## ID handling

Use source IDs consistently across related tables and follow the template guide for workbook-local IDs. Vocabulary fields such as `crop_id` still require the template's canonical codes.