import os
import unittest
import subprocess
import shutil
import csv
import logging

import UmberjackWork
import Utility
import config.settings as settings


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
HYPHY_LIBDIR = SIM_BIN_DIR + os.sep + "hyphy" + os.sep + "hyphy_2.2.3" + os.sep + "res" + os.sep + "TemplateBatchFiles"
HYPHY_BASEDIR = os.path.abspath(os.path.realpath(__file__) + os.sep + os.pardir + os.sep + os.pardir + "hyphy" + os.sep + "batchfile")
FASTTREE_EXE = SIM_BIN_DIR + os.sep + "fasttree" + os.sep + "fasttree_2.1.7" + os.sep + "linux_x64" + os.sep + "FastTree"

# INDELible dN/dS values that INDELible is aiming to simulate
INDELIBLE_DNDS_FILENAME = SIM_DATA_DIR + os.sep +  "fullpopn" + os.sep + SIM_DATA_FILENAME_PREFIX + "_RATES.csv"

# Full population dN/dS
EXPECTED_DNDS_FILENAME = SIM_DATA_DIR + os.sep +  "subs" + os.sep + SIM_DATA_FILENAME_PREFIX + ".dnds.tsv"

# Sliding Window configs
POPN_CONSENSUS_FASTA =  SIM_DATA_DIR + os.sep + "fullpopn" + os.sep +  SIM_DATA_FILENAME_PREFIX + ".consensus.fasta"
REF = "consensus"

MODE = UmberjackWork.MODE_DNDS
INSERT = False
MASK_STOP_CODON = True
REMOVE_DUPLICATES  = True
MAPQ_CUTOFF = 20  # alignment quality cutoff
MAX_PROP_N = 0.1  # maximum proportion of N bases in MSA-aligned sequence
READ_QUAL_CUTOFF = 20   # Phred quality score cutoff [0,40]

MIN_WINDOW_BREADTH_COV_FRACTION = 0.875
MIN_WINDOW_DEPTH_COV = 10
WINDOW_SIZE = 300
WINDOW_SLIDE = 30


THREADS_PER_WINDOW = 4
WINDOW_PROCS = 3


MIN_CONCORD = 0.8
LOGGER = logging.getLogger(__name__)

