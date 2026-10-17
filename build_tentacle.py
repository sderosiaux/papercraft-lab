"""Build the approved B concept as real, dimensioned paper components.

Units: centimetres. Body and mount planes are authored explicitly so the
accessories glue flush to planar body faces instead of intersecting its shell.
"""
import sys
import json
import math
from pathlib import Path
from itertools import combinations
import numpy as np
import papercraft.pipeline as pipeline
from papercraft.pipeline import bpy, bmesh, PaperModel, io, printprepper, exporters
from mathutils import Vector
from shapely.geometry import Polygon
from shapely.geometry import Point,box
from shapely.ops import unary_union,nearest_points
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output/tentacule-B-20cm'
RAW=OUT/'patrons-source'
RAW.mkdir(parents=True,exist_ok=True)
PROFILE=[(0,6.4), (5,5.8), (12,4.2), (17.5,2.8), (20,1.1)]
NORMAL=np.array([0.,-1.,.115]); NORMAL/=np.linalg.norm(NORMAL)
UP=np.array([0.,.115,1.]); UP/=np.linalg.norm(UP)
RIGHT=np.array([1.,0.,0.])
parts=[]
decorations=[]
report={ 'concept':'B - equilibre, user approved', 'units':'cm', 'target_height_mm':200,
         'engine':bpy.app.version_string, 'polyzamboni_version':'1.3.1',
         'physical_build_tested':False, 'folding_simulation':False, 'paper_thickness_simulated':False,
         'parts':{}, 'mounts':{}, 'decorations':[] }


def material(name,rgb):
    m=bpy.data.materials.new(name)
    m.diffuse_color=(*rgb,1)
    m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*rgb,1)
    bs.inputs['Roughness'].default_value=.9
    return m


def make_mesh(name,verts,faces,mat,closed=True):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(mat)
    bm=bmesh.new();bm.from_mesh(mesh)
    # Only triangulate genuinely warped quads, keeping simple foldable quads.
    warped=[]
    for f in bm.faces:
        p=np.array([v.co for v in f.verts],float)
        _,_,vh=np.linalg.svd(p-p.mean(0),full_matrices=True)
        if np.max(np.abs((p-p.mean(0))@vh[-1]))>1e-5:
            warped.append(f)
    if warped: bmesh.ops.triangulate(bm,faces=warped)
    if closed: bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    # PolyZamboni's print prep expects a UV layer, also for untextured material.
    mesh.uv_layers.new(name='PapercraftUV')
    obj['paper_component']=True
    obj['material_paper']=mat.name
    return obj


def radius_at(z):
    for (z0,r0),(z1,r1) in zip(PROFILE,PROFILE[1:]):
        if z0<=z<=z1:
            return r0+(r1-r0)*(z-z0)/(z1-z0),(r1-r0)/(z1-z0)
    raise ValueError(z)


def front(z): return np.array([0.,-4.3+.115*z,z])


def body(mat):
    shape=[(-.70,-1),(.70,-1),(1,-.45),(1,.45),(.70,1),(-.70,1),(-1,.45),(-1,-.45)]
    verts=[(a*rx,b*(4.3-.115*z),z) for z,rx in PROFILE for a,b in shape]
    faces=[]
    for j in range(len(PROFILE)-1):
        for k in range(8):
            faces.append((j*8+k,j*8+(k+1)%8,(j+1)*8+(k+1)%8,(j+1)*8+k))
    faces += [tuple(reversed(range(8))),tuple(range((len(PROFILE)-1)*8,len(PROFILE)*8))]
    obj=make_mesh('C_Corps',verts,faces,mat)
    obj['closure_face_id']=min(obj.data.polygons,key=lambda f:f.center.length).index
    return obj


