# Processes Indelible-related files
import csv
from cStringIO import StringIO
import Bio.Phylo as Phylo
from collections import namedtuple
import random
from numpy.random import RandomState, multinomial

# Keep track of Partitions for INDELible control.txt file
Partition = namedtuple("Partition", field_names=["TreeFile", "TreeLen", "Codons"])

# Keep track of unique Trees separately for INDELible control.txt file, so that we don't write the same Tree multiple times
Tree = namedtuple("Tree", field_names=["TreeFile", "TreeLen"])



def get_tree_string(tree_txt):
    """
    Parses the trees.txt file autogenerated by indelible.
    ASSUMES:
    - File starts with comments
    - Header: FILE	TREE	NTAXA	REP	PART	LENGTH	DEPTH	MAX PAIRWISE DISTANCE	TREE STRING
    - Contents follow:

    small_population.50.0	bigtree	100	1	1	50	1.1657	2.25102	((((((otu1:0.688568,....)ROOT;

    :param str tree_txt: full filepath of trees.txt file
    :return str:  first tree string encountered
    """
    with open(tree_txt, 'rU') as fh_in:
        # Skip the comments
        TOTAL_COMMENTS_LINES = 6
        for i in range(0, TOTAL_COMMENTS_LINES):
            fh_in.next()
        reader = csv.DictReader(fh_in, delimiter="\t")
        for row in reader:
            if not row["FILE"]:
                continue
            return row["TREE STRING"]

    return None


def get_tree_stringio(tree_txt):
    """
    Parses the trees.txt file autogenerated by indelible.
    ASSUMES:
    - File starts with comments
    - Header: FILE	TREE	NTAXA	REP	PART	LENGTH	DEPTH	MAX PAIRWISE DISTANCE	TREE STRING
    - Contents follow:

    small_population.50.0	bigtree	100	1	1	50	1.1657	2.25102	((((((otu1:0.688568,....)ROOT;

    :param str tree_txt: full filepath of trees.txt file
    :return StringIO:  tree string as StringIO handle
    """
    with open(tree_txt, 'rU') as fh_in:
        # Skip the comments
        TOTAL_COMMENTS_LINES = 6
        for i in range(0, TOTAL_COMMENTS_LINES):
            fh_in.next()
        reader = csv.DictReader(fh_in, delimiter="\t")
        for row in reader:
            if not row["FILE"]:
                continue
            return StringIO(row["TREE STRING"])

    return None


def write_tree(tree_txt, tree_newick):
    """
    Parses the trees.txt file autogenerated by indelible.  Writes out tree to a newick file.
    ASSUMES:
    - File starts with comments
    - Header: FILE	TREE	NTAXA	REP	PART	LENGTH	DEPTH	MAX PAIRWISE DISTANCE	TREE STRING
    - Contents follow:

    small_population.50.0	bigtree	100	1	1	50	1.1657	2.25102	((((((otu1:0.688568,....)ROOT;

    :param str tree_txt: full filepath of trees.txt file
    :param str tree_newick:  full filepath of newick file to write out.
    """
    with open(tree_txt, 'rU') as fh_in, open(tree_newick, 'w') as fh_out:
        # Skip the comments
        TOTAL_COMMENTS_LINES = 6
        for i in range(0, TOTAL_COMMENTS_LINES):
            fh_in.next()
        reader = csv.DictReader(fh_in, delimiter="\t")
        for row in reader:
            if not row["FILE"]:
                continue
            tree_str = row["TREE STRING"]
            fh_out.write(tree_str)
            break



def write_partition_csv(partition_csv, treefile_to_codons, tree_scaling_rates, seed=None):
    """
    Writes a Partition CSV with headers TreeFile, TreeLen, Codons
    which tells batch_indelible.py how to partition the genome by phylogenetic topology, mutation rate.

    For each contiguous genome section corresponding to a tree topology, divvy up the section into separate mutation rates.
    The size of a subsection corresponding to a mutation rate is drawn
    from a multinomial distro.
    The order of the mutation rate subsections is also shuffed for each tree topology.

    Each (tree topology,  mutation rate) combination forms a distinct INDELible partition.

    :param str partition_csv: filepath to output partition CSV
    :param OrderedDict treefile_to_codons: {str: int}  filepath to newick tree  ==> number of codons to apply to that tree topology
    :param list tree_scaling_rates:  float scaling rates to randomly apply to each tree
    :param int seed:  random seed
    """

    # Create partition CSV
    with open(partition_csv, 'w') as fh_out_partition_csv:
        writer = csv.DictWriter(fh_out_partition_csv, fieldnames=Partition._fields)
        writer.writeheader()

        randomizer = random.Random(seed)
        np_rander = RandomState(seed)


        # assign equal probability of selecting each scaling rate
        prob_scaling_rates = [1.0/len(tree_scaling_rates)]*len(tree_scaling_rates)


        # for each breakpoint tree & scaling rate combo, create a new genome partition
        for treefile, recombo_codons in treefile_to_codons.iteritems():

            # shuffle the scaling rates for each recombination partition
            randomizer.shuffle(tree_scaling_rates)  # shuffles in place

            # Select number of codons for each scaling rate
            recombo_scale_partition_sizes = np_rander.multinomial(n=recombo_codons, pvals=prob_scaling_rates, size=1)[0]

            for i, scaling_rate in enumerate(tree_scaling_rates):
                if recombo_scale_partition_sizes[i] == 0:
                    continue
                partition = Partition(TreeFile=treefile, TreeLen=scaling_rate, Codons=recombo_scale_partition_sizes[i])
                writer.writerow(partition._asdict())