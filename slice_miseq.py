import os
import Utility
import csv
import glob
import logging
import fasttree.fasttree_handler as fasttree
import re
import hyphy.hyphy_handler as hyphy_handler

LOGGER = logging.getLogger(__name__)



class SiteDnDsInfo:
    """
    Keeps track of selection information at a codon site.
    """
    def __init__(self):
        self.total_win_cover_site = 0
        self.total_syn_subs = 0
        self.total_nonsyn_subs = 0
        self.total_reads = 0
        self.total_exp_syn_subs = 0
        self.total_exp_nonsyn_subs = 0

        self.total_reads_for_dnds = 0.0
        self.accum_win_dnds_weightby_reads = 0.0
        self.accum_win_n_weightby_reads_nolowsub = 0.0
        self.accum_win_s_weightby_reads_nolowsub = 0.0
        self.accum_win_en_weightby_reads_nolowsub = 0.0
        self.accum_win_es_weightby_reads_nolowsub = 0.0


        self.total_subs_for_dnds = 0.0
        self.accum_win_dnds_weightby_subs = 0.0
        self.total_subs_nolowsub_for_dnds = 0.0
        self.accum_win_dnds_weightby_subs_nolowsub = 0.0

        self.total_reads_for_dnminusds = 0.0
        self.accum_win_dnminusds_weightby_reads = 0.0
        self.total_reads_nolowsub_for_dnminusds = 0.0
        self.accum_win_dn_minus_ds_weightby_reads_nolowsub = 0.0

        self.total_subs_for_dnminusds = 0.0
        self.accum_win_dnminusds_weightby_subs = 0.0
        self.total_subs_nolowsub_for_dnminusds = 0.0
        self.accum_win_dnminusds_weightby_subs_nolowsub = 0.0


    def add_window(self, dnds, dn_minus_ds, reads, syn_subs, nonsyn_subs, exp_syn_subs, exp_nonsyn_subs):
        """
        Insert selection information from a window for the codon site.
        :param float dnds: dN/dS for this codon site from a single window.
        :param float dn_minus_ds: dN-dS/(tree codon length) for this codon site from a single window.
        :param int reads: total reads that contain a valid codon (not - or N's) at this codon site in the window.
        :param float syn_subs: total synonymous substitutions for this codon site in the window
        :param float nonsyn_subs: total nonsynonymous substitutions for this codon site in the window
        :param float exp_syn_subs:  expected number of synonymous substitutions
        :param float exp_nonsyn_subs: expected nonsynomous substitutions
        """
        self.total_win_cover_site += 1
        self.total_reads += reads
        self.total_syn_subs += syn_subs
        self.total_nonsyn_subs += nonsyn_subs
        self.total_exp_syn_subs += exp_syn_subs
        self.total_exp_nonsyn_subs += exp_nonsyn_subs

        if dnds is not None:
            self.total_reads_for_dnds += reads
            self.total_subs_for_dnds += (syn_subs + nonsyn_subs)
            self.accum_win_dnds_weightby_reads += (reads * dnds)
            self.accum_win_dnds_weightby_subs += ((syn_subs + nonsyn_subs) * dnds)

        if dn_minus_ds is not None:
            self.total_reads_for_dnminusds += reads
            self.total_subs_for_dnminusds += (syn_subs + nonsyn_subs)
            self.accum_win_dnminusds_weightby_reads += (reads * dn_minus_ds)
            self.accum_win_dnminusds_weightby_subs += ((syn_subs + nonsyn_subs) * dn_minus_ds)


        # Poor accuracy when site has ambiguous codons and all of its unambiguous codons are fully conserved.
        # Hyphy averages substitutions over ambiguous codons.  If there are no substitutions between unambiguous codons,
        # any fluctation will greatly impact accuracy.
        # However, there are are exactly zero synonymous substitutions and many nonsynonymous substitutions or vice versa,
        # that is still informative.  We might not be able to calculate dN/dS, but we will be able to calculate dN-dS.
        if (syn_subs == 0 or syn_subs >= 1) and (nonsyn_subs == 0 or nonsyn_subs >= 1):
            if dn_minus_ds is not None:
                self.total_reads_nolowsub_for_dnminusds += reads
                self.accum_win_dn_minus_ds_weightby_reads_nolowsub += (reads*dn_minus_ds)

                self.total_subs_nolowsub_for_dnminusds += (syn_subs + nonsyn_subs)
                self.accum_win_dnminusds_weightby_subs_nolowsub += ((syn_subs + nonsyn_subs) * dn_minus_ds)

            if dnds is not None:
                self.accum_win_n_weightby_reads_nolowsub += reads*nonsyn_subs
                self.accum_win_en_weightby_reads_nolowsub += reads*exp_nonsyn_subs
                self.accum_win_s_weightby_reads_nolowsub += reads*syn_subs
                self.accum_win_es_weightby_reads_nolowsub += reads*exp_syn_subs


                self.total_subs_nolowsub_for_dnds += (syn_subs + nonsyn_subs)
                self.accum_win_dnds_weightby_subs_nolowsub += ((syn_subs + nonsyn_subs) * dnds)


    def get_ave_dnds_weightby_subs(self, is_exclude_low_sub=True):
        """
        Return weighted average dN/dS from all windows for the codon site.
        Average weighted by number of observed substitutions for the codon site in the window.
        :param bool is_exclude_low_sub: whether to exclude window-sites that have more than zero but less than 1 synonymous or nonsynonymous substitutions.
                These sites have poor accuracy.
        :rtype : float
        """
        if is_exclude_low_sub:
            if not self.total_subs_nolowsub_for_dnds:
                return None
            return self.accum_win_dnds_weightby_subs_nolowsub / self.total_subs_nolowsub_for_dnds
        else:
            if not self.total_subs_for_dnds:
                return None
            return self.accum_win_dnds_weightby_subs / self.total_subs_for_dnds


    def get_ave_dnds_weightby_reads(self, is_exclude_low_sub=True):
        """
        Return weighted average dN/dS from all windows for the codon site.
        Average weighted by number of reads with unamiguous codons for the codon site in the window.
        :param bool is_exclude_low_sub: whether to exclude window-sites that have more than zero but less than 1 synonymous or nonsynonymous substitutions.
                These sites have poor accuracy.
        :rtype : float
        """
        if is_exclude_low_sub:
            if not self.accum_win_s_weightby_reads_nolowsub or not self.accum_win_en_weightby_reads_nolowsub:
                return None
            return (self.accum_win_n_weightby_reads_nolowsub*self.accum_win_es_weightby_reads_nolowsub)/(self.accum_win_s_weightby_reads_nolowsub*self.accum_win_en_weightby_reads_nolowsub)
        else:
            if not self.total_reads_for_dnds:
                return None
            return self.accum_win_dnds_weightby_reads / self.total_reads_for_dnds


    def get_ave_dn_minus_ds_weightby_reads(self, is_exclude_low_sub=True):
        """
        Return average scaled dN-dS across all windows for the codon site, weighted by reads per window.
        Ignore windows in which there are less than 1 synonymous substitution at the site
        :param bool is_exclude_low_sub: whether to exclude window-sites that have more than zero but less than 1 synonymous or nonsynonymous substitutions.
                These sites have poor accuracy.
        :return float:
        """
        if is_exclude_low_sub:
            if not self.total_reads_nolowsub_for_dnminusds:
                return None
            return self.accum_win_dn_minus_ds_weightby_reads_nolowsub/self.total_reads_nolowsub_for_dnminusds
        else:
            if not self.total_reads_for_dnminusds:
                return None
            return self.accum_win_dnminusds_weightby_reads / self.total_reads_for_dnminusds


    def get_ave_dn_minus_ds_weightby_subs(self, is_exclude_low_sub=True):
        """
        Return average scaled dN-dS across all windows for the codon site, weighted by reads per window.
        Ignore windows in which there are less than 1 synonymous substitution at the site
        :param bool is_exclude_low_sub: whether to exclude window-sites that have more than zero but less than 1 synonymous or nonsynonymous substitutions.
                These sites have poor accuracy.
        :return float:
        """
        if is_exclude_low_sub:
            if not self.total_subs_nolowsub_for_dnminusds:
                return None
            return self.accum_win_dnminusds_weightby_subs_nolowsub/self.total_subs_nolowsub_for_dnminusds
        else:
            if not self.total_subs_for_dnminusds:
                return None
            return self.accum_win_dnminusds_weightby_subs / self.total_subs_for_dnminusds


    def get_window_coverage(self):
        """
        Return total windows that cover this codon site
        :rtype : int
        """
        return self.total_win_cover_site


    def get_ave_read_coverage(self):
        """
        Return average reads that cover this codon site with an unambiguous codon (is not - or Ns) over all windows.
        :rtype : float
        """
        if not self.total_win_cover_site:
            return None
        else:
            return float(self.total_reads)/self.total_win_cover_site

    def get_ave_syn_subs(self):
        """
        Return average synonymous substitutions at this codon site over all windows.
        :rtype : float
        """
        if not self.total_win_cover_site:
            return None
        else:
            return float(self.total_syn_subs)/self.total_win_cover_site

    def get_ave_nonsyn_subs(self):
        """
        Return average nonsynonymous substitutions at this codon site over all windows.
        :rtype : float
        """
        if not self.total_win_cover_site:
            return None
        else:
            return float(self.total_nonsyn_subs)/self.total_win_cover_site

    def get_ave_subs(self):
        """
        Return average substitutions at this codon site over all windows.
        :rtype : float
        """
        if not self.total_win_cover_site:
            return None
        else:
            return float(self.total_nonsyn_subs + self.total_syn_subs)/self.total_win_cover_site




