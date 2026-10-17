"""Package the audited nets without changing their physical scale."""
from pathlib import Path
from io import BytesIO
import math,json,zipfile
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader,PdfWriter

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output/tentacule-B-20cm'
data=json.loads((OUT/'validation.json').read_text())
W,H=210*mm,297*mm
purple=(.36,.08,.43); ink=(.12,.14,.15); gray=(.40,.43,.45)

def heading(c,title,sub):
    c.setFillColorRGB(*purple);c.setFont('Helvetica-Bold',20);c.drawString(16*mm,280*mm,title)
    c.setFillColorRGB(*gray);c.setFont('Helvetica',9);c.drawString(16*mm,272*mm,sub)
    c.setStrokeColorRGB(.8,.78,.82);c.line(16*mm,266*mm,194*mm,266*mm)

def text(c,x,y,line,size=10,bold=False,color=ink):
    c.setFillColorRGB(*color);c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
    c.drawString(x*mm,y*mm,line)

def scale(c,y=15):
    c.setStrokeColorRGB(*ink);c.setLineWidth(.6)
    c.line(16*mm,y*mm,66*mm,y*mm)
    for x in (16,66):c.line(x*mm,(y-1.5)*mm,x*mm,(y+1.5)*mm)
    text(c,71,y-.8,'50 mm - imprimer à 100 %, sans ajustement',8)

def footer(c,n):
    text(c,16,7,'Tentacule pourpre B | Prototype numérique - montage physique à tester',7,color=gray)
    text(c,188,7,str(n),7,color=gray)

def polygon(c,pts,ox,oy,fill=0,stroke=1):
    p=c.beginPath();p.moveTo((ox+pts[0][0]*10)*mm,(oy+pts[0][1]*10)*mm)
    for x,y in pts[1:]:p.lineTo((ox+x*10)*mm,(oy+y*10)*mm)
    p.close();c.drawPath(p,stroke=stroke,fill=fill)

buf=BytesIO();c=canvas.Canvas(buf,pagesize=(W,H))
heading(c,'LE TENTACULE POURPRE','Concept B validé | Papercraft de 20 cm | Blender + PolyZamboni')
c.drawImage(str(OUT/'rendu-3d.png'),38*mm,91*mm,width=134*mm,height=147.4*mm,preserveAspectRatio=True)
text(c,16,252,'UN VRAI MODÈLE 3D, UN PATRON À L\'ÉCHELLE',10,True)
text(c,16,78,f"{data['total_shell_faces']} faces planes - {data['total_shell_pieces']} pièces de structure + 2 décors plats",11,True)
d=data['assembled_dimensions_mm']
text(c,16,69,f"Encombrement : {d[0]:.0f} x {d[1]:.0f} x {d[2]:.0f} mm (largeur x profondeur x hauteur).",10)
text(c,16,57,'Impression COULEUR sur papier BLANC, recto simple : 10 feuilles de pièces.',10)
text(c,16,49,'Papier conseillé pour cet essai : 160 à 180 g/m², colle papier, règle et plioir.',9)
text(c,16,39,'Les pages 4 à 12 sont les patrons. Les deux décors colorés sont page 13.',9)
text(c,16,31,'Faire un premier essai sur papier ordinaire avant le montage définitif.',9)
scale(c,19);footer(c,1);c.showPage()

heading(c,'ASSEMBLAGE','Couleurs côté extérieur, verso blanc à l\'intérieur. Impression en recto simple.')
steps=[
('01  Préparer les pièces',[
 'Imprimer à 100 % et mesurer le segment de 50 mm. Découper les traits continus.',
 'Avant découpe, recopier au verso les identifiants et les numéros situés hors des pièces.',
 'Vu du côté coloré : pointillés = pli montagne ; tiret-point = pli vallée.',
 'Les traits fins gris reliant un chiffre à une arête sont des repères, pas des découpes.']),
('02  Construire les ventouses V1, V2, V3',[
 'Assembler séparément chaque ventouse, en reliant uniquement ses numéros identiques.',
 'Former le fond creux, les parois intérieures, le rebord et la paroi extérieure.',
 'Fermer le dos plat en dernier : '+', '.join(data['parts'][k]['closure_piece'] for k in ['V1','V2','V3'])+'.']),
('03  Construire les bras BG et BD',[
 'BG est le bras bas, à gauche sur la vue de face. BD est le bras levé, à droite.',
 'Assembler leurs facettes puis fermer les bases plates : '+data['parts']['BG']['closure_piece']+' et '+data['parts']['BD']['closure_piece']+'.',
 'Les bases plates servent de surfaces de collage contre les côtés du corps.']),
('04  Monter le corps C en gardant le dessous ouvert',[
 'Relier les pièces du corps. Garder la pièce '+data['parts']['C']['closure_piece']+' de côté : elle ferme le dessous.',
 'L\'ouverture permet de soutenir la face avant et les côtés pendant le collage.',
 'Les chiffres sur les languettes ou dans les marges repèrent les raccords à coller.']),
('05  Fixer les accessoires',[
 'Utiliser le gabarit page 3 pour centrer les trois ventouses sur la face avant plane.',
 'Coller BG au milieu de la face latérale gauche, centre à 110 mm au-dessus de la base.',
 'Coller BD de la même façon à droite, centre à 130 mm. Soutenir le carton par l\'intérieur.']),
('06  Poser les décors et fermer',[
 'Découper les décors colorés de la page 13. Coller S sur le rebord supérieur',
 'de la petite ventouse, puis P au bas de la face avant. Fermer le dessous en dernier.',
 'Un montage physique reste nécessaire pour vérifier la prise en main et l\'épaisseur.'])]
