import unittest
import umberjack
import os
import subprocess
import Utility
import shutil


# Simulation Configs
SIM_DIR = os.path.dirname(os.path.realpath(__file__)) + os.sep + "simulations"
SIM_BIN_DIR = SIM_DIR + os.sep + "bin"
SIM_DATA_FILENAME_PREFIX = "umberjack_unittest"
SIM_DATA_DIR = SIM_DIR + os.sep + "data" + os.sep + SIM_DATA_FILENAME_PREFIX
SIM_DATA_CONFIG_FILE = SIM_DATA_DIR + os.sep + "umberjack_unittest_sim.conf"

R_DIR = SIM_DIR + os.sep + "R"

# Executables
SIM_PIPELINE_PY = os.path.dirname(os.path.realpath(__file__)) + os.sep + "simulations" + os.sep + "sim_pipeline.py"
UMBERJACK_PY = os.path.dirname(os.path.realpath(__file__)) + os.sep + os.pardir + os.sep + "umberjack.py"
HYPHY_EXE = SIM_BIN_DIR + os.sep + "hyphy" + os.sep + "hyphy_2.2.3" + os.sep + "linux_x64" + os.sep + "HYPHYMP"
HYPHY_BASEDIR = SIM_BIN_DIR + os.sep + "hyphy" + os.sep + "hyphy_2.2.3" + os.sep + "res" + os.sep + "TemplateBatchFiles"
FASTTREE_EXE = SIM_BIN_DIR + os.sep + "fasttree" + os.sep + "fasttree_2.1.7" + os.sep + "linux_x64" + os.sep + "FastTree"

# INDELible dN/dS values that INDELible is aiming to simulate
INDELIBLE_DNDS_FILENAME = SIM_DATA_DIR + os.sep + "mixed" + os.sep + SIM_DATA_FILENAME_PREFIX + ".mixed.rates.csv"

# Full population dN/dS
EXPECTED_DNDS_FILENAME = SIM_DATA_DIR + os.sep + "mixed" + os.sep + SIM_DATA_FILENAME_PREFIX + ".mixed.dnds.tsv"

# Sliding Window configs
POPN_CONSENSUS_FASTA =  SIM_DATA_DIR + os.sep + "mixed" + os.sep + SIM_DATA_FILENAME_PREFIX + ".mixed.consensus.fasta"
REF = "consensus"

MODE = umberjack.MODE_DNDS
INSERT = False
MASK_STOP_CODON = True
MAPQ_CUTOFF = 20  # alignment quality cutoff
MAX_PROP_N = 0.1  # maximum proportion of N bases in MSA-aligned sequence
READ_QUAL_CUTOFF = 20   # Phred quality score cutoff [0,40]

MIN_WINDOW_BREADTH_COV_FRACTION = 0.875
MIN_WINDOW_DEPTH_COV = 10
WINDOW_SIZE = 300
WINDOW_SLIDE = 30


THREADS_PER_WINDOW = 4
WINDOW_PROCS = 3





