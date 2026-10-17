"""Blender + PolyZamboni unfolding with independent geometry checks.

Coordinates are centimetres. Blender preferences stay inside this checkout.
Importing this module initializes bpy and the PolyZamboni GPU shaders.
"""
from pathlib import Path
from itertools import combinations
from collections import Counter
import json
import math
import sys
import subprocess
import os

ROOT = Path(__file__).resolve().parent.parent
# Keep bpy's headless extension lifecycle separate from the interactive app.
os.environ['BLENDER_USER_CONFIG'] = str(ROOT/'.blender-test-config')
os.environ['BLENDER_USER_EXTENSIONS'] = str(ROOT/'.blender-test-extensions')
sys.path.insert(0, str(ROOT / 'vendor'))

import bpy
import bmesh
import gpu
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely.ops import unary_union

gpu.init()  # Required by PolyZamboni's viewport shaders, even for PDF export.
import PolyZamboni
from PolyZamboni.polyzamboni import autozamboni, printprepper, exporters, io
from PolyZamboni.polyzamboni.papermodel import PaperModel
PolyZamboni.register()


def mesh_audit(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    errors = []
    if not all(e.is_manifold and e.is_contiguous for e in bm.edges):
        errors.append('open/non-manifold edge or inconsistent normals')
    if not all(v.is_manifold for v in bm.verts):
        errors.append('non-manifold vertex')
    max_nonplanarity = 0.
    for face in bm.faces:
        pts = np.array([v.co for v in face.verts], dtype=float)
        _, _, basis = np.linalg.svd(pts - pts.mean(axis=0), full_matrices=True)
        max_nonplanarity = max(max_nonplanarity, float(np.max(np.abs((pts-pts.mean(axis=0)) @ basis[-1]))))
        if face.calc_area() < 1e-8:
            errors.append('degenerate face')
    if max_nonplanarity > 1e-5:
        errors.append('non-planar face')
    data = dict(vertices=len(bm.verts), edges=len(bm.edges), faces=len(bm.faces),
                euler_characteristic=len(bm.verts)-len(bm.edges)+len(bm.faces),
                closed_manifold=all(e.is_manifold for e in bm.edges),
                positive_volume_cm3=float(bm.calc_volume(signed=True)),
                max_nonplanarity_mm=max_nonplanarity*10, errors=errors)
    bm.free()
    return data


def unwrap_and_audit(obj, max_faces, flap_height=.5, section_name=None, isolate_faces=()):
    bpy.context.view_layer.objects.active = obj
    props = obj.data.polyzamboni_general_mesh_props
    props.glue_flap_height = flap_height
    props.glue_flap_angle = math.radians(45)
    initial = mesh_audit(obj)
    assert not initial['errors'], initial
    with PaperModel.new_from_mesh(obj.data) as pm:
        for fid in isolate_faces:
            pm.cut_out_face_region([fid])
        list(autozamboni.greedy_auto_cuts(pm, quality_level='NO_OVERLAPS_ALLOWED',
                                        target_loop_axis='Z', max_faces_per_component=max_faces))
    if section_name:
        io.write_new_build_section(obj.data, section_name, list(io.read_connected_component_sets(obj.data)))
    with PaperModel.from_existing(obj.data) as pm:
        pm.compute_build_step_numbers([0])
        seen = []
        length_errors = []
        overlap_areas = []
        flap_count = 0
        component_stats = []
        for cid, comp in pm.connected_components.items():
            assert not comp.cyclic and not comp.overlapping and not comp.has_overlapping_glue_flaps()
            seen.extend(comp.face_index_set)
            polygons = []
            for fid in comp.face_index_set:
                face = pm.bm.faces[fid]
                xy = [comp.get_unfolded_vertex_coordinates(v.co, fid, pm.local_coord_system_per_face) for v in face.verts]
                polygons.append(Polygon(xy))
                for i, vert in enumerate(face.verts):
                    j = (i+1) % len(xy)
                    length_errors.append(abs(float(np.linalg.norm(xy[i]-xy[j])) - float((vert.co-face.verts[j].co).length)))
            for flap in comp.glueflap_geometry.values():
                polygons.append(unary_union([Polygon(tri) for tri in flap]))
                flap_count += 1
            overlap_areas.extend(a.intersection(b).area for a,b in combinations(polygons,2))
            component_stats.append(dict(id=cid, faces=len(comp.face_index_set), step=comp.build_step_number))
        assert sorted(seen) == list(range(len(obj.data.polygons))), 'missing or duplicate faces'
        assert max(length_errors) < 1e-5, length_errors
        assert max(overlap_areas, default=0) < 1e-6, {'max_overlap_cm2':max(overlap_areas,default=0),'object':obj.name}
        cuts = [eid for eid in pm.edge_constraints if pm.edge_constraints[eid] in ('auto', 'cut')]
        # Verify using geometry, independent of string representation of cut constraints.
        cut_edge_ids = {e.index for e in pm.bm.edges if e.index in pm.glueflap_dict}
        assert flap_count == len(cut_edge_ids)
        initial.update(islands=len(component_stats), components=component_stats,
                       max_edge_length_error_mm=max(length_errors)*10,
                       max_overlap_area_mm2=max(overlap_areas, default=0)*100,
                       glue_flaps=flap_count, face_coverage='exactly once',
                       polyzamboni_overlap_flags=0)
    return initial


def settings(page_size):
    # Explicit values: upstream NamedTuple defaults include accidental tuples.
    return exporters.ExportSettings(
        paper_size=page_size, line_width=.6, cut_edge_ls='-', convex_fold_edge_ls='..',
        concave_fold_edge_ls='-.', glue_flap_ls='-', fold_hide_threshold_angle=0.,
        show_edge_numbers=True, edge_number_font_size=8, edge_number_offset=.15,
        show_build_step_numbers=True, prints_on_model_inside=True,
        color_of_cut_edges=[0,0,0], color_of_convex_fold_edges=[0,0,0],
        color_of_concave_fold_edges=[0,0,0], color_of_edge_numbers=[0,0,0],
        color_of_build_steps=[0,0,0], build_step_font_size=14,
        texture_quality='medium', color_of_glue_flaps=[.9,.9,.9],
        two_sided_pages=False, apply_texture_front=False, apply_texture_back=False,
        color_glue_flaps_front=True, color_glue_flaps_back=False)


def export_and_audit(obj, name, audit, page_size=(21.,29.7), output_dir=None):
    output_dir = Path(output_dir or ROOT / "output/pdf")
    output_dir.mkdir(parents=True, exist_ok=True)
    components = printprepper.create_print_data_for_all_components(obj, 1.)
    pages = printprepper.fit_components_on_pages(components, page_size, 1.5, .5, False)
    paired = Counter(e.edge_index for c in components for e in c.cut_edges + c.fold_edges_at_flaps)
    assert paired and set(paired.values()) == {2}, paired
    assert len(paired) == audit['glue_flaps']
    min_border = 100.
    inter_piece_overlap = 0.
    for page in pages:
        shapes=[]
        for comp in page:
            tris = [t.coords for t in comp.colored_triangles]
            tris += [tri for flap in comp.glue_flaps for tri in flap.tris]
            shape = unary_union([Polygon([comp.page_transform * np.array(v) for v in tri]) for tri in tris])
            x0,y0,x1,y1=shape.bounds
            min_border=min(min_border,x0,y0,page_size[0]-x1,page_size[1]-y1)
            shapes.append(shape)
        inter_piece_overlap=max(inter_piece_overlap, max((a.intersection(b).area for a,b in combinations(shapes,2)),default=0))
    assert min_border >= 1.49, min_border
    assert inter_piece_overlap < 1e-6
    audit.update(pages=len(pages), minimum_paper_border_mm=min_border*10,
                 edge_pairs=len(paired), matching_edge_number_pairs=len(paired), max_between_island_overlap_mm2=inter_piece_overlap*100)
    for fmt in ('pdf','svg'):
        exporters.MatplotlibBasedExporter(fmt, settings(page_size)).export(pages, str(output_dir/name))
    # Preserve page layout in the .blend as well.
    io.write_page_numbers(obj.data, {c.og_component_id: i for i,p in enumerate(pages) for c in p})
    io.write_page_transforms(obj.data, {c.og_component_id: c.page_transform for p in pages for c in p})
    return pages