def get_seq_dnds_info(dnds_tsv_dir, ref_codon_len):
    """
    Get dN/dS information from multiple windows for multiple codon sites as a list of SiteDnDsInfo object.
    We expect that all HyPhy has written out dn/ds tsv files for every window with suffix ".<win1basedStart>_<win1basedEnd>.dnds.tsv"

    :return: a list of SiteDnDsInfo objects, each containing the information about selection at a codon site across all windows
    :rtype: [SiteDnDsInfo]
    :param str dnds_tsv_dir:  directory containing sitewise dn/ds tab-separated files generated by HyPhy
    :param  int ref_codon_len: length of reference in codons

    Assumes these are the columns in the HyPhy DN/DS TSV output:
    - Observed S Changes
    - Observed NS Changes
    - E[S Sites]: proportion of random one-nucleotide substitutions that are expected to be synonymous
    - E[NS Sites]: proportion of random one-nucleotide substitutions that are expected to be non-synonymous
    - Observed S. Prop.: observed proportion of synomymous substitutions = Observed S Changes / (Observed S Changes + Observed NS Changes)
    - P{S}:  proportion of substitutions expected to be synonymous under neutral evolution = E[S Sites]/(E[S Sites] + E[NS Sites])
    - dS: observed synonymous substitutions / expected proportion synonymous substitutions = Observed S Changes / E[S Sites]
    - dN: observed non synonymous substitutions / expected proportion nonsynonymous substitutions = Observed NS Changes / E[NS Sites]
    - dN-dS:  difference between dS and dN
    - P{S leq. observed}:  binomial distro pvalue.  Probability of getting less than the observed synonymous substitutions
        under the binomial distribution where probability of 1 synonymous codon = P{S}
    - P{S geq. observed}: binomial distro  pvalue (for the other tail).  Probability of getting more than the observed synonymous substitutions
        under the binomial distribution where probability of 1 synonymous codon = P{S}
    - Scaled dN-dS:  dN-dS normalized by the total length of the tree.
    """
    seq_dnds_info =  [SiteDnDsInfo() for i in range(ref_codon_len)]

    for dnds_tsv_filename in glob.glob(dnds_tsv_dir + os.sep + "*.dnds.tsv"):
        with open(dnds_tsv_filename, 'rU') as dnds_fh:
            # *.{start bp}_{end bp}.dnds.tsv filenames use 1-based nucleotide position numbering
            dnds_tsv_fileprefix = dnds_tsv_filename.split('.dnds.tsv')[0]
            win_nuc_range = dnds_tsv_fileprefix.split('.')[-1]
            # Window starts at this 1-based nucleotide position with respect to the reference
            win_start_nuc_pos_1based_wrt_ref = int(win_nuc_range.split('_')[0])
            # Window starts at this 1-based codon position with respect to the reference
            win_start_codon_1based_wrt_ref = win_start_nuc_pos_1based_wrt_ref/Utility.NUC_PER_CODON + 1

            msa_slice_fasta_filename = dnds_tsv_fileprefix + ".fasta"
            aln = Utility.Consensus()
            aln.parse(msa_fasta_filename=msa_slice_fasta_filename)
            total_codons = aln.get_alignment_len()/Utility.NUC_PER_CODON  # Hyphy drops codons with less than 3 characters

            reader = csv.DictReader(dnds_fh, delimiter='\t')
            offset = 0
            for offset, codon_row in enumerate(reader):    # Every codon site is a row in the *.dnds.tsv file
                dN = float(codon_row[hyphy_handler.HYPHY_TSV_DN_COL])
                dS = float(codon_row[hyphy_handler.HYPHY_TSV_DS_COL])
                dn_minus_ds = float(codon_row[hyphy_handler.HYPHY_TSV_SCALED_DN_MINUS_DS_COL])
                syn_subs = float(codon_row[hyphy_handler.HYPHY_TSV_S_COL])
                nonsyn_subs = float(codon_row[hyphy_handler.HYPHY_TSV_N_COL])
                exp_syn_subs = float(codon_row[hyphy_handler.HYPHY_TSV_EXP_S_COL])
                exp_nonsyn_subs = float(codon_row[hyphy_handler.HYPHY_TSV_EXP_N_COL])
                ref_codon_0based = win_start_codon_1based_wrt_ref + offset - 1
                codons = aln.get_codon_depth(codon_pos_0based=offset, is_count_ambig=False, is_count_gaps=False, is_count_pad=False)

                # TODO:  remove me -- hack to get past bug
                if ref_codon_0based > len(seq_dnds_info):
                    LOGGER.error("Invalid codon - past reference length")
                    break

                if dS == 0:
                    dnds = None
                else:
                    dnds = dN/dS
                seq_dnds_info[ref_codon_0based].add_window(dnds=dnds, dn_minus_ds=dn_minus_ds,
                                            reads=codons, syn_subs=syn_subs, nonsyn_subs=nonsyn_subs,
                                            exp_syn_subs=exp_syn_subs, exp_nonsyn_subs=exp_nonsyn_subs)

            if offset+1 != total_codons:
                raise ValueError("The hyphy output dnds file " + dnds_tsv_filename +
                                 " should have " + str(total_codons) + " codon sites but it only  has" +
                                 str(offset+1))

    return seq_dnds_info




