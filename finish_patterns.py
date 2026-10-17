"""Add a French legend and physical scale check without resizing the real nets."""
from pathlib import Path
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from pypdf import PdfReader, PdfWriter

root=Path(__file__).resolve().parent
for filename,title,subtitle in [
    ('galet-facette-A4.pdf','GALET FACETTÉ','Prototype technique | 80 mm de haut | 20 faces | 3 pièces'),
    ('cube-controle-A4.pdf','CUBE DE CONTRÔLE','Prototype technique | arête de 30 mm | 6 faces | 1 pièce')
]:
    path=root/'output/pdf'/filename
    source=PdfReader(path)
    assert len(source.pages)==1
    page=source.pages[0]
    assert abs(float(page.mediabox.width)/mm-210)<.001
    assert abs(float(page.mediabox.height)/mm-297)<.001
    buf=BytesIO()
    c=canvas.Canvas(buf,pagesize=(210*mm,297*mm))
    c.setFillColorRGB(.09,.22,.21)
    c.setFont('Helvetica-Bold',18)
    c.drawString(15*mm,280*mm,title)
    c.setFont('Helvetica',9)
    c.drawString(15*mm,272*mm,subtitle)
    c.setStrokeColorRGB(.65,.72,.7)
    c.line(15*mm,266*mm,195*mm,266*mm)
    c.setFillColorRGB(.1,.1,.1)
    for y,text in [
        (259,'1. Imprimer en taille réelle / 100 %, sans ajustement à la page.'),
        (252,'2. Découper les traits continus. Marquer et plier les pointillés.'),
        (245,"3. Garder les chiffres à l'intérieur. Coller les languettes aux repères identiques."),
        (238,'4. Former les pièces, puis les réunir. Garder la fermeture finale accessible.')
    ]:
        c.drawString(15*mm,y*mm,text)
    c.setLineWidth(.7)
    c.setStrokeColorRGB(.1,.1,.1)
    c.line(15*mm,228*mm,65*mm,228*mm)
    c.line(15*mm,226.5*mm,15*mm,229.5*mm)
    c.line(65*mm,226.5*mm,65*mm,229.5*mm)
    c.setFont('Helvetica',8)
    c.drawString(70*mm,227*mm,"Ce segment doit mesurer exactement 50 mm.")
    c.setFillColorRGB(.38,.38,.38)
    c.setFont('Helvetica',7)
    c.drawString(15*mm,7*mm,'Blender + PolyZamboni | Géométrie vérifiée numériquement ; montage physique à tester.')
    c.save()
    page.merge_page(PdfReader(buf).pages[0])
    writer=PdfWriter()
    writer.add_page(page)
    writer.add_metadata({'/Title':title,'/Author':'Papercraft lab - Blender + PolyZamboni'})
    with path.open('wb') as f:
        writer.write(f)
    reread=PdfReader(path)
    assert '50 mm' in reread.pages[0].extract_text()
    print('Verified A4 with 50 mm calibration:',path)
