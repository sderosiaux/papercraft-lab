"""Check the committed example without importing Blender or using a GPU."""
from pathlib import Path
import json
import math
import sys
from pypdf import PdfReader
from pypdf.generic import ContentStream

ROOT = Path(__file__).resolve().parent.parent


def check(directory):
    directory = Path(directory)
    report = json.loads((directory/'validation.json').read_text())
    colours = json.loads((directory/'validation-couleur.json').read_text())
    assert report['assembled_dimensions_mm'][2] == 200
    assert report['total_shell_pieces'] == 38
    assert report['physical_build_tested'] is False
    assert colours['print_side'] == 'outside' and colours['paper'] == 'white'
    assert colours['duplex'] is False
    for code, audit in report['parts'].items():
        assert not audit['errors'] and audit['closed_manifold']
        assert audit['positive_volume_cm3'] > 0
        assert audit['face_coverage'] == 'exactly once'
        assert audit['max_edge_length_error_mm'] < .0001
        assert audit['max_overlap_area_mm2'] < .0001
        assert colours['parts'][code]['edge_labels'] == 2*audit['edge_pairs']
        assert colours['parts'][code]['labels_on_coloured_faces'] == 0

    reader = PdfReader(directory/'tentacule-B-20cm-papercraft-A4.pdf')
    assert len(reader.pages) == 13
    for page in reader.pages:
        assert math.isclose(float(page.mediabox.width), 210*72/25.4, abs_tol=.01)
        assert math.isclose(float(page.mediabox.height), 297*72/25.4, abs_tol=.01)
    assert '50 mm' in reader.pages[0].extract_text()
    assert 'papier BLANC' in reader.pages[0].extract_text()
    assert 'pli montagne' in reader.pages[1].extract_text()

    def srgb(rgb):
        return tuple(12.92*x if x <= .0031308 else 1.055*x**(1/2.4)-.055 for x in rgb)

    # Check the material fills, not just the coloured headings. The previous
    # monochrome PDF had purple headings and would fail this regression check.
    for index in range(3, 12):
        expected = srgb((.30,.025,.38) if index < 9 else (.12,.55,.02))
        ops = ContentStream(reader.pages[index].get_contents(), reader).operations
        colour = None
        coloured_fill = False
        for args, operator in ops:
            if operator == b'rg':
                colour = tuple(float(v) for v in args)
            elif operator in (b'g', b'k'):
                colour = None
            elif operator in (b'f',b'f*',b'B',b'B*') and colour is not None:
                coloured_fill |= all(abs(a-b)<.00001 for a,b in zip(colour, expected))
        assert coloured_fill, f'Page {index+1} has no material-coloured face fill'

    for name in ['tentacule-B-20cm.blend','tentacule-B-20cm.obj','tentacule-B-20cm.mtl',
                 'rendu-3d.png','vue-face.png','LIRE-MOI.txt']:
        assert (directory/name).stat().st_size > 0
    assert len(list((directory/'svg').glob('*.svg'))) == 9
    print('OK: 13 A4 pages, material colours, paired labels, 200 mm model and example assets')


if __name__ == '__main__':
    check(sys.argv[1] if len(sys.argv)>1 else ROOT/'examples/tentacle')
