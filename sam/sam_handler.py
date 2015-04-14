"""
Handles sam parsing.
"""
import re
import os
import logging
from sam_constants import SamFlag as SamFlag
from sam_constants import  SamHeader as SamHeader
import single_record
import paired_records
import Utility



NEWICK_NAME_RE = re.compile('[:;\-\(\)\[\]]')


LOGGER = logging.getLogger(__name__)


def __write_seq(fh_out, name, seq, max_prop_N=1.0, breadth_thresh=0.0):
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
        newick_nice_qname = re.sub(pattern=NEWICK_NAME_RE, repl='_', string=name)
        fh_out.write(">" + newick_nice_qname + "\n")
        fh_out.write(seq + "\n")
        return True
    return False


def record_iter(sam_filename, ref, mapping_cutoff, ref_len=0):
    """
    Parse SAM file contents for sequences aligned to a reference.
    Extracts the portion of the read that fits into the desired slice of the genome.
    For paired-end reads, merges the mates into a single sequence with gaps with respect to the reference.
    Creates a multiple sequence alignment (MSA) for the desired slice.
    Left and right pads the reads according to the positions within the slice.
    Writes the MSA sequences to out_fasta_filename.
    Converts query names so that they are compatible with Newick format in phylogenetic reconstruction by
        converting colons, semicolons, parentheses to underscores.

    NB:  Sam file must be query sorted.
    NB:  Only takes the primary alignment.

    :param str sam_filename: full path to sam file.  Must be queryname sorted.
    :param str ref: name of reference contig to form MSA alignments to.
                    If None, then splits out all alignments to any reference that fit within the desired slice positions.
                    Setting the ref to None is only useful when the reads are aligned to a set of multiple sequence aligned
                    reference contigs, and you don't care which reference the read hits, just that it fits in the slice.
    :param int mapping_cutoff:  Ignore alignments with mapping quality lower than the cutoff.
    :param int ref_len: length of reference.  If 0, then takes length from sam headers.
    :returns int:  total sequences written to multiple sequence aligned fasta
    :raises : :py:class:`exceptions.ValueError` if sam file is not queryname sorted according to the sam header
    :return :  yields the next PairedRecord.  Even if there is only a single record, it will be returned as a PairedRecord with an empty mate.
    :rtype: collections.Iterable[sam.paired_records.PairedRecord]
    """
    if not is_query_sort(sam_filename):
        raise ValueError("Sam file must be queryname sorted and header must specify sort order")

    if not ref_len:
        ref_len = get_reflen(sam_filename, ref)

    with open(sam_filename, 'r') as sam_fh:
        prev_mate = None
        for line in sam_fh:
            pair = None
            if line.startswith(SamHeader.TAG_HEADER_PREFIX):  # skip the headers
                continue

            lines_arr = line.rstrip().split('\t')
            if len(lines_arr) < 11:  # in case there are no alignments on this line
                continue

            qname, flag, rname, pos, mapq, cigar, rnext, pnext, tlen, seq, qual = lines_arr[:11]
            mate = single_record.SamRecord(ref_len=ref_len,
                                           qname=qname, flag=flag, rname=rname, seq=seq, cigar=cigar,
                                           mapq=mapq, qual=qual, pos=pos, rnext=rnext, pnext=pnext)

            if not mate.is_mapped(ref) or not mate.is_primary() or mate.is_chimeric():
                continue

            if not prev_mate:  # We are not expecting this mate to be a pair with prev_mate.
                if mate.is_mate_mapped():  # If record is paired, wait till we find its mate
                        prev_mate = mate
                elif mate.mapq >= mapping_cutoff:  #  If this record isn't paired and it passes our thresholds, then just yield it now
                    pair = paired_records.PairedRecord(None, mate)

            else:  # We are expecting this mate to be a pair with prev_mate.
                if not prev_mate.is_mate_mapped(ref):
                    raise ValueError("Invalid logic.  Shouldn't get here. - " +
                                     "Prevmate.qname=" + prev_mate.qname + " flag=" + str(prev_mate.flag) +
                                     " rnext=" + prev_mate.rnext +
                                     " mapq=" + str(prev_mate.mapq) + "\n" +
                                     "LINE=" + line)
                elif prev_mate.qname == mate.qname:
                    if not mate.is_mate_mapped(ref):
                        raise ValueError("Previous mate and this mate have the same qname " + mate.qname +
                                     " but this mate says it doesn't have a mapped mate\n" +
                                     "LINE:" + line)
                    else: # prev_mate and this mate are part of the same pair
                        # Only yield the mates with good map quality
                        if prev_mate.mapq >= mapping_cutoff and mate.mapq >= mapping_cutoff:
                            pair = paired_records.PairedRecord(prev_mate, mate)
                        elif prev_mate.mapq >= mapping_cutoff:
                            pair = paired_records.PairedRecord(prev_mate, None)
                        elif mate.mapq >= mapping_cutoff:
                            pair = paired_records.PairedRecord(None, mate)

                else:  # This sam record does not pair with the previous sam record.
                    LOGGER.warn("Sam record inconsistent.  Expected pair for " + prev_mate.qname + " but got " + qname +
                                ".  If unaligned records are excluded from the samfile, ignore this warning")

                    # Yield previous mate
                    if prev_mate.mapq >= mapping_cutoff:
                        pair = paired_records.PairedRecord(prev_mate, None)

            if not pair:
                if mate.is_mate_mapped():  # Maybe this mate will pair with the next record
                    prev_mate = mate
            else:
                prev_mate = None  # Clear the paired mate expectations for next set of sam records
                yield pair

        # In case the last record expects a mate that is not in the sam file, yield it if it has good map quality
        if prev_mate and prev_mate.mapq >= mapping_cutoff:
            pair = paired_records.PairedRecord(prev_mate, None)
            yield pair


