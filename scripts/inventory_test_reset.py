"""Read-only inventory for a proposed test reset. Never delete or update."""
import json
from pathlib import Path
import deploy_environment_management as dv

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/test-reset-20261003'
OUT.mkdir(parents=True,exist_ok=True)
dv.OUT=OUT

def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    table=dv.request("EntityDefinitions(LogicalName='cr6cb_evidencecase')?$select=LogicalName,EntitySetName,PrimaryIdAttribute,PrimaryNameAttribute")
    columns=dv.request("EntityDefinitions(LogicalName='cr6cb_evidencecase')/Attributes?$select=LogicalName,AttributeType,AttributeOf,IsValidForRead")
    save('case-table.json',table);save('case-columns.json',columns)
    allowed={r['LogicalName'] for r in columns['value'] if r['LogicalName'].startswith('cr6cb_') and r.get('AttributeOf') is None and r.get('IsValidForRead') and r.get('AttributeType')!='Virtual'}
    reporting={c for c in allowed if any(s in c for s in ('filename','url','status','archive','environment','server','count','review'))}
    select=sorted(reporting|{table['PrimaryIdAttribute'],table['PrimaryNameAttribute'],'createdon','modifiedon'})
    path=table['EntitySetName']+'?$select='+','.join(select)+'&$top=100&$orderby=createdon asc'
    records=dv.request(path)
    if '@odata.nextLink' in records: raise RuntimeError('More than 100 cases; use pagination before proposing deletion.')
    save('cases.json',records)
    case_ids={x[table['PrimaryIdAttribute']] for x in records['value']}
    file_table=dv.request("EntityDefinitions(LogicalName='cr6cb_evidencefile')?$select=LogicalName,EntitySetName,PrimaryIdAttribute")
    files=dv.request(file_table['EntitySetName']+'?$select=cr6cb_evidencefileid,_cr6cb_evidencecase_value,cr6cb_filename,cr6cb_filerole&$top=100')
    if '@odata.nextLink' in files: raise RuntimeError('Input file list needs paging.')
    files['value']=[x for x in files['value'] if x.get('_cr6cb_evidencecase_value') in case_ids]
    save('case-input-files.json',files)
    file_ids={x['cr6cb_evidencefileid'] for x in files['value']}
    notes=dv.request("annotations?$select=annotationid,filename,_objectid_value,filesize&$filter=(objecttypecode eq 'cr6cb_evidencecase' or objecttypecode eq 'cr6cb_evidencefile') and isdocument eq true&$top=100")
    if '@odata.nextLink' in notes: raise RuntimeError('Attachment list needs paging.')
    notes['value']=[x for x in notes['value'] if x.get('_objectid_value') in case_ids|file_ids]
    save('case-attachments.json',notes)
    settings=dv.request('cr6cb_evidencedestinations?$select=cr6cb_evidencedestinationid,cr6cb_environment,cr6cb_server,cr6cb_isactive,cr6cb_environmentenabled&$top=100')
    if '@odata.nextLink' in settings: raise RuntimeError('Settings need pagination.')
    save('settings.json',settings)
    print('Read-only case inventory:',len(records['value']))
    print('Related input file rows:',len(files['value']))
    print('Related input attachments:',len(notes['value']))
    print('Cases with saved result Excel links:',sum(bool(x.get('cr6cb_excelurl')) for x in records['value']))
    print('Cases with saved SharePoint folder links:',sum(bool(x.get('cr6cb_sharepointfolderurl')) for x in records['value']))
    print('Read-only environment/server pair inventory:',len(settings['value']))
    print('Case column names:',','.join(sorted(allowed)))
    print('No deletion or update performed.')

if __name__=='__main__': main()