class TestUmberjack(unittest.TestCase):

    def _is_good_concordance(self, concord_csv):
        """
        Read in umberjack_unit_test.concordance.csv and check that each estimated dnds metric
        has concordance with expected dnds >= MIN_CONCORD.
        :param str concord_csv: file path to umberjack_unit_test.concordance.csv
        """
        with open(concord_csv, 'rU') as fh_in_csv:
            reader = csv.DictReader(fh_in_csv)
            for row in reader:
                if row["Metric"].find("NoLowSub") >=0:  # Only the sites in which we exclude window-sites with low substitutions will be accurate
                    self.assertGreaterEqual(float(row["Concordance"]), MIN_CONCORD,
                                        "Expect concordance >=" + str(MIN_CONCORD) + " but got " +
                                        row["Concordance"] + " for metric " + row["Metric"])
                print row["Metric"] + " concordance=" + row["Concordance"]


    def check_concordance(self, out_dir, actual_dnds_filename, expected_dnds_filename):
        """
        Sets up the config files for R scripts and checks whether dnds concordance is good.
        :param out_dir:
        :param actual_dnds_filename:
        :param expected_dnds_filename:
        :return:
        """
        rconfig_file = out_dir + os.sep + "umberjack_unit_test.config"
        with open(rconfig_file, 'w') as fh_out_config:
            fh_out_config.write("ACTUAL_DNDS_FILENAME=" + actual_dnds_filename + "\n")
            fh_out_config.write("EXPECTED_DNDS_FILENAME=" + expected_dnds_filename + "\n")


        subprocess.check_call(["Rscript",
                               "launch_umberjack_unittest_report.R",
                               rconfig_file,
                               out_dir
                              ],
                              shell=False, env=os.environ, cwd=R_DIR)

        concord_csv = out_dir + os.sep + "umberjack_unit_test.concordance.csv"
        self._is_good_concordance(concord_csv=concord_csv)


    def setUp(self):
        """
        Generate simulated data for unit tests
        """
        settings.setup_logging()
        if os.path.exists(SIM_DATA_DIR):  # Clean the simulated data, except for the config file
            dirpar, dirnames, files =  os.walk(SIM_DATA_DIR).next()
            for dirname in dirnames:
                full_dirpath = dirpar + os.sep + dirname
                shutil.rmtree(full_dirpath)
                print ("Removed " + full_dirpath)
            for f in files:
                full_filepath = dirpar + os.sep + f
                if full_filepath != SIM_DATA_CONFIG_FILE:
                    os.remove(full_filepath)
                    print ("Removed " + full_filepath)

        if os.path.exists(SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX):
            print ("Removed " + SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX)
            shutil.rmtree(SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX)

        subprocess.check_call(["python", SIM_PIPELINE_PY, SIM_DATA_CONFIG_FILE])



    def test_umberjack_config_file(self):
        """
        Tests that umberjack parses the config file properly.
        """
        OUT_DIR =   SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX + os.sep + "Window" + str(WINDOW_SIZE) + ".fromconf"
        SAM_FILENAME = SIM_DATA_DIR + os.sep +  "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".reads.bwa.sort.query.sam"
        ACTUAL_DNDS_FILENAME = OUT_DIR + os.sep + os.path.splitext(os.path.basename(SAM_FILENAME))[0] + ".dnds.csv"
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
            #fh_config.write("--hyphy_exe  {}\n".format(HYPHY_EXE))
            #fh_config.write("--hyphy_basedir  {}\n".format(HYPHY_BASEDIR))
            fh_config.write("--fastree_exe  {}\n".format(FASTTREE_EXE))
            fh_config.write("--mode  {}\n".format(MODE))
            fh_config.write("--debug  \n")
        subprocess.check_call(["python", UMBERJACK_PY, "-f", CONFIG_FILE], env=os.environ)

        rconfig_file = R_DIR + os.sep + "umberjack_unit_test.config"
        with open(rconfig_file, 'w') as fh_out_config:
            fh_out_config.write("ACTUAL_DNDS_FILENAME=" + ACTUAL_DNDS_FILENAME + "\n")
            fh_out_config.write("EXPECTED_DNDS_FILENAME=" + EXPECTED_DNDS_FILENAME + "\n")
            fh_out_config.write("INDELIBLE_DNDS_FILENAME=" + INDELIBLE_DNDS_FILENAME + "\n")

        subprocess.check_call(["Rscript", "-e", "library(knitr); " +
                               "setwd('" + R_DIR + "'); " +
                               "spin('umberjack_unit_test.R', knit=FALSE);" +
                               "knit2html('./umberjack_unit_test.Rmd', stylesheet='./markdown_bigwidth.css');"],
                              shell=False, env=os.environ)
        shutil.copy(R_DIR + os.sep + "umberjack_unit_test.html",
                    OUT_DIR + os.sep + "umberjack_unit_test.html")

        concord_csv = OUT_DIR + os.sep + "umberjack_unit_test.concordance.csv"
        shutil.copy(R_DIR + os.sep + "umberjack_unit_test.concordance.csv",
                    concord_csv)
        self._is_good_concordance(concord_csv=concord_csv)


    def test_umberjack_cmd_line(self):
        """
        Tests that umberjack runs properly from commandline.  Also tests no debug option.
        """

        OUT_DIR =   SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX + os.sep + "Window" + str(WINDOW_SIZE) + ".fromcmd"
        SAM_FILENAME = SIM_DATA_DIR + os.sep +  "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".reads.bwa.sort.query.sam"
        ACTUAL_DNDS_FILENAME = OUT_DIR + os.sep + os.path.splitext(os.path.basename(SAM_FILENAME))[0] + ".dnds.csv"
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
               "--hyphy_exe", HYPHY_EXE,
               "--hyphy_basedir", HYPHY_BASEDIR,
               "--fastree_exe", FASTTREE_EXE,
               "--mode", MODE]
        subprocess.check_call(cmd, env=os.environ)

        rconfig_file = R_DIR + os.sep + "umberjack_unit_test.config"
        with open(rconfig_file, 'w') as fh_out_config:
            fh_out_config.write("ACTUAL_DNDS_FILENAME=" + ACTUAL_DNDS_FILENAME + "\n")
            fh_out_config.write("EXPECTED_DNDS_FILENAME=" + EXPECTED_DNDS_FILENAME + "\n")
            fh_out_config.write("INDELIBLE_DNDS_FILENAME=" + INDELIBLE_DNDS_FILENAME + "\n")

        subprocess.check_call(["Rscript", "-e", "library(knitr); " +
                               "setwd('" + R_DIR + "'); " +
                               "spin('umberjack_unit_test.R', knit=FALSE);" +
                               "knit2html('./umberjack_unit_test.Rmd', stylesheet='./markdown_bigwidth.css');"],
                              shell=False, env=os.environ)
        shutil.copy(R_DIR + os.sep + "umberjack_unit_test.html",
                    OUT_DIR + os.sep + "umberjack_unit_test.html")

        concord_csv = OUT_DIR + os.sep + "umberjack_unit_test.concordance.csv"
        shutil.copy(R_DIR + os.sep + "umberjack_unit_test.concordance.csv",
                    concord_csv)
        self._is_good_concordance(concord_csv=concord_csv)


    def test_eval_windows_async_sam(self):
        # ART generated reads aligned to population consensus
        SAM_FILENAME = SIM_DATA_DIR + os.sep +  "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".reads.bwa.sort.query.sam"
        OUT_DIR =  (SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX  + os.sep +
                    "window{}.breadth{}.depth{}".format(WINDOW_SIZE, MIN_WINDOW_BREADTH_COV_FRACTION, MIN_WINDOW_DEPTH_COV))
        ACTUAL_DNDS_FILENAME = OUT_DIR + os.sep + os.path.splitext(os.path.basename(SAM_FILENAME))[0] + ".dnds.csv"
        START_NUCPOS = 1
        END_NUCPOS = Utility.get_longest_seq_size_from_fasta(POPN_CONSENSUS_FASTA)

        # i.e.  it's up to you to open up ./simulations/R/umberjack_unit_test.html and inspect the graphs/contents.

        import pool.OneNodePool
        kwargs = dict(ref=REF,
                                         sam_filename=SAM_FILENAME,
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
                                         remove_duplicates=REMOVE_DUPLICATES,
                                         debug=True,
                                         pool=pool.OneNodePool.OneNodePool(concurrent_windows=WINDOW_PROCS))
        worker = UmberjackWork.UmberjackWork(**kwargs)
        worker.start()

        rconfig_file = R_DIR + os.sep + "umberjack_unit_test.config"
        with open(rconfig_file, 'w') as fh_out_config:
            fh_out_config.write("ACTUAL_DNDS_FILENAME=" + ACTUAL_DNDS_FILENAME + "\n")
            fh_out_config.write("EXPECTED_DNDS_FILENAME=" + EXPECTED_DNDS_FILENAME + "\n")
            fh_out_config.write("INDELIBLE_DNDS_FILENAME=" + INDELIBLE_DNDS_FILENAME + "\n")

        subprocess.check_call(["Rscript", "-e", "library(knitr); " +
                               "setwd('" + R_DIR + "'); " +
                               "spin('umberjack_unit_test.R', knit=FALSE);" +
                               "knit2html('./umberjack_unit_test.Rmd', stylesheet='./markdown_bigwidth.css');"],
                              shell=False, env=os.environ)
        shutil.copy(R_DIR + os.sep + "umberjack_unit_test.html",
                    OUT_DIR + os.sep + "umberjack_unit_test.html")

        concord_csv = OUT_DIR + os.sep + "umberjack_unit_test.concordance.csv"
        shutil.copy(R_DIR + os.sep + "umberjack_unit_test.concordance.csv",
                    concord_csv)
        self._is_good_concordance(concord_csv=concord_csv)


    def test_eval_windows_mpi(self):
        # ART generated reads aligned to population consensus
        SAM_FILENAME = SIM_DATA_DIR + os.sep +  "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".reads.bwa.sort.query.sam"
        OUT_DIR =  SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX  + os.sep + "window{}.breadth{}.depth{}.mpi".format(WINDOW_SIZE, MIN_WINDOW_BREADTH_COV_FRACTION, MIN_WINDOW_DEPTH_COV)
        ACTUAL_DNDS_FILENAME = OUT_DIR + os.sep + os.path.splitext(os.path.basename(SAM_FILENAME))[0] + ".dnds.csv"
        START_NUCPOS = 1
        END_NUCPOS = Utility.get_longest_seq_size_from_fasta(POPN_CONSENSUS_FASTA)


        # Can't call umberjack.eval_windows_mpi() directly since we need to invoke it with mpirun
        subprocess.check_call(["mpirun",
                               "-H", "localhost",  # host
                               "-n", str(WINDOW_PROCS),  # copies of program per node
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
                               "--mode",  "DNDS",
                               "--mpi",
                               "--sam_filename",  SAM_FILENAME,
                               "--ref", REF,
                               "--debug"])


        self.check_concordance(OUT_DIR, ACTUAL_DNDS_FILENAME, EXPECTED_DNDS_FILENAME)


    def test_msa_fasta(self):

        OUT_DIR =  (SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX  + os.sep +
                    "window{}.breadth{}.depth{}.msa_fasta".format(WINDOW_SIZE, MIN_WINDOW_BREADTH_COV_FRACTION, MIN_WINDOW_DEPTH_COV))
        # This is the pseudo msa fasta made from merged reads aligned against consensus using bwa
        MSA_FASTA = SIM_DATA_DIR + os.sep + "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".reads.bwa.msa.fasta"

        ACTUAL_DNDS_FILENAME = (OUT_DIR + os.sep + os.path.splitext(os.path.basename(MSA_FASTA))[0] + os.sep +
                               os.path.splitext(os.path.basename(MSA_FASTA))[0] + ".dnds.csv")
        START_NUCPOS = 1
        END_NUCPOS = Utility.get_longest_seq_size_from_fasta(POPN_CONSENSUS_FASTA)


        if not os.path.exists(OUT_DIR):
            os.makedirs(OUT_DIR)

        # Can't call umberjack.eval_windows_mpi() directly since we need to invoke it with mpirun
        subprocess.check_call(["mpirun",
                               "-H", "localhost",  # host
                               "-n", str(WINDOW_PROCS),  # copies of program per node
                               "-output-filename", OUT_DIR + os.sep + "Test_umberjack.log",  # stdout, stderr logfile

                               "python", UMBERJACK_PY,
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
                               "--mode",  "DNDS",
                               "--mpi",
                               "--msa_fasta",  MSA_FASTA,
                               "--out_dir",  OUT_DIR,
                               "--debug"])

        self.check_concordance(OUT_DIR, ACTUAL_DNDS_FILENAME, EXPECTED_DNDS_FILENAME)



    def test_count_subs(self):
        """
        Tests that umberjack runs properly from commandline.  Also tests no debug option.
        TODO:  make 2 time points and actually check that the rooting and timing works.
        """

        OUT_DIR =   SIM_DIR + os.sep + "out" + os.sep + SIM_DATA_FILENAME_PREFIX + os.sep + "Window" + str(WINDOW_SIZE) + ".checksubs"
        SAM_FILENAME = SIM_DATA_DIR + os.sep +  "aln" + os.sep + SIM_DATA_FILENAME_PREFIX + ".reads.bwa.sort.query.sam"
        OUT_CSV_FILENAME = OUT_DIR + os.sep + 'site_branch_sub.csv'
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
               "--hyphy_exe", HYPHY_EXE,
               "--hyphy_basedir", HYPHY_BASEDIR,
               "--fastree_exe", FASTTREE_EXE,
               "--mode", UmberjackWork.MODE_COUNT_SUBS]
        subprocess.check_call(cmd, env=os.environ)





if __name__ == '__main__':
    settings.setup_logging()
    unittest.main()
