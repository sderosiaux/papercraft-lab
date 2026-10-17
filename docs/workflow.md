# Making another model

## Concept approval

Start with a subject, a finished height and a difficulty level. Generate a few concept images that show a possible paper build: large flat faces, few thin projections and a stable base. A front and three-quarter view help reveal parts that would be hidden in one image.

Choose a concept before modelling it. The concept image is a design reference; the printable pattern must come from the final 3D geometry. This repository includes a procedural model built with Blender's Python API. It does not contain an image-generation service or an image-to-3D model.

A prompt to adapt:

> Create a concept sheet for a 20 cm paper sculpture of [subject]. Show three complexity levels. Use flat polygonal faces, broad glueable attachments and a stable base. Keep important features readable at this scale. Show an unobstructed three-quarter view on a neutral background. This is a visual concept, not a printable cutting pattern.

## Build and unfold

Use centimetres for mesh coordinates and flat polygons for paper faces. Give each detachable accessory a flat back and a matching surface on the main body. Decide which face closes each volume last, while the inside is still accessible for gluing.

This example builds and unfolds a blue 5 cm cube. Run it from the repository root after `make setup`:

```python
import json
from pathlib import Path
from papercraft.pipeline import bpy, unwrap_and_audit, export_and_audit
from papercraft.printing import export_colored_parts

out = Path("output/my-cube").resolve()
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 0.01
bpy.ops.mesh.primitive_cube_add(size=5)
obj = bpy.context.object
obj.name = "Cube"
obj.data.uv_layers.new(name="PaperUV")
mat = bpy.data.materials.new("Blue")
mat.diffuse_color = (0.03, 0.25, 0.65, 1.0)
obj.data.materials.append(mat)

audit = unwrap_and_audit(obj, max_faces=6, flap_height=0.5, section_name="C")
export_and_audit(obj, "C", audit, output_dir=out/"patrons-source")
(out/"validation.json").write_text(json.dumps({"parts": {"C": audit}}, indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out/"cube.blend"))
export_colored_parts(out/"cube.blend", out, out/"validation.json", [("C", "Cube")])
```

The PDF and SVG pages are under `output/my-cube/patrons-source/`. These are raw patterns; add a legend and a 50 mm scale bar before distributing them. The Tentacle packager shows how to merge those instructions without resizing the pattern. For short pieces, limit the usable layout height to leave space for a page header, as the Tentacle builder does.

Each component must use a single solid material for this colour exporter. It exports actual face colours; studio lighting and render shadows are not baked into the PDF. Importing `papercraft.pipeline` initializes Blender and PolyZamboni, including their GPU shaders.

## Print orientation

Colour printing on white paper uses the outside of the model. In the finished Tentacle PDF, dotted lines are mountain folds and dash-dot lines are valley folds when viewed from the coloured side. Solid outlines are cuts. Thin grey leaders connect labels to edges and are not cuts.

An inside-facing monochrome pattern is mirrored relative to an outside-facing colour pattern. Changing the print side requires changing the geometry's orientation on the page and the fold legend together. Adding colour to an inside-facing template would reverse the assembled shape.

The colour exporter handles that orientation and leaves tabs pale. Edge numbers are placed on tabs or outside the parts so they do not remain visible on the assembled surfaces. Copy labels from waste paper onto the white back before cutting.

## Checks before publishing a pattern

Run `unwrap_and_audit()` and inspect the generated reports. The independent checks compare actual polygon intersections and edge lengths, alongside PolyZamboni's overlap flags. Open the `.blend` file and compare the rendered shape with the approved concept.

Render every PDF page to images and inspect the instructions, small labels, margins and colours. The numbers need to remain readable at actual print size. Match the printed 50 mm bar with a ruler; disable any fit-to-page setting.

Build an ordinary-paper prototype before using heavier stock. Start with a difficult accessory, check whether tweezers and glue can reach its joints, and note which faces need to close last. A valid flat net alone does not test assembly order or cardstock thickness.