def create_msa_slice_from_sam(sam_filename, ref, out_fasta_filename, mapping_cutoff, read_qual_cutoff, max_prop_N,
                              breadth_thresh, start_pos=0, end_pos=0, do_insert_wrt_ref=False, do_mask_stop_codon=False,
                              ref_len=0):
    """
    Parse SAM file contents for sequences aligned to a reference.
    Extracts the portion of the read that fits into the desired slice of the genome.
    For paired-end reads, merges the mates into a single sequence with gaps with respect to the reference.
    Creates a multiple sequence alignment (MSA) for the desired slice.
    Left and right pads the reads according to the positions within the slice.
    Writes the MSA sequences to out_fasta_filename.
    Converts query names so that they are compatible with Newick format in phylogenetic reconstruction by
        converting colons, semicolons, parentheses to underscores.

    NB:  Sam file must be query sorted.
    NB:  Only takes the primary alignment.

    :param str sam_filename: full path to sam file.  Must be queryname sorted.
    :param str ref: name of reference contig to form MSA alignments to.
                    If None, then splits out all alignments to any reference that fit within the desired slice positions.
                    Setting the ref to None is only useful when the reads are aligned to a set of multiple sequence aligned
                    reference contigs, and you don't care which reference the read hits, just that it fits in the slice.
    :param str out_fasta_filename: full path to output multiple sequence aligned fasta file for the sequences in the slice.
    :param int mapping_cutoff:  Ignore alignments with mapping quality lower than the cutoff.
    :param int read_qual_cutoff: Convert bases with quality lower than this cutoff to N unless both mates agree.
    :param float max_prop_N:  Do not output reads with proportion of N higher than the cutoff.  Only counts the bases within the slice.
                                This only makes a difference if the slice is expected to be much wider than the (merged) read length.
    :param float breadth_thresh:  Fraction of the slice that the read must cover with actual bases A, C, G, T.
                                Reads below this threshold are excluded from output.
    :param int start_pos: 1-based start nucleotide start position of slice.  If 0, then uses beginning of ref.
    :param int end_pos: 1-based end nucleotide start position of slice.  If 0, then uses end of ref.
    :param bool do_insert_wrt_ref: whether to exclude insertions to the reference.
                If include insertions, then the insertions will be multiple sequence aligned further by MAFFT.
    :param bool do_mask_stop_codon: whether to mask stop codons with "NNN".
                Most useful when you want to do codon analysis aftwards, as many codon models do not allow stop codons.
                Assumes that the reference starts at the beginning of a codon.
    :param int ref_len: length of reference.  If 0, then takes length from sam headers.
    :returns int:  total sequences written to multiple sequence aligned fasta
    :raises : :py:class:`exceptions.ValueError` if sam file is not queryname sorted according to the sam header
    """

    LOGGER.debug("About to slice fasta " + out_fasta_filename + " from " + sam_filename)
    if os.path.exists(out_fasta_filename) and os.path.getsize(out_fasta_filename):
        LOGGER.warn("Found existing Sliced MSA-Fasta " + out_fasta_filename + ". Not regenerating.")
        total_seq = Utility.get_total_seq_from_fasta(out_fasta_filename)
        LOGGER.debug("Done slice fasta " + out_fasta_filename)
        return total_seq


    total_written = 0
    with open(out_fasta_filename, 'w') as out_fasta_fh:
        for pair in record_iter(sam_filename=sam_filename, ref=ref, mapping_cutoff=mapping_cutoff, ref_len=ref_len):
            mseq, stats = pair.get_seq_qual(do_pad_wrt_ref=False, do_pad_wrt_slice=True,
                                                   q_cutoff=read_qual_cutoff,
                                                   slice_start_wrt_ref_1based=start_pos,
                                                   slice_end_wrt_ref_1based=end_pos,
                                                   do_insert_wrt_ref=do_insert_wrt_ref,
                                                   do_mask_stop_codon=do_mask_stop_codon)
            is_written = __write_seq(out_fasta_fh, pair.get_name(), mseq, max_prop_N, breadth_thresh)
            total_written += 1 if is_written else 0

    LOGGER.debug("Done slice fasta " + out_fasta_filename)
    return total_written