class TestUmberjack(unittest.TestCase):

    def setUp(self):
        """
        Generate simulated data for unit tests
        """
        subprocess.check_call(["python", SIM_PIPELINE_PY, SIM_DATA_CONFIG_FILE])


    def test_umberjack_config_file(self):
        """
        Tests that umberjack parses the config file properly.
        """
        OUT_DIR =   SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX + os.sep + "Window" + str(WINDOW_SIZE) + ".fromconf"
        SAM_FILENAME = SIM_DATA_DIR + os.sep + "mixed" + os.sep + "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".mixed.reads.consensus.bwa.sort.query.sam"
        ACTUAL_DNDS_FILENAME = OUT_DIR + os.sep + 'actual_dnds_by_site.csv'
        CONFIG_FILE = OUT_DIR + os.sep + 'umberjack_unittest.conf'
        if not os.path.exists(OUT_DIR):
            os.makedirs(OUT_DIR)
        with open(CONFIG_FILE, 'w') as fh_config:
            fh_config.write("--sam_filename  {}\n".format(SAM_FILENAME))
            fh_config.write("--ref  {}\n".format(REF))
            fh_config.write("--out_dir  {}\n".format(OUT_DIR))
            fh_config.write("--map_qual_cutoff  {}\n".format(MAPQ_CUTOFF))
            fh_config.write("--read_qual_cutoff  {}\n".format(READ_QUAL_CUTOFF))
            fh_config.write("--max_prop_n  {}\n".format(MAX_PROP_N))
            fh_config.write("--window_size  {}\n".format(WINDOW_SIZE))
            fh_config.write("--window_slide  {}\n".format(WINDOW_SLIDE))
            fh_config.write("--window_breadth_cutoff  {}\n".format(MIN_WINDOW_BREADTH_COV_FRACTION))
            fh_config.write("--window_depth_cutoff  {}\n".format(MIN_WINDOW_DEPTH_COV))
            fh_config.write("--threads_per_window  {}\n".format(THREADS_PER_WINDOW))
            fh_config.write("--concurrent_windows  {}\n".format(WINDOW_PROCS))
            fh_config.write("--output_csv_filename  {}\n".format(ACTUAL_DNDS_FILENAME))
            fh_config.write("--hyphy_exe  {}\n".format(HYPHY_EXE))
            fh_config.write("--hyphy_basedir  {}\n".format(HYPHY_BASEDIR))
            fh_config.write("--fastree_exe  {}\n".format(FASTTREE_EXE))
            fh_config.write("--mode  {}\n".format(MODE))
            fh_config.write("--debug  \n")
        subprocess.check_call(["python", UMBERJACK_PY, "-f", CONFIG_FILE], env=os.environ)


    def test_umberjack_cmd_line(self):
        """
        Tests that umberjack runs properly from commandline.  Also tests no debug option.
        """
        OUT_DIR =   SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX + os.sep + "Window" + str(WINDOW_SIZE) + ".fromcmd"
        SAM_FILENAME = SIM_DATA_DIR + os.sep + "mixed" + os.sep + "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".mixed.reads.consensus.bwa.sort.query.sam"
        ACTUAL_DNDS_FILENAME = OUT_DIR + os.sep + 'actual_dnds_by_site.csv'
        cmd = ["python", UMBERJACK_PY,
               "--sam_filename", SAM_FILENAME,
               "--ref", REF,
               "--out_dir", OUT_DIR,
               "--map_qual_cutoff", str(MAPQ_CUTOFF),
               "--read_qual_cutoff", str(READ_QUAL_CUTOFF),
               "--max_prop_n", str(MAX_PROP_N),
               "--window_size", str(WINDOW_SIZE),
               "--window_slide", str(WINDOW_SLIDE),
               "--window_breadth_cutoff", str(MIN_WINDOW_BREADTH_COV_FRACTION),
               "--window_depth_cutoff", str(MIN_WINDOW_DEPTH_COV),
               "--threads_per_window", str(THREADS_PER_WINDOW),
               "--concurrent_windows", str(WINDOW_PROCS),
               "--output_csv_filename", ACTUAL_DNDS_FILENAME,
               "--hyphy_exe", HYPHY_EXE,
               "--hyphy_basedir", HYPHY_BASEDIR,
               "--fastree_exe", FASTTREE_EXE,
               "--mode", MODE]
        subprocess.check_call(cmd, env=os.environ)


    def test_eval_windows_async(self):
        # ART generated reads aligned to population consensus
        SAM_FILENAME = SIM_DATA_DIR + os.sep + "mixed" + os.sep + "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".mixed.reads.consensus.bwa.sort.query.sam"
        OUT_DIR =   SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX + os.sep + "Window" + str(WINDOW_SIZE)
        ACTUAL_DNDS_FILENAME = OUT_DIR + os.sep + 'actual_dnds_by_site.csv'
        START_NUCPOS = 1
        END_NUCPOS = Utility.get_longest_seq_size_from_fasta(POPN_CONSENSUS_FASTA)
        # TODO:  automate check output of R scripts.  Right now, we need to manually view HTML generated from R.
        # i.e.  it's up to you to open up ./simulations/R/umberjack_unit_test.html and inspect the graphs/contents.
        umberjack.eval_windows_async(ref=REF, sam_filename=SAM_FILENAME,
                                               out_dir=OUT_DIR, map_qual_cutoff=MAPQ_CUTOFF,
                                               read_qual_cutoff=READ_QUAL_CUTOFF, max_prop_n=MAX_PROP_N,
                                               start_nucpos=START_NUCPOS, end_nucpos=END_NUCPOS,
                                               window_size=WINDOW_SIZE,
                                               window_depth_cutoff=MIN_WINDOW_DEPTH_COV,
                                               window_breadth_cutoff=MIN_WINDOW_BREADTH_COV_FRACTION,
                                               threads_per_window=THREADS_PER_WINDOW,
                                               concurrent_windows=WINDOW_PROCS,
                                               output_csv_filename=ACTUAL_DNDS_FILENAME,
                                               window_slide=WINDOW_SLIDE,
                                               insert=INSERT,
                                               mask_stop_codon=MASK_STOP_CODON,
                                               debug=True)

        rconfig_file = R_DIR + os.sep + "umberjack_unit_test.config"
        with open(rconfig_file, 'w') as fh_out_config:
            fh_out_config.write("ACTUAL_DNDS_FILENAME=" + ACTUAL_DNDS_FILENAME + "\n")
            fh_out_config.write("EXPECTED_DNDS_FILENAME=" + EXPECTED_DNDS_FILENAME + "\n")
            fh_out_config.write("INDELIBLE_DNDS_FILENAME=" + INDELIBLE_DNDS_FILENAME + "\n")

        subprocess.check_call(["Rscript", "-e", "library(knitr); setwd('" + R_DIR + "'); spin('umberjack_unit_test.R')"],
                              shell=False, env=os.environ)
        shutil.copy(R_DIR + os.sep + "umberjack_unit_test.html",
                    OUT_DIR + os.sep + "umberjack_unit_test.html")


    def test_eval_windows_async_errfree(self):
        ERR_FREE_SAM_FILENAME = SIM_DATA_DIR + os.sep + "mixed" + os.sep + "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".mixed.reads.errFree.consensus.bwa.sort.query.sam"
        ERR_FREE_OUT_DIR = SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX + os.sep + "Window" + str(WINDOW_SIZE) + ".errFree"
        ERR_FREE_ACTUAL_DNDS_CSV = ERR_FREE_OUT_DIR + os.sep + 'actual_dnds_by_site.csv'
        START_NUCPOS = 1
        END_NUCPOS = Utility.get_longest_seq_size_from_fasta(POPN_CONSENSUS_FASTA)
        umberjack.eval_windows_async(ref=REF,
                                               sam_filename=ERR_FREE_SAM_FILENAME,
                                               out_dir=ERR_FREE_OUT_DIR,
                                               map_qual_cutoff=MAPQ_CUTOFF,
                                               read_qual_cutoff=READ_QUAL_CUTOFF,
                                               max_prop_n=MAX_PROP_N,
                                               start_nucpos=START_NUCPOS,
                                               end_nucpos=END_NUCPOS,
                                               window_size=WINDOW_SIZE,
                                               window_depth_cutoff=MIN_WINDOW_DEPTH_COV,
                                               window_breadth_cutoff=MIN_WINDOW_BREADTH_COV_FRACTION,
                                               threads_per_window=THREADS_PER_WINDOW,
                                               concurrent_windows=WINDOW_PROCS,
                                               output_csv_filename=ERR_FREE_ACTUAL_DNDS_CSV,
                                               mode=umberjack.MODE_DNDS,
                                               window_slide=WINDOW_SLIDE,
                                               insert=INSERT,
                                               mask_stop_codon=MASK_STOP_CODON,
                                               debug=True)
        # TODO:  verify concordance and correlation
        rconfig_file = R_DIR + os.sep + "umberjack_unit_test.config"
        with open(rconfig_file, 'w') as fh_out_config:
            fh_out_config.write("ACTUAL_DNDS_FILENAME=" + ERR_FREE_ACTUAL_DNDS_CSV + "\n")
            fh_out_config.write("EXPECTED_DNDS_FILENAME=" + EXPECTED_DNDS_FILENAME + "\n")
            fh_out_config.write("INDELIBLE_DNDS_FILENAME=" + INDELIBLE_DNDS_FILENAME + "\n")

        subprocess.check_call(["Rscript", "-e", "library(knitr); setwd('" + R_DIR + "'); spin('umberjack_unit_test.R')"],
                              shell=False, env=os.environ)
        shutil.copy(R_DIR + os.sep + "umberjack_unit_test.html",
                    ERR_FREE_OUT_DIR + os.sep + "umberjack_unit_test.html")

    def test_eval_windows_mpi(self):
        # ART generated reads aligned to population consensus
        SAM_FILENAME = SIM_DATA_DIR + os.sep + "mixed" + os.sep + "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".mixed.reads.consensus.bwa.sort.query.sam"
        OUT_DIR =   SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX + os.sep + "Window" + str(WINDOW_SIZE) + ".mpi"
        ACTUAL_DNDS_FILENAME = OUT_DIR + os.sep + 'actual_dnds_by_site.csv'
        START_NUCPOS = 1
        END_NUCPOS = Utility.get_longest_seq_size_from_fasta(POPN_CONSENSUS_FASTA)
        # TODO:  automate check output of R scripts.  Right now, we need to manually view HTML generated from R.
        # i.e.  it's up to you to open up ./simulations/R/umberjack_unit_test.html and inspect the graphs/contents.

        # Can't call umberjack.eval_windows_mpi() directly since we need to invoke it with mpirun
        subprocess.check_call(["mpirun",
                               "-H", "localhost",  # host
                               "-n", "2",  # copies of program per node
                               "-output-filename", OUT_DIR + os.sep + "Test_umberjack.log",  # stdout, stderr logfile

                               "python", UMBERJACK_PY,
                               "--out_dir", OUT_DIR,
                               "--map_qual_cutoff", str(MAPQ_CUTOFF),
                               "--read_qual_cutoff", str(READ_QUAL_CUTOFF),
                               "--max_prop_n", str(MAX_PROP_N),
                               "--window_size", str(WINDOW_SIZE),
                               "--window_slide", str(WINDOW_SLIDE),
                               "--window_breadth_cutoff", str(MIN_WINDOW_BREADTH_COV_FRACTION),
                               "--window_depth_cutoff", str(MIN_WINDOW_DEPTH_COV),
                               "--start_nucpos", str(START_NUCPOS),
                               "--end_nucpos", str(END_NUCPOS),
                               "--threads_per_window", str(THREADS_PER_WINDOW),
                               "--output_csv_filename",  ACTUAL_DNDS_FILENAME,
                               "--mode",  "DNDS",
                               "--mpi",
                               "--sam_filename",  SAM_FILENAME,
                               "--ref", REF,
                               "--debug"])


        rconfig_file = os.path.dirname(__file__) + os.sep +"simulations" + os.sep + "R" + os.sep + "umberjack_unit_test.config"
        with open(rconfig_file, 'w') as fh_out_config:
            fh_out_config.write("ACTUAL_DNDS_FILENAME=" + ACTUAL_DNDS_FILENAME + "\n")
            fh_out_config.write("EXPECTED_DNDS_FILENAME=" + EXPECTED_DNDS_FILENAME + "\n")
            fh_out_config.write("INDELIBLE_DNDS_FILENAME=" + INDELIBLE_DNDS_FILENAME + "\n")

        subprocess.check_call(["Rscript", "-e", "library(knitr); setwd('" + R_DIR + "'); spin('umberjack_unit_test.R')"],
                              shell=False, env=os.environ)
        shutil.copy(R_DIR + os.sep + "umberjack_unit_test.html",
                    OUT_DIR + os.sep + "umberjack_unit_test.html")



if __name__ == '__main__':
    unittest.main()