def cup(code,z,r,depth,mat):
    n=8
    center=front(z)
    # Cross-section: back -> outer front -> inner front -> recessed floor.
    rings=[(r,0.),(r,depth),(.72*r,depth),(.64*r,.18)]
    verts=[center+RIGHT*(rad*math.cos(2*math.pi*(k+.5)/n))+
           UP*(rad*math.sin(2*math.pi*(k+.5)/n))+NORMAL*offset
           for rad,offset in rings for k in range(n)]
    faces=[]
    for j in range(3):
        for k in range(n): faces.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
    faces += [tuple(reversed(range(n))),tuple(range(3*n,4*n))]
    obj=make_mesh(code,verts,faces,mat)
    obj['closure_face_id']=min(obj.data.polygons,key=lambda f:(f.center-Vector(center)).length).index
    residual=max(abs(float(np.dot(v-center,NORMAL))) for v in verts[:n])
    assert residual<1e-10
    report['mounts'][code]={'back_plane_error_mm':residual*10,'height_from_base_mm':z*10,
                          'distance_along_front_mm':z*10*np.linalg.norm(np.array([0,.115,1])),
                          'outer_diameter_mm':2*r*10, 'depth_mm':depth*10}
    return obj


def arm(code,side,z,points,radii,mat):
    rx,slope=radius_at(z)
    mount=np.array([side*rx,0.,z])
    mount_normal=np.array([side,0.,-slope]); mount_normal/=np.linalg.norm(mount_normal)
    centers=[mount]+[np.array(p,float) for p in points]
    verts=[];n=6
    for i,(c,r) in enumerate(zip(centers,radii)):
        if i==0: tangent=mount_normal
        elif i==len(centers)-1: tangent=centers[i]-centers[i-1]
        else: tangent=centers[i+1]-centers[i-1]
        tangent=tangent/np.linalg.norm(tangent)
        u=np.array([0.,1.,0.]);v=np.cross(tangent,u)
        for k in range(n):
            a=2*math.pi*(k+.5)/n
            verts.append(c+r*(u*math.cos(a)+v*math.sin(a)))
    faces=[]
    for j in range(len(centers)-1):
        for k in range(n):faces.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
    faces += [tuple(reversed(range(n))),tuple(range((len(centers)-1)*n,len(centers)*n))]
    obj=make_mesh(code,verts,faces,mat)
    obj['closure_face_id']=min(obj.data.polygons,key=lambda f:(f.center-Vector(mount)).length).index
    residual=max(abs(float(np.dot(v-mount,mount_normal))) for v in verts[:n])
    assert residual<1e-10
    report['mounts'][code]={'back_plane_error_mm':residual*10,'height_from_base_mm':z*10,
                          'side':'right' if side>0 else 'left','mount_center_cm':mount.tolist()}
    return obj


def flat_piece(code,points,origin,u,v,mat):
    verts=[origin+x*u+y*v for x,y in points]
    obj=make_mesh(code,verts,[tuple(range(len(verts)))],mat,False)
    obj['flat_decoration']=True
    decorations.append((obj,points))
    report['decorations'].append({'name':code,'points_cm':points,'flat':True})
    return obj


