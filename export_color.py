"""Re-export the Tentacle in colour, using the saved Blender geometry."""
from pathlib import Path
import shutil
from papercraft.printing import export_colored_parts

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'output/tentacule-B-20cm'
PARTS = [('C','C_Corps'), ('BG','BG_Bras_bas'), ('BD','BD_Bras_leve'), ('V1','V1'), ('V2','V2'), ('V3','V3')]


def export():
    OUT.mkdir(parents=True, exist_ok=True)
    # A fresh clone can re-export the committed example without rebuilding it.
    for name in ['tentacule-B-20cm.blend', 'tentacule-B-20cm.obj', 'tentacule-B-20cm.mtl',
                 'validation.json', 'rendu-3d.png', 'vue-face.png']:
        target = OUT/name
        if not target.exists():
            shutil.copy2(ROOT/'examples/tentacle'/name, target)
    export_colored_parts(OUT/'tentacule-B-20cm.blend', OUT, OUT/'validation.json', PARTS)


if __name__=='__main__':
    export()
