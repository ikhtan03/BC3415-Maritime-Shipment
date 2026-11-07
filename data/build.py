import os,json,csv,copy,zipfile
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
ROOT=os.path.dirname(__file__)
if (os.path.exists(os.path.join(ROOT, "test_cases")) or
        os.path.exists(os.path.join(ROOT, "dataset_manifest.csv"))):
    raise SystemExit(
        "Dataset already exists. Generation stopped to prevent overwriting "
        "PDFs, ground truth, and augmented answer keys."
    )
base={"shipment_id":"SG-DEMO-001","movement_type":"import","shipper":"Meridian Components Sdn Bhd (FICTIONAL)","consignee":"Harbour Tech Pte Ltd (FICTIONAL)","carrier":"Example Ocean Lines (FICTIONAL)","vessel":"DEMO MERIDIAN","voyage":"DM102A","port_of_loading":"Port Klang, Malaysia","port_of_discharge":"Singapore","terminal":"PSA Singapore (scenario assumption)","shipment_date":"2026-10-15","document_reference":"BL-DEMO-001","invoice_number":"INV-DEMO-001","container_id":"MSCU6639870","seal_number":"SEAL-DEMO-104","cargo_description":"Paint products, packaged in steel drums (illustrative DG cargo)","proper_shipping_name":"PAINT","un_number":"UN1263","dg_class":"3","package_count":100,"package_type":"Steel drums (illustrative; verify packaging suitability)","gross_cargo_weight_kg":18500,"net_cargo_weight_kg":17000,"hs_code":"NOT_VERIFIED","declared_invoice_value_usd":54000}
# Valid ISO 6346 checksum computed instead of assuming sample ID checksum
mapping={str(i):i for i in range(10)}
for i,c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
 v=10+i
 while v%11==0:v+=1
 mapping[c]=v