def tabulate_dnds(dnds_tsv_dir, ref, ref_nuc_len, output_csv_filename, comments=""):
    """
    Aggregate selection information from multiple windows for each codon site.
    Output selection information into a tab separated file with the following columns:
    - Ref:  reference name
    - Site:  1-based codon site in the reference
    - Windows:  total windows covering this site
    - Codons: the average reads containing an unambiguous codon at this codon site across windows
    - NonSyn: the average observed nonsynonymous substitutions at this codon site across windows
    - Syn:  the average observed synonymous substitutions at this codon site across windows
    - Subst:  the average observed substitutions at this codon site across windows
    - dndsWeightByReads:  average site dN/dS across windows, weighted window-site depth of unambiguous codons
    - dNdSWeightBySubs:  average site dN/dS across windows, weighted window-site observed substitutions
    - dNdSWeightByReadsNoLowSub:  average site dN/dS across windows, weighted window-site depth of unambiguous codons,
        exclude window-site with nonsynonymous or synonymous substitutions < 1
    - dNdSWeightBySubsNoLowSub:  average site dN/dS across windows, weighted window-site observed substitutions,
        exclude window-site with nonsynonymous or synonymous substitutions < 1
    - dnMinusDsWeightByReads:  average site dN-dS/treelength across windows, weighted window-site depth of unambiguous codons
    - dnMinusDsWeightBySubs:  average site dN-dS/treelength across windows, weighted window-site observed substitutions
    - dnMinusDsWeightByReadsNoLowSubs:  average site dN-dS/treelength across windows, weighted window-site depth of unambiguous codons,
        exclude window-site with nonsynonymous or synonymous substitutions < 1
    - dnMinusDsWeightBySubsNoLowSubs:  average site dN-dS/treelength across windows, weighted window-site observed substitutions,
        exclude window-site with nonsynonymous or synonymous substitutions < 1

    :param str dnds_tsv_dir:  output directory of dN/dS tab separated files generated by HyPhy
    :param str ref: name of reference contig
    :param int ref_nuc_len:  length of reference contig in nucleotides
    :param str output_csv_filename: full filepath of aggregated selection tsv to write to
    :param str comments: any comments to add at the top of the aggregated selection tsv
    """
    LOGGER.debug("Start Ave Dn/DS for all windows for dir=" + dnds_tsv_dir + " ref=" + ref + " " + output_csv_filename)

    seq_dnds_info = get_seq_dnds_info(dnds_tsv_dir=dnds_tsv_dir,
                                      ref_codon_len=ref_nuc_len / Utility.NUC_PER_CODON)


    with open(output_csv_filename, 'w') as dnds_fh:
        dnds_fh.write("# " + comments + "\n")
        writer = csv.DictWriter(dnds_fh,
                                fieldnames=["Ref", "Site", "Windows", "Codons",
                                            "NonSyn", "Syn", "Subs",
                                            "dNdSWeightByReads", "dNdSWeightBySubs",
                                            "dNdSWeightByReadsNoLowSub", "dNdSWeightBySubsNoLowSub",
                                            "dnMinusDsWeightByReads", "dnMinusDsWeightBySubs",
                                            "dnMinusDsWeightByReadsNoLowSubs", "dnMinusDsWeightBySubsNoLowSubs"])

        writer.writeheader()
        for site_0based, site_dnds_info in enumerate(seq_dnds_info):
            outrow = dict()
            outrow["Ref"] = ref
            outrow["Site"] = site_0based + 1
            outrow["Windows"] = site_dnds_info.get_window_coverage()
            outrow["Codons"] = site_dnds_info.get_ave_read_coverage()
            outrow["NonSyn"] = site_dnds_info.get_ave_nonsyn_subs()
            outrow["Syn"] = site_dnds_info.get_ave_syn_subs()
            outrow["Subs"] = site_dnds_info.get_ave_subs()
            outrow["dNdSWeightByReads"] = site_dnds_info.get_ave_dnds_weightby_reads(is_exclude_low_sub=False)
            outrow["dNdSWeightBySubs"] = site_dnds_info.get_ave_dnds_weightby_subs(is_exclude_low_sub=False)
            outrow["dNdSWeightByReadsNoLowSub"] = site_dnds_info.get_ave_dnds_weightby_reads(is_exclude_low_sub=True)
            outrow["dNdSWeightBySubsNoLowSub"] = site_dnds_info.get_ave_dnds_weightby_subs(is_exclude_low_sub=True)
            outrow["dnMinusDsWeightByReads"] = site_dnds_info.get_ave_dn_minus_ds_weightby_reads(is_exclude_low_sub=False)
            outrow["dnMinusDsWeightBySubs"] = site_dnds_info.get_ave_dn_minus_ds_weightby_subs(is_exclude_low_sub=False)
            outrow["dnMinusDsWeightByReadsNoLowSubs"] = site_dnds_info.get_ave_dn_minus_ds_weightby_reads(is_exclude_low_sub=True)
            outrow["dnMinusDsWeightBySubsNoLowSubs"] = site_dnds_info.get_ave_dn_minus_ds_weightby_subs(is_exclude_low_sub=True)
            writer.writerow(outrow)

    LOGGER.debug("Done Ave Dn/DS for all windows  for dir=" + dnds_tsv_dir + " ref=" + ref + ".  Wrote to " + output_csv_filename)