def export_part(obj,code,paper,flap,max_faces):
    audit=pipeline.unwrap_and_audit(obj,max_faces,flap_height=flap,section_name=code,
                                    isolate_faces=[obj['closure_face_id']])
    face_sets=io.read_connected_component_sets(obj.data)
    closing_cid=next(cid for cid,fs in face_sets.items() if obj['closure_face_id'] in fs)
    audit['closure_piece']=code+'-'+str(io.read_build_step_numbers(obj.data)[closing_cid])
    # Keep usable page area below a header: 21 x 26.7 cm, on a true A4 page.
    cs=printprepper.create_print_data_for_all_components(obj,1.)
    external_labels=code!='C'
    pages=printprepper.fit_components_on_pages(cs,(21.,26.7),1.2,1.3 if external_labels else .45,False)
    from collections import Counter
    labels=Counter(e.edge_index for c in cs for e in c.cut_edges+c.fold_edges_at_flaps)
    assert all(n==2 for n in labels.values())
    assert len(labels)==audit['glue_flaps']
    max_overlap=0.;min_border=100
    for pg in pages:
        shapes=[]
        for c in pg:
            tri=[t.coords for t in c.colored_triangles]+[t for f in c.glue_flaps for t in f.tris]
            shape=unary_union([Polygon([c.page_transform*np.array(p) for p in t]) for t in tri])
            x0,y0,x1,y1=shape.bounds
            min_border=min(min_border,x0,y0,21-x1,26.7-y1)
            shapes.append(shape)
        max_overlap=max(max_overlap,max((a.intersection(b).area for a,b in combinations(shapes,2)),default=0.))
    assert min_border>=1.19,(obj.name,min_border)
    assert max_overlap<1e-6,(obj.name,max_overlap)
    small=code in ('BG','BD','V3')
    s=pipeline.settings((21.,29.7))._replace(line_width=.5,edge_number_font_size=5 if small else 6.5,
                                          edge_number_offset=.025 if small else .065,build_step_font_size=11,
                                          show_build_step_numbers=not external_labels,
                                          fold_hide_threshold_angle=math.radians(.1))
    if not external_labels:
        for fmt in ('pdf','svg'):exporters.MatplotlibBasedExporter(fmt,s).export(pages,str(RAW/code))
    else:
        exp=exporters.MatplotlibBasedExporter('pdf',s)
        with PdfPages(str(RAW/code)+'.pdf') as pdf:
            for pn,pg in enumerate(pages,1):
                fig,ax=exp._MatplotlibBasedExporter__create_page_figure(pg,False,True,False)
                shapes=[]
                for comp in pg:
                    tris=[t.coords for t in comp.colored_triangles]+[t for f in comp.glue_flaps for t in f.tris]
                    pts=[[comp.page_transform*np.array(v) for v in t] for t in tris]
                    shapes.append(unary_union([Polygon([(21-v[0],v[1]) for v in t]) for t in pts]))
                # On narrow faces even 5 pt edge numbers can meet. Move only
                # colliding numbers into free paper space, with an edge leader.
                fig.canvas.draw()
                renderer=fig.canvas.get_renderer()
                def text_box(t):
                    bb=t.get_window_extent(renderer).transformed(ax.transData.inverted())
                    return box(bb.x0-.018,bb.y0-.018,bb.x1+.018,bb.y1+.018)
                numeric_texts=list(ax.texts)
                for ti,t in enumerate(numeric_texts):
                    r=text_box(t)
                    if not any(r.intersects(text_box(o)) for oi,o in enumerate(numeric_texts) if oi!=ti):continue
                    pos=np.array(t.get_position())
                    angle=math.radians(t.get_rotation())
                    normal=np.array([-math.sin(angle),math.cos(angle)])
                    tangent=np.array([math.cos(angle),math.sin(angle)])
                    edge_point=pos-s.edge_number_offset*normal
                    t.set_rotation(0);t.set_horizontalalignment('center');t.set_verticalalignment('center');t.set_fontsize(6)
                    found=False
                    for dist in (.25,.4,.6,.85,1.1,1.5,2.):
                        for shift in (0,.3,-.3,.6,-.6):
                            candidate=edge_point-dist*normal+shift*tangent
                            t.set_position(candidate)
                            r=text_box(t)
                            x0,y0,x1,y1=r.bounds
                            if x0<.25 or y0<1.15 or x1>20.75 or y1>25.5:continue
                            if any(r.intersects(p.buffer(.04)) for p in shapes):continue
                            if any(r.intersects(text_box(o)) for oi,o in enumerate(numeric_texts) if oi!=ti):continue
                            ax.annotate('',xy=edge_point,xytext=candidate,
                                        arrowprops={'arrowstyle':'-','linewidth':.35,'color':'#777777',
                                                    'shrinkA':4,'shrinkB':1})
                            found=True;break
                        if found:break
                    assert found,('cannot place edge number',code,t.get_text())
                for i,t in enumerate(numeric_texts):
                    assert not any(text_box(t).intersects(text_box(o)) for o in numeric_texts[i+1:]),('overlapping labels',code)
                occupied=[]
                for comp,shape in zip(pg,shapes):
                    label=code+'-'+str(comp.build_step_number)
                    fp=FontProperties(family='DejaVu Sans',size=7,weight='bold')
                    width=TextPath((0,0),label,prop=fp).get_extents().width*2.54/72+.10
                    height=.30
                    x0,y0,x1,y1=shape.bounds
                    candidates=[]
                    for shift in (0,.5,-.5,1.,-1.,1.5,-1.5):
                        cy=(y0+y1)/2+shift
                        candidates.append((x0-.45-width,cy-height/2))
                    candidates += [((x0+x1-width)/2,y1+.35),((x0+x1-width)/2,y0-.65)]
                    for lx,ly in candidates:
                        rect=box(lx-.05,ly-.05,lx+width+.05,ly+height+.05)
                        if lx<.3 or ly<1.2 or lx+width>20.7 or ly+height>25.5:continue
                        if any(rect.intersects(p.buffer(.10)) for p in shapes+occupied):continue
                        if any(rect.intersects(text_box(t)) for t in numeric_texts):continue
                        occupied.append(rect)
                        origin=Point(lx+width/2,ly+height/2)
                        end=nearest_points(shape,origin)[0]
                        ax.annotate(label,xy=(end.x,end.y),xytext=(origin.x,origin.y),
                                    ha='center',va='center',fontproperties=fp,color='#202020',
                                    arrowprops={'arrowstyle':'-','linewidth':.45,'color':'#555555',
                                                'shrinkA':3,'shrinkB':1},zorder=10)
                        break
                    else:raise RuntimeError('No collision-free label position for '+label)
                pdf.savefig(fig)
                fig.savefig(str(RAW/code)+'_page'+str(pn)+'.svg')
                plt.close(fig)
    io.write_page_numbers(obj.data,{c.og_component_id:i for i,pg in enumerate(pages) for c in pg})
    io.write_page_transforms(obj.data,{c.og_component_id:c.page_transform for pg in pages for c in pg})
    audit.update(pages=len(pages),paper=paper,edge_pairs=len(labels),max_page_overlap_mm2=max_overlap*100,
                 nominal_flap_height_mm=flap*10,minimum_border_mm=min_border*10)
    report['parts'][code]=audit
    print('PART',code,'faces',audit['faces'],'pieces',audit['islands'],'pages',len(pages),flush=True)