prefix='MSCU663987'
total=sum(mapping[c]*(2**i) for i,c in enumerate(prefix)); check=(total%11)%10
base['container_id']=prefix+str(check)
scenarios=[('S01_correct',[]),('S02_weight_mismatch',[('packing_list','gross_cargo_weight_kg',19500)]),('S03_container_mismatch',[('bill_of_lading','container_id','MSCU663988'+str((check+1)%10))]),('S04_missing_dgd',[('dangerous_goods_declaration','missing',True)]),('S05_dg_class_conflict',[('dangerous_goods_declaration','dg_class','9')]),('S06_multiple_errors',[('packing_list','gross_cargo_weight_kg',19500),('bill_of_lading','container_id','MSCU663988'+str((check+1)%10)),('dangerous_goods_declaration','dg_class','9')])]
# use distinct valid alternative container
altprefix='MSCU663988'; altcheck=(sum(mapping[c]*(2**i) for i,c in enumerate(altprefix))%11)%10
scenarios=[(n,[(d,k,altprefix+str(altcheck) if k=='container_id' else v) for d,k,v in changes]) for n,changes in scenarios]
doc_fields={
'bill_of_lading':['document_reference','shipment_date','shipper','consignee','carrier','vessel','voyage','port_of_loading','port_of_discharge','container_id','seal_number','cargo_description','package_count','gross_cargo_weight_kg','un_number','dg_class'],
'commercial_invoice':['invoice_number','shipment_date','shipper','consignee','port_of_loading','port_of_discharge','cargo_description','package_count','gross_cargo_weight_kg','hs_code','declared_invoice_value_usd'],
'packing_list':['document_reference','shipper','consignee','container_id','seal_number','cargo_description','package_count','package_type','gross_cargo_weight_kg','net_cargo_weight_kg'],
'dangerous_goods_declaration':['document_reference','shipper','consignee','carrier','seal_number','vessel','voyage','port_of_loading','port_of_discharge','container_id','un_number','proper_shipping_name','dg_class','package_count','package_type','gross_cargo_weight_kg']}
pretty={'document_reference':'Transport Document Reference','shipment_date':'Document Date','shipper':'Shipper / Consignor','consignee':'Consignee','carrier':'Carrier','vessel':'Vessel','voyage':'Voyage','port_of_loading':'Port of Loading','port_of_discharge':'Port of Discharge','container_id':'Container Number','seal_number':'Seal Number','cargo_description':'Cargo Description','package_count':'Number of Packages','package_type':'Package Type','gross_cargo_weight_kg':'Gross Cargo Mass (kg)','net_cargo_weight_kg':'Net Cargo Mass (kg)','un_number':'UN Number','dg_class':'Declared DG Class','proper_shipping_name':'Declared Proper Shipping Name','invoice_number':'Invoice Number','hs_code':'HS Code','declared_invoice_value_usd':'Invoice Value (USD)'}
titles={'bill_of_lading':'BILL OF LADING - DEMO','commercial_invoice':'COMMERCIAL INVOICE - DEMO','packing_list':'PACKING LIST - DEMO','dangerous_goods_declaration':'DANGEROUS GOODS DECLARATION - DEMO'}
styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='DocHead',parent=styles['Heading1'],fontSize=15,leading=18,alignment=TA_CENTER,textColor=colors.HexColor('#123550'),spaceAfter=12));styles.add(ParagraphStyle(name='TinyCustom',parent=styles['Normal'],fontSize=8,leading=11));
def dgd_pdf(path,data,case):
 from reportlab.pdfgen import canvas
 from reportlab.lib.pagesizes import A4
 from reportlab.lib.utils import simpleSplit
 c=canvas.Canvas(path,pagesize=A4)
 W,H=A4
 left,right=30,W-30
 def text(x,y,value,size=8,bold=False,maxwidth=None):
  c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
  lines=simpleSplit(str(value),'Helvetica-Bold' if bold else 'Helvetica',size,maxwidth or right-x-8)
  for line in lines[:4]:c.drawString(x,y,line);y-=size+3
 def cell(x,y,w,h,label,value='',sz=8):
  c.rect(x,y-h,w,h)
  text(x+4,y-11,label,6.3,True,w-8)
  if value!='':text(x+5,y-27,value,sz,False,w-10)
 c.setTitle('SYNTHETIC - Multimodal Dangerous Goods Form - '+case)
 c.setFont('Helvetica-Bold',13);c.drawCentredString(W/2,H-31,'MULTIMODAL DANGEROUS GOODS FORM')
 c.setFont('Helvetica-Bold',7);c.drawCentredString(W/2,H-43,'ACADEMIC SYNTHETIC - NOT VALID FOR SHIPPING / OFFICIAL SUBMISSION')
 y=H-55
 cell(left,y,275,65,'1. Shipper / Consignor / Sender',data['shipper'])
 cell(left+275,y,260,33,'2. Transport document number',data['document_reference'])
 cell(left+275,y-33,125,32,'3. Page 1 of', '1')
 cell(left+400,y-33,135,32,"4. Shipper reference",data['document_reference'])
 y-=65
 cell(left,y,275,67,'6. Consignee',data['consignee'])
 cell(left+275,y,260,67,'7. Carrier',data.get('carrier','Not listed on form'))
 y-=67
 cell(left,y,275,51,'8. Transport mode','SEA CARRIAGE - CONTAINERISED IMPORT')
 cell(left+275,y,260,51,"SHIPPER DECLARATION (SYNTHETIC)",'Not signed; test data only')
 y-=51
 cell(left,y,275,44,'10. Vessel / voyage',data['vessel']+' / '+data['voyage'])
 cell(left+275,y,260,44,'9. Additional handling information','Refer for qualified review')
 y-=44
 cell(left,y,267,43,'11. Port / place of loading',data['port_of_loading'])
 cell(left+267,y,268,43,'12. Port / place of discharge',data['port_of_discharge'])
 y-=43
 c.rect(left,y-174,535,174)
 text(left+5,y-12,'14. Shipping marks | Number and kind of packages; description of goods | Gross mass (kg)',6.7,True,520)
 text(left+7,y-38,f"{data['package_count']} {data['package_type']}",9,False,513)
 text(left+7,y-59,f"{data['un_number']}  {data['proper_shipping_name']}  CLASS {data['dg_class']}",10,True,513)
 text(left+7,y-83,f"Gross mass: {data['gross_cargo_weight_kg']:,} kg",9,False,513)
 text(left+7,y-104,'Synthetic training document - DG details must be independently verified',7,False,513)
 y-=174
 cell(left,y,173,57,'15. Container identification no.',data['container_id'])
 cell(left+173,y,124,57,'16. Seal number',data.get('seal_number','N/A'))
 cell(left+297,y,121,57,'17. Container size & type','Illustrative')
 cell(left+418,y,117,57,'19. Total gross mass',str(data['gross_cargo_weight_kg'])+' kg')
 y-=57
 cell(left,y,267,67,'CONTAINER / VEHICLE PACKING CERTIFICATE','NOT EXECUTED - DEMO ONLY')
 cell(left+267,y,268,67,'RECEIVING ORGANISATION RECEIPT','NOT EXECUTED - DEMO ONLY')
 y-=67
 cell(left,y,267,53,'20. Name of company / signature','FICTIONAL - UNSIGNED')
 cell(left+267,y,268,53,'22. Name of company / signature','FICTIONAL - UNSIGNED')
 y-=60
 text(left,y,'Case: '+case+'  |  Source: UNECE multimodal DG form layout reference (adapted).',7,False,530)
 text(left,y-13,'NOT a certification, MPA declaration, TradeNet permit or compliance determination.',7,True,530)
 c.save()
