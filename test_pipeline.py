"""Integration checks: a cube, a faceted pebble, and invalid-mesh controls."""
from pathlib import Path
import json
import subprocess
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from papercraft.pipeline import bpy, PolyZamboni, mesh_audit, unwrap_and_audit, export_and_audit

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'output'
OUT.mkdir(exist_ok=True)


def preview(obj, target):
    verts = np.array([v.co for v in obj.data.vertices])
    faces = [[verts[i] for i in p.vertices] for p in obj.data.polygons]
    fig = plt.figure(figsize=(8,8), facecolor='#faf8f3')
    ax = fig.add_subplot(111, projection='3d', facecolor='#faf8f3')
    palette=['#568a88','#80aaa1','#acc6b8','#d2dac5','#39706e']
    ax.add_collection3d(Poly3DCollection(faces,facecolors=[palette[i%5] for i in range(len(faces))],edgecolors='#203b3b',linewidths=.7,shade=True))
    radius=max(np.ptp(verts,axis=0))*.6
    center=verts.mean(axis=0)
    ax.set(xlim=(center[0]-radius,center[0]+radius),ylim=(center[1]-radius,center[1]+radius),zlim=(center[2]-radius,center[2]+radius))
    ax.set_box_aspect((1,1,1))
    ax.view_init(elev=16,azim=-55)
    ax.set_axis_off()
    fig.text(.08,.92,'DU VOLUME AU PAPIER',size=21,weight='bold',color='#203b3b')
    fig.text(.08,.875,'Prototype géométrique · 20 faces · hauteur 80 mm',size=12,color='#4d6363')
    fig.text(.08,.06,'Même maillage dans le fichier Blender et le patron PDF.',size=11,color='#4d6363')
    fig.savefig(target,dpi=150)
    plt.close(fig)


def negative_controls():
    mesh = bpy.data.meshes.new('NonManifoldControl')
    mesh.from_pydata([(0,0,0),(2,0,0),(0,2,0),(0,-2,0),(0,0,2)],[],[(0,1,2),(1,0,3),(0,1,4)])
    obj=bpy.data.objects.new('NonManifoldControl',mesh)
    result=mesh_audit(obj)
    assert result['errors']
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(mesh)
    mesh=bpy.data.meshes.new('WarpedQuadControl')
    mesh.from_pydata([(0,0,0),(2,0,0),(2,2,.5),(0,2,0)],[],[(0,1,2,3)])
    obj=bpy.data.objects.new('WarpedQuadControl',mesh)
    result2=mesh_audit(obj)
    assert 'non-planar face' in result2['errors']
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(mesh)
    return dict(nonmanifold_rejected=True, warped_quad_rejected=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.context.scene.unit_settings.scale_length=.01
    bpy.context.scene.unit_settings.length_unit='CENTIMETERS'
    results=dict(blender=bpy.app.version_string,polyzamboni=PolyZamboni.bl_info['version'],
                 polyzamboni_commit=subprocess.check_output(['git','-C',str(ROOT/'vendor/PolyZamboni'),'rev-parse','HEAD'],text=True).strip(),
                 negative_controls=negative_controls(),physical_assembly_tested=False,
                 limitations=['No cardstock thickness simulation','No dynamic folding/collision simulation','No physical build test','No AI-generated source mesh tested'])
    bpy.ops.mesh.primitive_cube_add(size=3)
    cube=bpy.context.object
    cube.name='Cube_control_30mm'
    results['cube']=unwrap_and_audit(cube,6)
    export_and_audit(cube,'cube-controle-A4',results['cube'])
    bpy.data.objects.remove(cube,do_unlink=True)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1)
    gem=bpy.context.object
    gem.name='Galet_facette_80mm'
    zs=[v.co.z for v in gem.data.vertices]
    for v in gem.data.vertices:
        v.co *= 8/(max(zs)-min(zs))
        v.co.x *= .8
        v.co.y *= .8
    gem.data.update()
    bpy.context.view_layer.update()
    results['faceted_model']=unwrap_and_audit(gem,10)
    results['faceted_model']['dimensions_mm']=[round(float(d)*10,4) for d in gem.dimensions]
    export_and_audit(gem,'galet-facette-A4',results['faceted_model'])
    mat=bpy.data.materials.new('Sauge')
    mat.diffuse_color=(.19,.43,.39,1.)
    gem.data.materials.append(mat)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'galet-facette.blend'))
    bpy.ops.wm.obj_export(filepath=str(OUT/'galet-facette.obj'),export_selected_objects=True)
    preview(gem,OUT/'apercu-3d.png')
    (OUT/'validation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
