"""
Tests the chemistry/structure module
"""
try:
    import cStringIO as StringIO
except ImportError:
    # Must be Python 3
    import io as StringIO
import chemistry.structure as structure
import unittest
from utils import get_fn

def reset_stringio(io):
    """ Resets a StringIO instance to "empty-file" state """
    io.seek(0)
    io.truncate()
    return io

class TestChemistryStructure(unittest.TestCase):
    
    def setUp(self):
        self.pdb = get_fn('4lzt.pdb')
        self.pdbgz = get_fn('4lzt.pdb.gz')
        self.pdbbz2 = get_fn('4lzt.pdb.bz2')
        self.models = get_fn('2koc.pdb')
        self.overflow = get_fn('4lyt_vmd.pdb')
        self.simple = get_fn('ala_ala_ala.pdb')

    def testAscii(self):
        """ Test PDB file parsing """
        self._check4lyt(structure.read_PDB(self.pdb))
        # The PDB file with multiple models
        pdbfile = structure.read_PDB(open(self.models))
        self.assertEqual(len(pdbfile.pdbxyz), 20)
        self.assertEqual(pdbfile.pdbxyz[0][:3], [-8.886, -5.163, 9.647])
        self.assertEqual(pdbfile.pdbxyz[19][-3:], [-12.051, 5.205, -2.146])

    def testGzip(self):
        """ Test Gzipped-PDB file parsing """
        self._check4lyt(structure.read_PDB(self.pdbgz))

    def testBzip(self):
        """ Test Bzipped-PDB file parsing """
        self._check4lyt(structure.read_PDB(self.pdbbz2))

    def testVmdOverflow(self):
        """ Test PDB file where atom and residue numbers overflow """
        pdbfile = structure.read_PDB(self.overflow)
        self.assertEqual(len(pdbfile.atoms), 110237)
        self.assertEqual(len(pdbfile.residues), 35697)
        self.assertEqual(pdbfile.box, [0, 0, 0, 90, 90, 90])

    def testPdbWriteSimple(self):
        """ Test PDB file writing on a very simple input structure """
        pdbfile = structure.read_PDB(self.simple)
        self.assertEqual(len(pdbfile.atoms), 33)
        self.assertEqual(len(pdbfile.residues), 3)
        output = StringIO.StringIO()
        pdbfile.write_pdb(output)
        output.seek(0)
        pdbfile2 = structure.read_PDB(output)
        self.assertEqual(len(pdbfile2.atoms), 33)
        self.assertEqual(len(pdbfile2.residues), 3)
        self._compareInputOutputPDBs(pdbfile, pdbfile2)

    def testPdbWriteModels(self):
        """ Test PDB file writing from NMR structure with models """
        pdbfile = structure.read_PDB(self.models)
        self.assertEqual(len(pdbfile.pdbxyz), 20)
        self.assertEqual(len(pdbfile.atoms), 451)
        output = StringIO.StringIO()
        structure.write_PDB(pdbfile, output)
        output.seek(0)
        pdbfile2 = structure.read_PDB(output)
        self.assertEqual(len(pdbfile2.atoms), 451)
        self._compareInputOutputPDBs(pdbfile, pdbfile2)

    def testPdbWriteXtal(self):
        """ Test PDB file writing from a Xtal structure """
        pdbfile = structure.read_PDB(self.pdb)
        self._check4lyt(pdbfile)
        output = StringIO.StringIO()
        pdbfile.write_pdb(output, renumber=False)
        output.seek(0)
        pdbfile2 = structure.read_PDB(output)
        self._check4lyt(pdbfile2, check_meta=False)
        self._compareInputOutputPDBs(pdbfile, pdbfile2)
        output = reset_stringio(output)
        structure.write_PDB(pdbfile, output)
        output.seek(0)
        pdbfile3 = structure.read_PDB(output)
        self._check4lyt(pdbfile3, check_meta=False)
        self._compareInputOutputPDBs(pdbfile, pdbfile3, True)
        # Now check that renumbering is done correctly. 4lzt skips residues 130
        # through 200
        for res1, res2 in zip(pdbfile.residues, pdbfile3.residues):
            if res1.idx < 129:
                self.assertEqual(res1.number, res2.number)
            elif res1.idx < 135:
                self.assertEqual(res1.number, res2.number + 71)
            else:
                # Some residue numbers are skipped in the water numbering
                self.assertGreaterEqual(res1.number, res2.number + 71 + 794)

    def testPdbWriteAltlocOptions(self):
        """ Test PDB file writing with different altloc options """
        pdbfile = structure.read_PDB(self.pdb)
        self._check4lyt(pdbfile)
        output = StringIO.StringIO()
        pdbfile.write_pdb(output, renumber=False, altlocs='all')
        output.seek(0)
        pdbfile2 = structure.read_PDB(output)
        self._check4lyt(pdbfile2, check_meta=False)
        self._compareInputOutputPDBs(pdbfile, pdbfile2)
        # Check that 'first' option works
        output = reset_stringio(output)
        pdbfile.write_pdb(output, renumber=False, altlocs='first')
        output.seek(0)
        pdbfile3 = structure.read_PDB(output)
        self._check4lyt(pdbfile3, check_meta=False, has_altloc=False)
        self._compareInputOutputPDBs(pdbfile, pdbfile3, altloc_option='first')
        # Check that the 'occupancy' option works
        output = reset_stringio(output)
        structure.write_PDB(pdbfile, output, renumber=False, altlocs='occupancy')
        output.seek(0)
        pdbfile4 = structure.read_PDB(output)
        self._check4lyt(pdbfile4, check_meta=False, has_altloc=False)
        self._compareInputOutputPDBs(pdbfile, pdbfile4, altloc_option='occupancy')
        # Double-check 'first' vs. 'occupancy'. Residue 85 (SER) has a conformer
        # A that has an occupancy of 0.37 and conformer B with occupancy 0.63
        self.assertEqual(pdbfile3.residues[84][4].xx, -4.162)
        self.assertEqual(pdbfile4.residues[84][4].xx, -4.157)

    def _compareInputOutputPDBs(self, pdbfile, pdbfile2, reordered=False,
                                altloc_option='all'):
        # Now go through all atoms and compare their attributes
        for a1, a2 in zip(pdbfile.atoms, pdbfile2.atoms):
            if altloc_option in ('first', 'all'):
                self.assertEqual(a1.occupancy, a2.occupancy)
                a1idx = a1.idx
            elif altloc_option == 'occupancy':
                a, occ = a1, a1.occupancy
                for key, oa in a1.other_locations.items():
                    if oa.occupancy > occ:
                        occ = oa.occupancy
                        a = oa
                a1idx = a1.idx
                a1 = a # This is the atom we want to compare with
            self.assertEqual(a1.atomic_number, a2.atomic_number)
            self.assertEqual(a1.name, a2.name)
            self.assertEqual(a1.type, a2.type)
            self.assertEqual(a1.mass, a2.mass)
            self.assertEqual(a1.charge, a2.charge)
            self.assertEqual(a1.bfactor, a2.bfactor)
            self.assertEqual(a1.altloc, a2.altloc)
            self.assertEqual(a1idx, a2.idx)
            if altloc_option == 'all':
                self.assertEqual(set(a1.other_locations.keys()),
                                 set(a2.other_locations.keys()))
            self.assertEqual(a1.xx, a2.xx)
            self.assertEqual(a1.xy, a2.xy)
            self.assertEqual(a1.xz, a2.xz)
            if altloc_option != 'all':
                # There should be no alternate locations unless we keep them all
                self.assertEqual(len(a2.other_locations), 0)
            if not reordered:
                self.assertEqual(a1.number, a2.number)
            # Search all alternate locations as well
            for k1, k2 in zip(sorted(a1.other_locations.keys()),
                              sorted(a2.other_locations.keys())):
                self.assertEqual(k1, k2)
                oa1 = a1.other_locations[k1]
                oa2 = a2.other_locations[k2]
                self.assertEqual(oa1.atomic_number, oa2.atomic_number)
                self.assertEqual(oa1.name, oa2.name)
                self.assertEqual(oa1.type, oa2.type)
                self.assertEqual(oa1.mass, oa2.mass)
                self.assertEqual(oa1.charge, oa2.charge)
                self.assertEqual(oa1.occupancy, oa2.occupancy)
                self.assertEqual(oa1.bfactor, oa2.bfactor)
                self.assertEqual(oa1.altloc, oa2.altloc)
                self.assertEqual(oa1.idx, oa2.idx)
                if not reordered:
                    self.assertEqual(oa1.number, oa2.number)
        # Now compare all residues
        for r1, r2 in zip(pdbfile.residues, pdbfile2.residues):
            self.assertEqual(r1.name, r2.name)
            self.assertEqual(r1.idx, r2.idx)
            self.assertEqual(r1.ter, r2.ter)
            self.assertEqual(len(r1), len(r2))
            self.assertEqual(r1.insertion_code, r2.insertion_code)
            if not reordered:
                self.assertEqual(r1.number, r2.number)

    # Private helper test functions
    def _check4lyt(self, obj, check_meta=True, has_altloc=True):
        self.assertEqual(len(obj.pdbxyz), 1)
        self.assertEqual(obj.box,
                         [27.24, 31.87, 34.23, 88.52, 108.53, 111.89])
        self.assertEqual(obj.space_group, 'P 1')
        self.assertEqual(len(obj.atoms), 1164)
        self.assertEqual(len(obj.residues[0]), 9)
        # Check that alternate conformations are taken into account
        total_natoms = 0
        for i, atom in enumerate(obj.atoms):
            total_natoms += 1
            for key in atom.other_locations:
                total_natoms += 1
                atom2 = atom.other_locations[key]
                self.assertEqual(atom.altloc, 'A')
                self.assertEqual(atom2.altloc, 'B')
                if i in [388, 389]:
                    # Sum of atom 388/389 occupancies is 1.02
                    self.assertEqual(atom2.occupancy + atom.occupancy, 1.02)
                else:
                    # Other atoms occupancy sums are 1 exactly
                    self.assertEqual(atom2.occupancy + atom.occupancy, 1)
        if has_altloc:
            self.assertEqual(total_natoms, 1183)
            self.assertEqual(len(obj.atoms), 1164)
        else:
            self.assertEqual(total_natoms, 1164) # 19 atoms have altlocs
        # Check the metadata
        if check_meta:
            self.assertEqual(obj.experimental, 'X-RAY DIFFRACTION')
            self.assertEqual(len(obj.residues), 274)
            self.assertEqual(obj.pmid, '9761848')
            self.assertEqual(obj.journal_authors, 'M.A.WALSH,T.R.SCHNEIDER,'
                             'L.C.SIEKER,Z.DAUTER,V.S.LAMZIN,K.S.WILSON')
            self.assertEqual(obj.journal, 'ACTA CRYSTALLOGR.,SECT.D')
            self.assertEqual(obj.year, 1998)
            self.assertEqual(obj.keywords, ['HYDROLASE', 'O-GLYCOSYL',
                             'GLYCOSIDASE'])
            self.assertEqual(obj.title, 'REFINEMENT OF TRICLINIC HEN EGG-WHITE '
                             'LYSOZYME AT ATOMIC RESOLUTION.')
            self.assertEqual(obj.doi, '10.1107/S0907444997013656')
            self.assertEqual(obj.volume, '54')
            self.assertEqual(obj.page, '522')
        # Check the TER card is picked up
        for i, residue in enumerate(obj.residues):
            if i == 128:
                self.assertTrue(residue.ter)
            else:
                self.assertFalse(residue.ter)

if __name__ == '__main__':
    unittest.main()