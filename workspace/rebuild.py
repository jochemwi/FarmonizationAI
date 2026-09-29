import csv,os
from collections import defaultdict
IN='/app/workspace/cleaned.csv'; OUT='/app/output';os.makedirs(OUT,exist_ok=True)
rows=list(csv.DictReader(open(IN)))
def write(name,cols,data):
 with open(os.path.join(OUT,name),'w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(data)
field=[r for r in rows if r['source_table']=='Field_obs'];soil=[r for r in rows if r['source_table']=='Soil_initial'];bio=[r for r in rows if r['source_table']=='Biomass_timeseries']
write('experiment.csv',['experiment_id','experiment_name'],[{'experiment_id':'ANMG9901','experiment_name':'Potato trial Colombia 1999'}])
write('treatment.csv',['experiment_id','treatment_id','treatment_name','n_applied_kg_ha'],[{'experiment_id':'ANMG9901','treatment_id':r['plot_id'],'treatment_name':r['trt_name'],'n_applied_kg_ha':r['n_applied_kg_ha']} for r in field])
write('plot.csv',['experiment_id','plot_id','treatment_id','location','crop_type','variety','planting_date','harvest_date'],[{'experiment_id':'ANMG9901','plot_id':r['plot_id'],'treatment_id':r['plot_id'],'location':r['location'],'crop_type':r['crop_type'],'variety':r['variety'],'planting_date':r['planting_date'],'harvest_date':r['harvest_date']} for r in field])
write('soil_initial.csv',['experiment_id','sample_id','sample_date','depth_cm','bulk_density_g_cm3','organic_carbon_pct','total_n_pct','ph_water','ph_buffer','p_extractable_mg_kg','k_cmol_kg'],[{'experiment_id':'ANMG9901',**{k:r[k] for k in ['sample_id','sample_date','depth_cm','bulk_density_g_cm3','organic_carbon_pct','total_n_pct','ph_water','ph_buffer','p_extractable_mg_kg','k_cmol_kg']}} for r in soil])
write('biomass_observation.csv',['experiment_id','observation_id','treatment_id','obs_date','tops_roots_dw_kg_ha','tuber_fw_mg_ha','tuber_dw_kg_ha','stem_dw_kg_ha','leaf_dw_unresolved_unit','dead_material_kg_ha','lai_m2_m2','leaf_area_index_m2_m2','root_dw_kg_ha','note'],[{'experiment_id':'ANMG9901','observation_id':r['record_key'],'treatment_id':r['trt'],'obs_date':r['obs_date'],**{k:r[k] for k in ['tops_roots_dw_kg_ha','tuber_fw_mg_ha','tuber_dw_kg_ha','stem_dw_kg_ha','leaf_dw_unresolved_unit','dead_material_kg_ha','lai_m2_m2','leaf_area_index_m2_m2','root_dw_kg_ha','note']}} for r in bio])