y=252
for title,lines in steps:
    text(c,16,y,title,11,True,color=purple);y-=7
    for line in lines:text(c,16,y,line,9);y-=5.2
    y-=8
footer(c,2);c.showPage()

heading(c,'PLACEMENT DES VENTOUSES','Gabarit à taille réelle de la face avant plane - papier ordinaire - ne pas coller au modèle')
text(c,16,257,'Aligner le bas du gabarit avec le bas du corps. Les octogones indiquent les dos à coller.',8)
profile=[(0,6.4),(5,5.8),(12,4.2),(17.5,2.8),(20,1.1)]
s=math.sqrt(1+.115**2)
outline=[(-.70*r,z*s) for z,r in profile]+[(.70*r,z*s) for z,r in reversed(profile)]
c.setStrokeColorRGB(*ink);c.setLineWidth(.7)
polygon(c,outline,105,37)
c.setDash(2,3);c.line(105*mm,37*mm,105*mm,(37+200*s)*mm);c.setDash()
for k in ('V1','V2','V3'):
    m=data['mounts'][k];rad=m['outer_diameter_mm']/20
    cy=37+m['distance_along_front_mm']
    pts=[(rad*math.cos(2*math.pi*(j+.5)/8),rad*math.sin(2*math.pi*(j+.5)/8)) for j in range(8)]
    c.setStrokeColorRGB(.23,.5,.1);polygon(c,pts,105,cy)
    c.line(102*mm,cy*mm,108*mm,cy*mm);c.line(105*mm,(cy-3)*mm,105*mm,(cy+3)*mm)
    text(c,110,cy+1,k,11,True)
    text(c,158,cy,f"{m['distance_along_front_mm']:.1f} mm",8)
text(c,16,27,'Mesures à droite : distance le long de la face avant, depuis son bord inférieur.',8)
scale(c,17);footer(c,3);c.save()
front_matter=PdfReader(buf)
writer=PdfWriter()
for page in front_matter.pages:writer.add_page(page)

titles={'C':'CORPS','BG':'BRAS BAS','BD':'BRAS LEVÉ','V1':'GRANDE VENTOUSE','V2':'VENTOUSE MOYENNE','V3':'PETITE VENTOUSE'}
page_n=4
for code in ('C','BG','BD','V1','V2','V3'):
    source=PdfReader(OUT/'patrons-source'/f'{code}.pdf')
    assert len(source.pages)==data['parts'][code]['pages']
    for local_n,page in enumerate(source.pages,1):
        assert abs(float(page.mediabox.width)/mm-210)<.001
        assert abs(float(page.mediabox.height)/mm-297)<.001
        overlay=BytesIO();o=canvas.Canvas(overlay,pagesize=(W,H))
        heading(o,f'{code} - {titles[code]}',f"Couleur sur papier BLANC | Feuille {local_n}/{len(source.pages)} | Face colorée à l'extérieur")
        text(o,16,259,'100 % / taille réelle. Associer les repères identiques uniquement dans ce groupe.',8)
        footer(o,page_n)
        # Keep the scale above the nets; exterior edge labels use the bottom margin.
        o.setStrokeColorRGB(*ink);o.setLineWidth(.5)
        o.line(16*mm,253*mm,66*mm,253*mm)
        text(o,70,252.3,'50 mm',6)
        o.save();page.merge_page(PdfReader(overlay).pages[0]);writer.add_page(page)
        page_n+=1

