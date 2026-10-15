# Agricultural data harmonization task

This task tests whether noisy agricultural source data can be reconstructed into a consistent set of target CSV tables. Interpret the source records, resolve supported inconsistencies, and organize the data using the supplied harmonization template.

## Locations

| Location | Purpose |
| --- | --- |
| `/app/input/noise_data/` | Input workbooks, weather files and soil records to process. |
| `/app/data/target/v8/template/` | Target CSV templates and the template README with field and submission rules. |
| `/app/data/target/v8/scheme/` | Field meanings, units, table relationships and code lists. |
| `/app/output/submission/` | Place your completed target CSV tables here. |
| `/app/workspace/` | Your working area: processing code, mapping notes, uncertainty notes and `dictionary.csv`. |

## Workflow

1. Read the files in `/app/input/noise_data/` and the template README. Use the source context and field definitions to understand records, units and relationships.
2. Process the data into the 35 target tables. Convert units and consolidate records where the template requires it. Preserve missing values and document unresolved interpretations rather than inventing answers.
3. Copy only the 35 table CSVs from the template folder into `/app/output/submission/`, using the template filenames, and fill them there. dictionary.csv in the template folder is not one of the 35 tables, so do not copy it. Keep mapping notes, code and any dictionary you create in `/app/workspace/`, outside the submission folder. If you create a dictionary, write it to `/app/workspace/dictionary.csv`.

## ID handling

Use source IDs consistently across related tables and follow the template guide for workbook-local IDs. Vocabulary fields such as `crop_id` still require the template's canonical codes.