def is_query_sort(sam_filename):
    """
    :param sam_filename:
    :return: whether the sam is sorted by queryname using the header.  False if header if absent.
    :rtype: boolean
    """
    with open(sam_filename, 'rU') as fh_in:
        header = fh_in.next()  # header should be the first line if present
        header = header.rstrip()
        if not header.startswith(SamHeader.TAG_HEADER_START):
            return False
        tags = header.split(SamHeader.TAG_SEP)
        for tag in tags[1:]:
            key, val = tag.split(SamHeader.TAG_KEY_VAL_SEP)
            if key == SamHeader.TAG_SORT_ORDER_KEY:
                if val == SamHeader.TAG_SORT_ORDER_VAL_QUERYNAME:
                    return True
                else:
                    return False
    return False


def get_reflen(sam_filename, ref):
    """
    Searches sam header for reference length
    :param str sam_filename:  path to sam file
    :param str ref: name of reference
    :return: length of reference or None if not found in the header
    :rtype: int
    """
    with open(sam_filename, 'rU') as fh_in:
        for line in fh_in:
            if not line.startswith(SamHeader.TAG_HEADER_PREFIX):
                return None
            if line.startswith(SamHeader.TAG_REFSEQ_START):
                line = line.rstrip()
                is_found_ref = False
                length = None
                for tag in line.split(SamHeader.TAG_SEP)[1:]:
                    key, val = tag.split(SamHeader.TAG_KEY_VAL_SEP)
                    if key == SamHeader.TAG_REFSEQ_NAME_KEY and val == ref:
                        is_found_ref = True
                    if key == SamHeader.TAG_REFSEQ_LEN_KEY:
                        length = int(val)
                if is_found_ref:
                    return length
    return None
