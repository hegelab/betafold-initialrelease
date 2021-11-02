import argparse
import itertools
import MDAnalysis as mda

parser = argparse.ArgumentParser("Reads pLLDT values from unrelaxed pdb and writes them to relaxed pdb.")
parser.add_argument("--unrelaxed", "-u", help="unrelaxed pdb file")
parser.add_argument("--relaxed", "-r", help="relaxed pdb file")
parser.add_argument("--out", "-o", help="out pdb file")
args = parser.parse_args()

unrelaxed = mda.Universe(args.unrelaxed)
ranked = mda.Universe(args.relaxed)

plddt = {}
for a in unrelaxed.select_atoms("name CA"):
    plddt[a.resindex] = a.tempfactor

for resindex, atoms in itertools.groupby(ranked.atoms, lambda x: x.resindex):
    for a in atoms:
        a.tempfactor = plddt[resindex]

ranked.atoms.write(args.out)