flatbuf=BytesIO();f=canvas.Canvas(flatbuf,pagesize=(W,H))
heading(f,'S + P - DÉCORS PLATS','Imprimer en couleur sur papier blanc - découper directement les formes colorées')
text(f,16,252,'S - SOURCIL NOIR',11,True)
text(f,16,244,'Découper une seule pièce noire. Aucun pli. Coller sur le haut du rebord de V3.',9)
f.setStrokeColorRGB(0,0,0);f.setFillColorRGB(0,0,0);f.setLineWidth(.6)
polygon(f,data['decorations'][0]['points_cm'],70,207,fill=1)
text(f,16,178,'P - BANDE VERTE',11,True)
text(f,16,170,'Découper la bande verte. Coller au bas de la face avant, bien centré.',9)
f.setFillColorRGB(.38109186,.76737566,.15170372)
polygon(f,data['decorations'][1]['points_cm'],105,141,fill=1)
text(f,16,112,'Les deux formes sont déjà à l\'échelle. Ne pas les agrandir.',10,True)
text(f,16,102,'Le sourcil tient sur les deux zones du rebord supérieur ; son centre reste libre.',9)
scale(f,25);footer(f,page_n);f.save();writer.add_page(PdfReader(flatbuf).pages[0])
writer.add_metadata({'/Title':'Tentacule pourpre B - 20 cm - patron A4 COULEUR','/Author':'Papercraft lab - Blender + PolyZamboni'})
target=OUT/'tentacule-B-20cm-papercraft-A4.pdf'
with target.open('wb') as fh:writer.write(fh)
check=PdfReader(target)
assert len(check.pages)==13
for pg in check.pages:
    assert abs(float(pg.mediabox.width)/mm-210)<.001 and abs(float(pg.mediabox.height)/mm-297)<.001
assert '50 mm' in check.pages[0].extract_text()
assert 'SOURCIL NOIR' in check.pages[-1].extract_text()
(OUT/'LIRE-MOI.txt').write_text('''TENTACULE POURPRE - CONCEPT B - 20 CM

Le PDF comporte 13 pages : 3 de notice/gabarit, 9 de patrons, 1 de décors plats.
Imprimer à 100 %, sans adapter à la page. Mesurer les repères de 50 mm.
Imprimer EN COULEUR sur papier BLANC, en RECTO SIMPLE.
Pages 4-9 : pièces violettes. Pages 10-12 : pièces vertes.
Page 13 : décors noir (sourcil) et vert (bande), à découper directement.
La face colorée se place à l'extérieur, le verso blanc à l'intérieur.
Vu du côté coloré : pointillés = pli montagne ; tiret-point = pli vallée.
Les identifiants sont dans les marges, les raccords dans les marges/languettes.
Recopier au verso les repères situés hors des pièces AVANT de découper.
Les traits gris reliant des chiffres aux arêtes sont des repères, pas des coupes.

Le fichier .blend contient le véritable maillage et les données de dépliage
PolyZamboni. Les images rendu-3d.png et vue-face.png proviennent de ce maillage.
L'OBJ conserve des coordonnées en centimètres (format sans unité intégrée).

Vérifications : surfaces fermées orientées, faces planes, longueurs 3D/2D,
couverture des faces, paires de repères, chevauchements 2D, marges A4,
plans de fixation, hauteur assemblée de 200 mm. Détails : validation.json.
Tolérance d'intersection numérique : 0,0001 mm² par paire de polygones.
Pas de test de montage physique, de simulation de pliage, ni d'épaisseur papier.

Il s'agit d'un prototype à construire pour valider l'ergonomie réelle du montage.
Pour rouvrir le dépliage dans Blender : sélectionner une pièce, touche N,
panneau PolyZamboni. Ne pas modifier le maillage sans recalculer le patron.

Sources outils :
https://extensions.blender.org/add-ons/polyzamboni/
https://github.com/AntonFlorey/PolyZamboni
https://extensions.blender.org/add-ons/export-paper-model/
Le MCP est optionnel pour ce workflow, réalisé avec l'API Python de Blender.
https://github.com/ahujasid/mcp-for-blender
''',encoding='utf-8')
deliverables=[target,OUT/'tentacule-B-20cm.blend',OUT/'tentacule-B-20cm.obj',OUT/'tentacule-B-20cm.mtl',
              OUT/'rendu-3d.png',OUT/'vue-face.png',OUT/'validation.json',OUT/'validation-couleur.json',OUT/'LIRE-MOI.txt']
with zipfile.ZipFile(OUT/'tentacule-B-20cm-kit.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in deliverables:z.write(p,p.name)
    for p in sorted((OUT/'patrons-source').glob('*.svg')):z.write(p,'svg/'+p.name)
print('Verified',len(check.pages),'A4 pages:',target)
