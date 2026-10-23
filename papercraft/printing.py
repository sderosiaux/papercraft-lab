"""Export saved nets with vector solid colours or UV textures on the outside.

Retains the exact component/page transforms stored in the Blender file.
Numbers are placed on tabs or in the waste paper, never on coloured faces.
"""
from pathlib import Path
import json
import math
import numpy as np
import papercraft.pipeline as pipeline
from papercraft.pipeline import bpy, io, printprepper, exporters
from shapely.geometry import Polygon, Point, box, LineString
from shapely.ops import unary_union, nearest_points
from matplotlib.patches import Polygon as Patch
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt



def srgb(rgb):
    return tuple(12.92*v if v <= .0031308 else 1.055*v**(1/2.4)-.055 for v in rgb[:3])


def export_colored_parts(blend_path, output_dir, report_path, parts, attachment_guides=()):
    """Export A4 nets from saved PolyZamboni layout; parts are (code, object name) pairs."""
    OUT = Path(output_dir)
    RAW = OUT/"patrons-source"
    RAW.mkdir(parents=True, exist_ok=True)
    (OUT/"qa").mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    report = json.loads(Path(report_path).read_text())
    qa = {'print_side':'outside', 'paper':'white', 'duplex':False, 'vector_colours':True,
          'uv_textures':False, 'hidden_attachment_marks':len(attachment_guides), 'parts':{}}
    for code, name in parts:
        obj = bpy.data.objects[name]
        components = printprepper.create_print_data_for_all_components(obj, 1.)
        page_numbers = io.read_page_numbers(obj.data)
        transforms = io.read_page_transforms(obj.data)
        pages = [[] for _ in range(report['parts'][code]['pages'])]
        for comp in components:
            comp.set_new_page_transform(transforms[comp.og_component_id])
            pages[page_numbers[comp.og_component_id]].append(comp)
        settings = pipeline.settings((21.,29.7))._replace(
            prints_on_model_inside=False, show_edge_numbers=False,
            show_build_step_numbers=False, line_width=.35,
            fold_hide_threshold_angle=math.radians(.1),texture_quality='super')
        exp = exporters.MatplotlibBasedExporter('pdf', settings)
        label_count = 0
        face_area = 0.
        with PdfPages(RAW/f'{code}.pdf') as pdf:
            for pn, page in enumerate(pages, 1):
                textured=any(t.absolute_texture_path for c in page for t in c.colored_triangles)
                if textured:
                    qa['uv_textures']=True;qa['vector_colours']=False
                fig, ax = exp._MatplotlibBasedExporter__create_page_figure(page,textured,True,False)
                faces, shapes, edge_items = [], [], []
                for comp in page:
                    pts = lambda coords: [comp.page_transform*np.array(v) for v in coords]
                    face = unary_union([Polygon(pts(t.coords)) for t in comp.colored_triangles])
                    shape = unary_union([face]+[Polygon(pts(tri)) for f in comp.glue_flaps for tri in f.tris])
                    faces.append(face); shapes.append(shape)
                    face_area += face.area
                    if not textured:
                        colour = srgb(comp.colored_triangles[0].color)
                        assert all(np.allclose(t.color,comp.colored_triangles[0].color) for t in comp.colored_triangles)
                        for poly in ([face] if face.geom_type=='Polygon' else face.geoms):
                            assert sum(Polygon(ring).area for ring in poly.interiors)<1e-6
                            ax.add_patch(Patch(np.array(poly.exterior.coords),facecolor=colour,edgecolor='none',zorder=-1))
                    for e in comp.cut_edges+comp.fold_edges_at_flaps:
                        a,b=map(np.array,pts(e.coords))
                        edge_items.append((len(faces)-1,e.edge_index,a,b))
                fig.canvas.draw()
                renderer=fig.canvas.get_renderer()
                occupied=[]
                face_surface=unary_union(faces)
                face_union=face_surface.buffer(.015)

                def rectangle(t):
                    b=t.get_window_extent(renderer).transformed(ax.transData.inverted())
                    return box(b.x0-.018,b.y0-.018,b.x1+.018,b.y1+.018)

                def available(r, owner):
                    x0,y0,x1,y1=r.bounds
                    return (x0>.5 and y0>.85 and x1<20.5 and y1<25.0
                        and not r.intersects(face_union)
                        and not any(r.intersects(s.buffer(.02)) for i,s in enumerate(shapes) if i!=owner)
                        and not any(r.intersects(o) for o in occupied))

                # Reserve component IDs before placing the more numerous edge IDs.
                for i,(comp,shape) in enumerate(zip(page,shapes)):
                    x0,y0,x1,y1=shape.bounds
                    t=ax.text(0,0,code+'-'+str(comp.build_step_number),fontsize=7,fontweight='bold',ha='center',va='center',zorder=10)
                    candidates=[]
                    for d in (.35,.55,.8,1.1,1.5,2.):
                        for shift in (0,.5,-.5,1.,-1.):
                            candidates += [(x1+d,(y0+y1)/2+shift),(x0-d,(y0+y1)/2+shift),((x0+x1)/2+shift,y1+d),((x0+x1)/2+shift,y0-d)]
                    for p in candidates:
                        t.set_position(p);r=rectangle(t)
                        if not available(r,i) or r.intersects(shape.buffer(.08)):continue
                        end=nearest_points(shape,Point(p))[0]
                        line=LineString([p,(end.x,end.y)])
                        if line.intersection(face_surface).length>.002:continue
                        occupied.append(r)
                        ax.annotate('',xy=(end.x,end.y),xytext=p,arrowprops={'arrowstyle':'-','linewidth':.35,'color':'#555555','shrinkA':8,'shrinkB':1})
                        break
                    else:raise RuntimeError(('component label placement',code,pn,t.get_text()))

                for i,edge_id,a,b in edge_items:
                    mid=(a+b)/2;tangent=(b-a)/np.linalg.norm(b-a)
                    normal=np.array([-tangent[1],tangent[0]])
                    # Positive normal is the face side in the exterior unfolding.
                    if not faces[i].buffer(.001).covers(Point(mid+normal*.01)):normal=-normal
                    label=str(edge_id)+('.' if edge_id in (6,9) else '')
                    t=ax.text(0,0,label,fontsize=5.5,ha='center',va='center',zorder=10)
                    found=False
                    for dist in (.10,.16,.23,.32,.45,.60,.85,1.1,1.5,2.,2.8,4.):
                        for shift in (0,.16,-.16,.32,-.32,.55,-.55,.85,-.85,1.2,-1.2,1.8,-1.8,2.5,-2.5,3.5,-3.5):
                            p=mid-normal*dist+tangent*shift
                            t.set_position(p);r=rectangle(t)
                            if not available(r,i):continue
                            line=LineString([mid,p])
                            if line.intersection(face_surface).length>.002:continue
                            if any(line.intersects(o.buffer(-.025)) for o in occupied):continue
                            occupied.append(r)
                            if dist>.24 or abs(shift)>.17:
                                ax.annotate('',xy=mid,xytext=p,arrowprops={'arrowstyle':'-','linewidth':.25,'color':'#777777','shrinkA':3,'shrinkB':.5})
                            found=True;break
                        if found:break
                    if not found:
                        fig.savefig(OUT/'qa'/'color-placement-debug.png',dpi=100)
                        print('PLACEMENT DEBUG',code,edge_id,a,b,mid,normal,faces[i].bounds,flush=True)
                    assert found,('edge label placement',code,pn,edge_id)
                    label_count+=1
                assert len(occupied)==len(page)+len(edge_items)
                for i,r in enumerate(occupied):
                    assert not r.intersects(face_union)
                    assert not any(r.intersects(s) for s in occupied[i+1:])
                # Optional positioning marks are covered by the attached accessory.
                for guide in attachment_guides:
                    if guide['part']!=code:continue
                    groups=io.read_connected_component_sets(obj.data)
                    fid=guide['face_id']
                    cid=next(k for k,fs in groups.items() if fid in fs)
                    comp=next((c for c in page if c.og_component_id==cid),None)
                    if comp is None:continue
                    from mathutils import Vector
                    local=io.read_local_coordinate_systems_per_face(obj.data)
                    affine=io.read_affine_transforms_to_roots(obj.data)
                    points=[comp.page_transform*printprepper.unfolding.get_globally_consistent_2d_coord_in_face(
                        obj.data,Vector(p),fid,cid,local,affine) for p in guide['polygon_cm']]
                    ax.add_patch(Patch(points,fill=False,edgecolor='#666666',linewidth=.35,linestyle=':',zorder=8))
                    center=np.mean(points,axis=0)
                    ax.text(*center,guide['label'],fontsize=5,ha='center',va='center',color='#444444',zorder=9,
                            bbox={'facecolor':'white','alpha':.7,'edgecolor':'none','pad':.3})
                pdf.savefig(fig)
                fig.savefig(RAW/f'{code}_page{pn}.svg')
                plt.close(fig)
        assert label_count==report['parts'][code]['edge_pairs']*2
        qa['parts'][code]={'pages':len(pages),'edge_labels':label_count,'coloured_face_area_cm2':face_area,'labels_on_coloured_faces':0}
        print(code,qa['parts'][code],flush=True)
    (OUT/'validation-couleur.json').write_text(json.dumps(qa,indent=2))
