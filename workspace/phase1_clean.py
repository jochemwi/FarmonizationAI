import zipfile,xml.etree.ElementTree as ET,csv,json,re
from datetime import datetime
SRC='/app/data/ANMG9901_messy.xlsx'; NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def iso(x):
 x=str(x).strip()
 for f in ['%d/%m/%Y','%Y-%m-%d','%d-%m-%Y','%B %d, %Y','%b %d %Y','%d %B %Y','%d %b %y','%d/%m/%y','%d-%m-%y','%b %d, %Y','%Y/%m/%d']:
  try:return datetime.strptime(x,f).date().isoformat()
  except:pass
 return x if x else '-99'
def val(x): return '-99' if not str(x).strip() or str(x).strip().upper() in ('NA','N/A','NULL') else str(x).strip()
def rows(z,target):
 r=ET.fromstring(z.read(target)); out=[]
 for row in r.findall('.//m:sheetData/m:row',NS):
  d={}
  for c in row.findall('m:c',NS):
   col=re.match('[A-Z]+',c.attrib['r']).group(); t=c.find('m:is/m:t',NS); v=c.find('m:v',NS);d[col]=t.text if t is not None else (v.text if v is not None else '')
  out.append(d)
 return out
with zipfile.ZipFile(SRC) as z:
 wb=ET.fromstring(z.read('xl/workbook.xml')); rel=ET.fromstring(z.read('xl/_rels/workbook.xml.rels')); rr={x.attrib['Id']:x.attrib['Target'].lstrip('/') for x in rel}; all=[]
 for sh in wb.find('m:sheets',NS):
  name=sh.attrib['name']; rid=sh.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']; rs=rows(z,rr[rid])
  if name=='Field_obs':
   data=rs[3:6]; cols=['plot_id','trt_name','location','planting_date','harvest_date','crop_type','variety','n_applied_kg_ha','yield_fresh_t_ha','notes']
   for i,r in enumerate(data,1):
    a=[val(r.get(chr(65+j),'')) for j in range(10)]; a[3]=iso(a[3]);a[4]=iso(a[4]);a[1]=a[1].upper();a[2]=a[2].upper();a[5]={'PT':'POTATO'}.get(a[5].upper(),a[5].upper());a[6]=a[6].upper();a[7]=re.match(r'[0-9.]+',a[7]).group() if re.match(r'[0-9.]+',a[7]) else '-99';all.append(dict(source_table=name,source_row=i,record_key='PLOT_'+a[0],**dict(zip(cols,a))))
   data=rs[11:14];cols=['sample_id','sample_date','depth_cm','bulk_density_g_cm3','organic_carbon_pct','total_n_pct','ph_water','ph_buffer','p_extractable_mg_kg','k_cmol_kg']
   for i,r in enumerate(data,1):
    a=[val(r.get(chr(65+j),'')) for j in range(10)];a[1]=iso(a[1]);all.append(dict(source_table='Soil_initial',source_row=i,record_key='SOIL_'+a[0],**dict(zip(cols,a))))
  else:
   cols=['trt','obs_date','tops_roots_dw_kg_ha','tuber_fw_mg_ha','tuber_dw_kg_ha','stem_dw_kg_ha','leaf_dw_unresolved_unit','dead_material_kg_ha','lai_m2_m2','leaf_area_index_m2_m2','root_dw_kg_ha','note']
   for i,r in enumerate(rs[2:],1):
    a=[val(r.get(chr(65+j),'')) for j in range(12)];a[1]=iso(a[1]);all.append(dict(source_table=name,source_row=i,record_key=f'TRT_{a[0]}_{a[1]}_{i}',**dict(zip(cols,a))))
fields=sorted({k for x in all for k in x})
with open('/app/workspace/cleaned.csv','w',newline='') as f: w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:x.get(k,'-99') for k in fields} for x in all)
classes={c:('structural' if c in ('record_key','source_table','source_row','plot_id','trt','trt_name','sample_id') else 'context' if c in ('location','planting_date','harvest_date','crop_type','variety','notes','obs_date','note','depth_cm') else 'measurement') for c in fields}
profile={'source_file':SRC,'tables':{'Field_obs':{'primary_key':'plot_id','foreign_keys':[]},'Soil_initial':{'primary_key':'sample_id','foreign_keys':[]},'Biomass_timeseries':{'primary_key':'record_key','foreign_keys':['trt -> Field_obs.plot_id (assumed; confirm)']}},'column_classification':classes,'missing_value':'-99','uncertainties':['ICASA schema file is absent at /app/src/rag/icasa_schema.json.','Biomass leaf DW unit is unspecified and remains unresolved.','TRT-to-plot relationship is inferred from matching numeric IDs and should be confirmed.']}
json.dump(profile,open('/app/workspace/schema_profile.json','w'),indent=2)
print('cleaned',len(all),'records')