def pdf(path,kind,data,case):
 if kind=="dangerous_goods_declaration":
  return dgd_pdf(path,data,case)
 from reportlab.platypus import KeepTogether
 from reportlab.lib.enums import TA_LEFT,TA_RIGHT
 from reportlab.lib.pagesizes import A4
 from xml.sax.saxutils import escape
 doc=SimpleDocTemplate(path,pagesize=A4,leftMargin=16*mm,rightMargin=16*mm,topMargin=14*mm,bottomMargin=14*mm)
 C=colors.HexColor('#17334A'); MID=colors.HexColor('#48677D'); LIGHT=colors.HexColor('#E9F0F4'); PALE=colors.HexColor('#F7F9FB')
 styles2=getSampleStyleSheet()
 styles2.add(ParagraphStyle(name='HeaderMiniA',parent=styles2['Normal'],fontName='Helvetica-Bold',fontSize=8,leading=11,textColor=MID))
 styles2.add(ParagraphStyle(name='KeyMiniA',parent=styles2['Normal'],fontName='Helvetica-Bold',fontSize=7,leading=9,textColor=MID,spaceAfter=2))
 styles2.add(ParagraphStyle(name='ValMiniA',parent=styles2['Normal'],fontSize=9,leading=12,textColor=C))
 styles2.add(ParagraphStyle(name='DocTitleA',parent=styles2['Normal'],fontName='Helvetica-Bold',fontSize=18,leading=22,textColor=C,spaceAfter=4))
 styles2.add(ParagraphStyle(name='FootMiniA',parent=styles2['Normal'],fontSize=7,leading=9,textColor=MID))
 styles2.add(ParagraphStyle(name='SectionMiniA',parent=styles2['Normal'],fontName='Helvetica-Bold',fontSize=9,leading=12,textColor=C))
 P=lambda t,style='ValMiniA':Paragraph(escape(str(t)).replace('\n','<br/>'),styles2[style])
 def section(title):
  tab=Table([[P(title,'SectionMiniA')]],colWidths=[177*mm]);tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),8)]));return tab
 def field(k):
  if k not in data:return [P(pretty.get(k,k),'KeyMiniA'),P('—')]
  value=data[k]
  if k=='gross_cargo_weight_kg' or k=='net_cargo_weight_kg':value=f'{value:,.0f} kg'
  elif k=='declared_invoice_value_usd':value=f'USD {value:,.2f}'
  return [P(pretty.get(k,k),'KeyMiniA'),P(value)]
 def fieldgrid(keys,columns=2):
  r=[]
  for i in range(0,len(keys),columns):
   row=[]
   for k in keys[i:i+columns]:
    klabel,kvalue=field(k);row.append([klabel,kvalue])
   while len(row)<columns:row.append([P(''),P('')])
   r.append([Table([[a],[b]],colWidths=[(177/columns-4)*mm]) for a,b in row])
  t=Table(r,colWidths=[177*mm/columns]*columns,hAlign='LEFT');t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.HexColor('#D6E2EA')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),6)]));return t
 docid={'bill_of_lading':data.get('document_reference','BL-DEMO-001'),'commercial_invoice':data.get('invoice_number','INV-DEMO-001'),'packing_list':'PL-DEMO-001','dangerous_goods_declaration':'DGD-DEMO-001'}[kind]
 title={'bill_of_lading':'BILL OF LADING','commercial_invoice':'COMMERCIAL INVOICE','packing_list':'PACKING LIST','dangerous_goods_declaration':'MULTIMODAL DANGEROUS GOODS FORM'}[kind]
 content=[P('ACADEMIC SYNTHETIC TEST RECORD  |  NOT VALID FOR SHIPPING','HeaderMiniA'),Spacer(1,7),P(title,'DocTitleA'),P('REFERENCE: '+docid+'     |     DOCUMENT TYPE: '+kind.replace('_',' ').upper()+'     |     CASE: '+case,'HeaderMiniA'),Spacer(1,14)]
 if kind=='bill_of_lading':
  blocks=[('SHIPMENT PARTIES',['shipper','consignee','carrier']),('CARRIAGE',['vessel','voyage','port_of_loading','port_of_discharge','shipment_date']),('GOODS AND EQUIPMENT',['container_id','seal_number','cargo_description','package_count','gross_cargo_weight_kg','un_number','dg_class'])]
 elif kind=='commercial_invoice':
  blocks=[('COMMERCIAL PARTIES',['shipper','consignee','invoice_number','shipment_date']),('SHIPMENT DETAILS',['port_of_loading','port_of_discharge','cargo_description','package_count']),('COMMERCIAL INFORMATION',['gross_cargo_weight_kg','hs_code','declared_invoice_value_usd'])]
 elif kind=='packing_list':
  blocks=[('SHIPMENT REFERENCE',['document_reference','shipper','consignee']),('PACKAGING AND WEIGHT',['cargo_description','package_count','package_type','gross_cargo_weight_kg','net_cargo_weight_kg']),('CONTAINER MARKS',['container_id','seal_number'])]
 else:
  blocks=[('SHIPPER AND CONSIGNEE',['shipper','consignee','document_reference']),('TRANSPORT INFORMATION',['vessel','voyage','port_of_loading','port_of_discharge','container_id']),('DANGEROUS GOODS DETAILS',['un_number','proper_shipping_name','dg_class','package_count','package_type','gross_cargo_weight_kg'])]
 for title,keys in blocks:
  content.append(section(title));content.append(Spacer(1,4));content.append(fieldgrid(keys));content.append(Spacer(1,9))
 if kind=='dangerous_goods_declaration':
  content.append(P('Important: Declaration text, certification and packing suitability have NOT been verified for use in actual maritime transport. Not an official IMO/UNECE form.','FootMiniA'));content.append(Spacer(1,8))
 content.append(P('SYNTHETIC / FICTIONAL — Document deliberately generated for AI extraction and discrepancy testing. Not a permit, terminal approval, or regulatory clearance.','FootMiniA'))
 doc.build(content)