def tabulate_nuc_subst(nucmodelfit_dir, output_csv_filename, comments):
    # Hyphy creates a *.nucmodelfit file that contains the best fit model (according to AIC) with this entry.  Parse it.
    #       Model averaged rates relative to AG (REV estimates):
    #           AC =   0.1902	(  0.1781)
    #           AT =   0.2058	(  0.2198)
    #           CG =   0.0573	(  0.0567)
    #           CT =   1.2453	(  1.2953)
    #           GT =   0.4195	(  0.4246)
    import fnmatch
    # .../out/RunABC/HIV1B-nef/ABC_S89.HIV1B-nef.msa.1_300.nucmodelfit
    with  open(output_csv_filename,'w') as fh_nucmodelcsv:
        fh_nucmodelcsv.write("#" + comments + "\n")
        fh_nucmodelcsv.write("ID,Ref,Window_Start,Window_End,StartBase,EndBase,Mutation,Rate\n")
        for root, dirs, filenames in os.walk(nucmodelfit_dir):
            for nucmodelfit_filename in fnmatch.filter(filenames, '*.nucmodelfit'):

                # ASSUME that multiple sequence aligned file used as input for the nucleotide model fit file is in the same folder
                # TODO:  be more general
                msa_slice_fasta_filename = nucmodelfit_filename.replace(".nucmodelfit", ".fasta")
                #nongap_by_window_pos = Utility.get_total_nongap_nuc_by_pos(msa_fasta_filename=msa_slice_fasta_filename)
                with open(os.path.join(root, nucmodelfit_filename), 'r') as fh_fit:
                    is_found_rates = False
                    # TODO:  make more general
                    sample_id, ref, msa, window, ext = os.path.basename(nucmodelfit_filename).split(".")
                    window_start, window_end = window.split("_")

                    for line in fh_fit:
                        line = line.rstrip().lstrip()
                        if not len(line):
                            continue
                        if not is_found_rates and "Model averaged rates relative to AG" in line:
                            is_found_rates = True
                            continue


                        if is_found_rates:
                            if line.find("Model averaged selection") >= 0:
                                break  # end of rates

                            match = re.findall(r'([ACGT][ACGT])\s*=\s*(\d+\.\d+)\s*\(\s*(\d+\.\d+)\s*\)', line, re.IGNORECASE)
                            if not match:
                                raise ValueError("Line should contain model rates but it doesn't: " + line)
                            subst, sym_rate, nonsym_rate = match[0]  # list of 1 tuple
                            init_base, end_base = list(subst)
                            mutation = init_base + end_base
                            fh_nucmodelcsv.write(",".join(str(x) for x in [sample_id, ref,
                                                                           window_start, window_end,
                                                                           init_base, end_base, mutation, nonsym_rate]) + "\n")