def render_setup():
    scene=bpy.context.scene
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1000;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('Studio')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.8,.8,.8,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.4
    scene.view_settings.view_transform='AgX'
    ground=material('Studio - hors patron',(.86,.83,.76))
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.025))
    plane=bpy.context.object;plane.name='Studio_sol';plane.data.materials.append(ground)
    for name,pos,power,size in [('Key',(-20,-30,40),11000,22),('Fill',(28,-15,30),4500,18),('Rim',(0,20,30),7000,20)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        lamp=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(lamp);lamp.location=pos
        lamp.rotation_euler=(Vector((0,0,10))-lamp.location).to_track_quat('-Z','Y').to_euler()
    camdata=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camdata)
    bpy.context.collection.objects.link(cam);scene.camera=cam
    camdata.type='ORTHO';camdata.ortho_scale=27
    cam.location=(28,-60,28)
    cam.rotation_euler=(Vector((0,-.5,10))-cam.location).to_track_quat('-Z','Y').to_euler()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.shading.color_type='MATERIAL'
                area.spaces.active.region_3d.view_distance=32
                area.spaces.active.region_3d.view_location=(0,0,10)
                area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
                area.spaces.active.overlay.show_floor=False
    return cam,plane


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01;scene.unit_settings.length_unit='CENTIMETERS'
    purple=material('Violet',(.30,.025,.38))
    green=material('Vert vif',(.12,.55,.02))
    black=material('Noir',(.007,.007,.008))
    parts.append((body(purple),'C','VIOLET',.5,8))
    parts.append((arm('BG_Bras_bas',-1,11,[(-6.,0,10),(-6.8,0,9.2)],[.9,.8,.4],purple),'BG','VIOLET',.35,8))
    parts.append((arm('BD_Bras_leve',1,13,[(5.3,0,14.3),(5.5,0,16.9),(5.25,0,18.5)],[.85,.8,.65,.32],purple),'BD','VIOLET',.35,8))
    for code,z,r,depth in [('V1',4.7,3.15,.95),('V2',10.9,2.35,.80),('V3',16.1,1.62,.65)]:
        parts.append((cup(code,z,r,depth,green),code,'VERT VIF',.25 if code=='V3' else .3,8))
    brow=[(-1.72,1.0),(-1.47,1.48),(-.95,1.56),(-.32,1.30),(0,1.17),(.45,1.32),(1.2,1.62),(1.6,1.46),(1.7,1.16),(1.37,1.13),(.92,1.20),(.35,.91),(0,.82),(-.45,.96),(-1.03,1.17),(-1.38,1.12)]
    flat_piece('S_Sourcil',brow,front(16.1)+NORMAL*.655,RIGHT,UP,black)
    base=[(-4.25,.02),(4.25,.02),(4.15,.80),(-4.15,.80)]
    flat_piece('P_Bande_verte',base,front(0)+NORMAL*.01,RIGHT,UP,green)
    # The body is convex. Accessory vertices may touch but must not enter it.
    body_mesh=parts[0][0].data
    for obj,code,*_ in parts[1:]:
        signed_max=[]
        for v in obj.data.vertices:
            signed_max.append(max(float((v.co-face.center).dot(face.normal)) for face in body_mesh.polygons))
        assert min(signed_max)>-1e-5, (code,min(signed_max))
        report['mounts'][obj.name]['vertices_inside_body']=sum(d < -1e-5 for d in signed_max)
    # Two contact areas of the black paper eyebrow sit on the upper cup rim.
    ring=lambda r: Polygon([(r*math.cos(2*math.pi*(k+.5)/8),r*math.sin(2*math.pi*(k+.5)/8)) for k in range(8)])
    brow_contact=Polygon(brow).intersection(ring(1.62).difference(ring(1.62*.72)))
    report['eyebrow_glue_contact_mm2']=brow_contact.area*100
    assert brow_contact.area>.1
    for obj,code,paper,flap,max_faces in parts:
        export_part(obj,code,paper,flap,max_faces)
    bpy.context.view_layer.update()
    coordinates=np.array([v.co for obj,*_ in parts for v in obj.data.vertices])
    report['assembled_dimensions_mm']=(np.ptp(coordinates,axis=0)*10).tolist()
    assert abs(report['assembled_dimensions_mm'][2]-200)<.001
    report['total_shell_faces']=sum(p['faces'] for p in report['parts'].values())
    report['total_shell_pieces']=sum(p['islands'] for p in report['parts'].values())
    report['total_shell_pages']=sum(p['pages'] for p in report['parts'].values())
    # Export only physical components; no lights, floor or camera.
    bpy.ops.object.select_all(action='DESELECT')
    for obj,*_ in parts: obj.select_set(True)
    for obj,_ in decorations:obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0][0]
    bpy.ops.wm.obj_export(filepath=str(OUT/'tentacule-B-20cm.obj'),export_selected_objects=True)
    cam,plane=render_setup()
    bpy.ops.object.select_all(action='DESELECT');parts[0][0].select_set(True);bpy.context.view_layer.objects.active=parts[0][0]
    plane.hide_set(True)
    scene.render.filepath=str(OUT/'rendu-3d.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'tentacule-B-20cm.blend'))
    (OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    bpy.ops.render.render(write_still=True)
    cam.location=(0,-60,18)
    cam.rotation_euler=(Vector((0,0,10))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/'vue-face.png')
    bpy.ops.render.render(write_still=True)
    print(json.dumps(report,indent=2),flush=True)
    # The deliverable is a colour print on white paper, with its printed side out.
    import export_color
    export_color.export()


if __name__=='__main__':main()
