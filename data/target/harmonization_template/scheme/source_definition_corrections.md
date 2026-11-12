# Source definitions and target corrections

The source baseline is the five variable files in `knowledge/ontology/ICASA`: Metadata, Management_info, Soils_data, Weather_data, and Measured_data. All 1,384 catalog records retain their original source filename, variable name, code, description, unit, type, classification, and bounds. Corrected definitions or existing replacement fields belong in `variables.csv`; `adapt_operation=adapt_fix` and `Decision_reason` connect the original source variable to those targets. The ontology files are read-only. The twelve reviewed corrections below use `adapt_fix`; ordinary conversions and representation mappings use `map` without an additional flag column. A selected correction can remain inferred, as documented for 610.

Two catalog descriptions had text corruption relative to that baseline: 138 replaced the quoted cultivar-class example, and 302 replaced the irrigation example's ellipsis. Their source descriptions have been restored verbatim. The target description for 302 also retains the original wording.

| UID | Original issue | Selected target definition or representation |
| --- | --- | --- |
| 141 | A program/company name is declared as `number/single`. | Retain the breeding-program name as text. |
| 331 | The manganese name and `kg[Mn]/ha` unit conflict with the description's elemental Mg. | Seasonal manganese amount as elemental Mn. |
| 610 | Base saturation names a proportion, while `cmol/kg` denotes an amount per soil mass. | Retain `cmol/kg` and explicitly define exchangeable base cation content under the inferred legacy SLBS/TOTBAS interpretation. This interpretation remains uncertain. |
| 611 | Electrical conductivity is given as `seimen`, omitting the length basis. | Soil electrical conductivity in `dS/m`. Convert from the dataset's actual unit and retain its measurement basis; the malformed catalog unit does not establish a conversion factor. |
| 612 | APSIM KL is declared as generic `number`, omitting its daily basis. | Crop-specific soil-layer water-extraction coefficient in `1/d`; the source KL numerical coefficient is unchanged. |
| 677 | A duration label is paired with a percentage unit without defining the denominator. | Monthly mean daily bright sunshine as percent of daylength, following DSSAT SHMN. |
| 687 | ALPHA is called a rainfall scale parameter and assigned `1/mm2`. | Dimensionless monthly gamma-distribution shape parameter under the DSSAT ALPHA convention. Different source parameterizations require interpretation, not a fixed unit multiplier. |
| 787 | A calendar-event date is described with generic `day/single`, without specifying its time basis. | First-square date in `YYYY-MM-DD`. Resolve source DOY or DAP and its anchor before conversion. |
| 848 | The catalog's `mg/ha` unit is implausible for harvested tuber yield. | Tuber fresh weight at harvest in `kg/ha`, as selected for this contract. Actual dataset units determine the conversion; the catalog entry alone is insufficient to rescale data. |
| 932 | A textual measurement comment declares the mass-per-area unit `t/ha`. | Copy the original comments into the existing text `source_comments` fields; no mass conversion applies. The exact targets and source-unit conflict are recorded in `Decision_reason`. |
| 1348 | The variable name and `kg/(ha.d)` describe a rate, but the description says "date". | Floodwater denitrification rate as N, retaining `kg/(ha.d)`. |
| 1393 | A standing population is paired with the rate unit `number/(m2.d)`. | Standing plant population density in `number/m2`; this corrects the definition rather than integrating a rate. |

Representation mappings are recorded separately in their reasons. The 52 retained variables with source `Unit_or_type=date` and `Data_type=single` use the target `date` type and `YYYY-MM-DD` format. Their numeric source date encoding is a legacy representation, not automatically a scientific definition error. Station identifiers (693) similarly map their code/numeric representation to text. Ordinary mass-unit conversions also remain mappings without implying that the source unit was erroneous.

Vegetative age (959) uses `keep` with its original ICASA description; `Supplementary_information` clarifies physiological development time rather than correcting a demonstrated source error. Its unit remains `day` as development days; the source determines the calculation and accumulation start. DSSAT distinguishes CDVD from calendar age CDAY, and CROPGRO provides an example of temperature-based physiological days, without establishing a universal CDVD formula. Raw degree-days require a documented conversion. The evidence and user decision are recorded in `Decision_reason`.

Developmental DOY and DAP variables 738, 740, 741, 742, 744, 748, 749, 750, 751, and 753 remain `keep` with their original units; their consolidation is deferred to post-processing. The separate conflict correction for 787 does not change that decision. Shared original codes, such as SCGED for 1072 and 1075, retain their source values and are distinguished by variable identity.

## Supporting evidence

- [DSSAT User Guide, Vol. 2](https://dssat.net/wp-content/uploads/2011/10/DSSAT-vol2.pdf) associates SLBS with TOTBAS and an amount unit; it supports the legacy interpretation for 610 without confirming the intended meaning of every dataset.
- [SLU soil chemistry](https://www.slu.se/en/about-slu/organisation/departments/soil-environment/environmental-monitoring/markinfo-eng/soil-chemistry/cation-exchange-capacity-and-base-saturation/) distinguishes percentage base saturation from exchange capacity and exchangeable cation amounts.
- [USDA-NRCS electrical conductivity guidance](https://www.nrcs.usda.gov/sites/default/files/2022-11/Electrical%20Conductivity%20%28EC%29%20-%20Soil%20Health%20Guide_0.pdf) reports soil EC in dS/m and distinguishes measurement bases; unit conversion alone does not change extraction methods.
- [APSIM soil-water parameter guide](https://www.apsim.info/wp-content/uploads/2019/10/Parameters-for-soil-water-Ver24.pdf) defines KL as a fraction of available water extracted per day.
- [DSSAT User Guide, Vol. 3](https://dssat.net/wp-content/uploads/2011/10/DSSAT-vol3.pdf) defines SHMN as percent of daylength.
- [DSSAT WEATHER.CDE](https://github.com/DSSAT/dssat-csm-os/blob/develop/Data/WEATHER.CDE) identifies ALPHA as the monthly gamma shape parameter; the [NIST gamma-distribution definition](https://www.itl.nist.gov/div898/handbook/eda/section3/eda366b.htm) distinguishes shape from scale.