def tabulate_rates(fasttree_output_dir, output_csv_filename, comments=""):
    """
    Collects all the GTR model rates from all the fasttree logs in a directory and puts them into output_csv_filename.
    ASSUME that multiple sequence aligned file is in the same folder
    :param output_dir:
    :return:
    """
    import fnmatch
    LOGGER.debug("Start Tabulate GTR Rates for All Windows For dir " + fasttree_output_dir + " " + output_csv_filename)
    with  open(output_csv_filename,'w') as fh_out:
        fh_out.write("#" + comments + "\n")
        #writer = csv.DictWriter(fh_out, fieldnames=["ID","Ref","Window_Start","Window_End","Window_Reads","Non_Gap_Window_Start","Mutation,Rate"])
        fh_out.write("ID,Ref,Window_Start,Window_End,Window_Reads,Non_Gap_Window_Start,Mutation,Rate\n")
        for root, dirs, filenames in os.walk(fasttree_output_dir):
            for fasttree_log in fnmatch.filter(filenames, '*.fasttree.log'):
                fullpath_fasttree_log = os.path.join(root, fasttree_log)
                AC, AG, AT, CG, CT, GT = fasttree.extract_gtr_rates(fullpath_fasttree_log)
                rates = {"AC":AC, "AG":AG, "AT":AT, "CG":CG, "CT":CT, "GT":GT}

                msa_slice_fasta_filename = fullpath_fasttree_log.replace(".fasttree.log", ".fasta")
                # sample_id.ref.msa.window_start_window_end.fasta
                name_split = os.path.basename(msa_slice_fasta_filename).split(".")
                window = name_split[-2]
                ref = name_split[-4]  # TODO:  what if reference has . in it?
                sample_id = ".".join(name_split[0:-4])
                window_start, window_end = window.split("_")
                nongap_window_start = Utility.get_total_nongap_nuc_by_pos(msa_slice_fasta_filename, 0)
                reads = Utility.get_total_seq_from_fasta(msa_slice_fasta_filename)


                for mutation, rate in rates.iteritems():
                    fh_out.write(",".join([sample_id,
                                  ref,
                                  window_start,
                                  window_end,
                                  str(reads),
                                  str(nongap_window_start),
                                  mutation,
                                  str(rate)]) + "\n")
    LOGGER.debug("Done Tabulate GTR Rates for all windows for dir " + fasttree_output_dir + " " + output_csv_filename)