def changes_to_findings(changes):
 findings=[]
 for d,k,v in changes:
  typ='missing_document' if k=='missing' else ('weight_mismatch' if k=='gross_cargo_weight_kg' else 'container_mismatch' if k=='container_id' else 'dg_class_conflict')
  findings.append({'finding_type':typ,'affected_document':d,'affected_field':None if k=='missing' else k,'expected_action':'qualified_human_review' if typ=='dg_class_conflict' else 'verify_or_correct_documents','expected_value':None if k=='missing' else base[k],'injected_value':None if k=='missing' else v})
 return findings
manifest=[]
for case,changes in scenarios:
 folder=os.path.join(ROOT,'test_cases',case);os.makedirs(folder,exist_ok=True)
 documents={}; missing=[]
 for kind,fields in doc_fields.items():
  if any(d==kind and k=='missing' for d,k,v in changes):missing.append(kind);continue
  values={k:base[k] for k in fields}
  for d,k,v in changes:
   if d==kind and k!='missing':values[k]=v
  documents[kind]=values
  pdf(os.path.join(folder,kind+'.pdf'),kind,values,case)
 truth={'case_id':case,'shipment_truth':base,'document_truth':documents,'missing_documents':missing,'note':'document_truth contains exactly the values printed in the generated PDFs'}
 answer={'case_id':case,'expected_findings':changes_to_findings(changes),'expected_issue_count':len(changes),'regulatory_checks':[],'regulatory_note':'Regulatory verdicts are NOT labelled. MPA PSA DG arrival notification and Customs import permits are separate external processes; the four PDFs alone cannot demonstrate their completion. Member 2 must confirm any source-specific checks.'}
 for name,data in [('ground_truth.json',truth),('answer_key.json',answer)]:
  with open(os.path.join(folder,name),'w') as f:json.dump(data,f,indent=2)
 manifest.append({'case_id':case,'pdf_count':len(documents),'injected_issues':len(changes),'folder':'test_cases/'+case})
with open(os.path.join(ROOT,'dataset_manifest.csv'),'w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=manifest[0].keys());w.writeheader();w.writerows(manifest)
print('Generated',len(manifest),'test cases and',sum(x['pdf_count'] for x in manifest),'PDFs')