def write_seq(fh_out, name, seq, max_prop_N=1.0, breadth_thresh=0.0):
    """
    Helper function to write out sequence to fasta file handle if has sufficient bases.
    Renames the sequence name so that it is newick compatible.
    :param FileIO fh_out:  python file handle
    :param str name: Sequence Name
    :param str seq:  Sequence
    :param float max_prop_N: maximum fraction allowed N.  Doesn't care about gaps.
            Setting this to less than 1 only makes sense when a read has not been sliced prior to passing into this function,
            since the fraction of N's is only calculated on the sequence passed in.
    :param float breadth_thresh:  minimum fraction of true bases (ACGT) required.  Only calculated on the sequence passed in.
    :return bool:  True if sequence written out
    """

    if seq.count('N') / float(len(seq)) <= max_prop_N and (seq.count("N") + seq.count("-"))/float(len(seq)) <= (1.0-breadth_thresh):
        # Newick tree formats don't like special characters.  Convert them to underscores.
        newick_nice_qname = Utility.newick_nice_name(name)
        fh_out.write(">" + newick_nice_qname + "\n")
        fh_out.write(seq + "\n")
        return True
    return False


def create_slice_msa_fasta(fasta_filename, out_fasta_filename, start_pos, end_pos, max_prop_N=1.0, breadth_thresh=0.0, do_mask_stop_codon=False):
    """
    From a fasta file of multiple sequence alignments, extract the sequence sequence from desired region.
    If the sequence is shorter than <end_pos>, then fills in the gaps with '-' characters so that it ends at <end_pos>

    Only puts in the read into the sliced msa fasta if it obeys the window constraints.

    :rtype int: total sequences written
    :param str fasta_filename: full file path to fasta of multiple sequence alignments
    :param str out_fasta_filename:  full file path to output fasta of sliced multiple sequence alignments
    :param int start_pos : 1-based start position of region to extract
    :param int end_pos: 1-based end position of region to extract
    :param float max_prop_N:  proportion of bases in sequences that can be N within the start_pos and end_pos inclusive
    :param float breadth_thresh: fraction of sequence that be A,C,T,or G within start_pos and end_pos inclusive.
    :param bool do_mask_stop_codon:  whether or not to mask stop codons in the slices with "NNN"
    """

    total_seq = 0
    if os.path.exists(out_fasta_filename) and os.path.getsize(out_fasta_filename):
        total_seq = Utility.get_total_seq_from_fasta(out_fasta_filename)
        LOGGER.warn("Found existing Sliced MSA-Fasta " + out_fasta_filename + ". Not regenerating.")

    else:
        with open(fasta_filename, 'r') as fasta_fh, open(out_fasta_filename, 'w') as slice_fasta_fh:
            header = ""
            seq = ""
            for line in fasta_fh:
                line = line.rstrip()
                if line:
                    line = line.split()[0]  # remove trailing whitespace and any test after the first whitespace

                    if line[0] == '>':  # previous sequence is finished.  Write out previous sequence
                        if header and seq:
                            if do_mask_stop_codon:
                                seq = Utility.mask_stop_codon(seq)

                            written = write_seq(slice_fasta_fh, name=header, seq=seq[start_pos-1:end_pos], max_prop_N=max_prop_N, breadth_thresh=breadth_thresh)
                            if written:
                                total_seq += 1
                        seq = ""
                        header = line[1:]

                    else:   # cache current sequence so that entire sequence is on one line
                        seq += line

            if do_mask_stop_codon:
                seq = Utility.mask_stop_codon(seq)

            written = write_seq(slice_fasta_fh, name=header, seq=seq[start_pos-1:end_pos], max_prop_N=max_prop_N, breadth_thresh=breadth_thresh)
            if written:
                total_seq += 1
        LOGGER.debug("Done slice fasta " + out_fasta_filename)

    return total_seq
