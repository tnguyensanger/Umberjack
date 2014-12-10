import re
import logging
import sys
import sam_constants

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] [%(name)s] [%(process)d] %(message)s')
console_handler.setFormatter(formatter)
LOGGER.addHandler(console_handler)





class SamRecord:


    def __init__(self, ref_len):
        self.ref_len = ref_len
        self.qname = None
        self.flag = None
        self.seq = None
        self.cigar = None
        self.mapq = None
        self.qual = None
        self.pos = None
        self.mate_record = None
        self.nopad_noinsert_seq = None
        self.nopad_noinsert_qual = None
        self.ref_pos_to_insert_seq_qual = None
        self.seq_end_wrt_ref = None
        self.ref_align_len = 0  # includes deletions wrt reference.  Excludes insertions wrt reference
        self.seq_align_len = 0  # includes insertions wrt reference.  Excludes deletions wrt reference

    def is_empty(self):
        return not self.qname and not self.seq

    def fill_record(self, sam_row_dict):
        self.qname = sam_row_dict["qname"]
        self.flag = int(sam_row_dict["flag"])
        self.seq = sam_row_dict["seq"]
        self.cigar = sam_row_dict["cigar"]
        self.mapq = int(sam_row_dict["mapq"])
        self.qual = sam_row_dict["qual"]
        self.pos = int(sam_row_dict["pos"])
        self.mate_record = None

    def fill_mate(self, mate_record):
        self.mate_record = mate_record
        if not mate_record.mate_record:
            mate_record = self


    def get_seq_qual(self, do_pad_wrt_ref=False, do_pad_wrt_slice=False, do_mask_low_qual=False, q_cutoff=10,
                     slice_start_wrt_ref_1based=None, slice_end_wrt_ref_1based=None, do_insert_wrt_ref=False):
        """
        Gets the sequence for the sam record.
        :param do_pad_wrt_slice: Ignored if do_pad_wrt_ref=True.  If True, then pads with gaps with respect to the slice.
        :param bool do_pad_wrt_ref: Pad sequence with gaps with respect to the reference.
                        If slice_start_wrt_ref and slice_end_wrt_ref are valid, then pads the slice with respect to the reference.
        :param bool do_insert_wrt_ref: Include insertions with respect to the reference.
                        If slice_start_wrt_ref and slice_end_wrt_ref are valid, then only includes inserts inside the slice.
        :param bool do_mask_low_qual: Mask bases with quality < q_cutoff with "N"
        :param int q_cutoff:  quality cutoff
        :param int slice_start_wrt_ref_1based:  If None, then whole sequence returned.   Otherwise, the slice 1-based start position with respect to the reference.
        :param int slice_end_wrt_ref_1based:  If None, then whole sequence returned.  Otherwise the slice end 1-based position with respect to the reference.
        :return tuple (str, str):  (sequence, quality)
        """
        # NB:  the original seq from sam file includes softclips.  Remove them with apply_cigar()
        if not self.nopad_noinsert_seq or not self.nopad_noinsert_qual:
            self.__parse_cigar()

        if slice_start_wrt_ref_1based and slice_end_wrt_ref_1based and slice_start_wrt_ref_1based > slice_end_wrt_ref_1based:
            raise ValueError("slice start must be <= slice end")
        elif (not slice_start_wrt_ref_1based and slice_end_wrt_ref_1based) or (slice_start_wrt_ref_1based and not slice_end_wrt_ref_1based):
            raise  ValueError("Either define both slice start and end or don't define either")

        result_seq = self.nopad_noinsert_seq
        result_qual = self.nopad_noinsert_qual

        # Slice

        # Does slice start after the sequence ends or does the slice end before the sequence starts?
        # Then just return empty string or padded gaps wrt ref or slice as desired.
        if ((slice_start_wrt_ref_1based and slice_start_wrt_ref_1based > self.get_seq_end_wrt_ref()) or
                (slice_end_wrt_ref_1based and slice_end_wrt_ref_1based < self.get_seq_start_wrt_ref())):

            if do_pad_wrt_ref:
                result_seq = sam_constants.SEQ_PAD_CHAR * self.ref_len
                result_qual = sam_constants.QUAL_PAD_CHAR * self.ref_len
            elif do_pad_wrt_slice:
                slice_len = slice_end_wrt_ref_1based - slice_start_wrt_ref_1based + 1
                result_seq = sam_constants.SEQ_PAD_CHAR * slice_len
                result_qual = sam_constants.QUAL_PAD_CHAR * slice_len
            return result_seq, result_qual

        # The sequence overlaps the slice.
        # Modify the slice start so that it starts at or after the sequence start.
        if not slice_start_wrt_ref_1based:
            slice_start_wrt_ref_1based = 1
        if not slice_end_wrt_ref_1based:
            slice_end_wrt_ref_1based = self.ref_len

        # 0-based start position of slice wrt result_seq
        slice_start_wrt_result_seq_0based = max(self.get_seq_start_wrt_ref(), slice_start_wrt_ref_1based) - self.get_seq_start_wrt_ref()
        # 0-based end position of slice wrt result_seq
        slice_end_wrt_result_seq_0based = self.get_ref_align_len() - 1 - (self.get_seq_end_wrt_ref() - min(self.get_seq_end_wrt_ref(), slice_end_wrt_ref_1based))
        result_seq = result_seq[slice_start_wrt_result_seq_0based:slice_end_wrt_result_seq_0based+1]
        result_qual = result_qual[slice_start_wrt_result_seq_0based:slice_end_wrt_result_seq_0based+1]

        # Mask
        if do_mask_low_qual:
            masked_seq = ""
            for i, base in enumerate(result_seq):
                base_qual = ord(result_qual[i])-sam_constants.PHRED_SANGER_OFFSET
                if base != sam_constants.SEQ_PAD_CHAR and base_qual < q_cutoff:
                    masked_seq += "N"
                else:
                    masked_seq += base
            result_seq = masked_seq

        # Add Insertions
        if do_insert_wrt_ref:
            total_inserts = 0
            total_insert_1mate_only_lowqual = 0
            result_seq_with_inserts = ""
            result_qual_with_inserts = ""
            last_insert_pos_0based_wrt_result_seq = -1  # 0-based position wrt result_seq before the previous insertion
            # insert_pos_wrt_ref: 1-based reference position before the insertion
            for insert_1based_pos_wrt_ref, (insert_seq, insert_qual) in self.ref_pos_to_insert_seq_qual.iteritems():
                if slice_start_wrt_ref_1based <= insert_1based_pos_wrt_ref < slice_end_wrt_ref_1based:
                    total_inserts += 1
                    # insert_pos_0based_wrt_result_seq:  0-based position wrt result_seq right before the insertion
                    insert_pos_0based_wrt_result_seq =  insert_1based_pos_wrt_ref - max(self.get_seq_start_wrt_ref(), slice_start_wrt_ref_1based)

                    if do_mask_low_qual:
                        masked_insert_seq = ""
                        is_low_qual = False
                        for i, ichar in enumerate(insert_seq):
                            iqual = ord(insert_qual[i])-sam_constants.PHRED_SANGER_OFFSET
                            if iqual >= q_cutoff:  # Only include inserts with high quality
                                masked_insert_seq += ichar
                            else:
                                is_low_qual = True
                        if is_low_qual:
                            total_insert_1mate_only_lowqual += 1
                    else:
                        masked_insert_seq = insert_seq

                    result_seq_with_inserts += result_seq[last_insert_pos_0based_wrt_result_seq+1:insert_pos_0based_wrt_result_seq+1] + masked_insert_seq
                    result_qual_with_inserts += result_qual[last_insert_pos_0based_wrt_result_seq+1:insert_pos_0based_wrt_result_seq+1] + insert_qual
                    last_insert_pos_0based_wrt_result_seq = insert_pos_0based_wrt_result_seq

            # TODO:  assume that bowtie will not let inserts at beginning/end of align, but check
            result_seq_with_inserts += result_seq[last_insert_pos_0based_wrt_result_seq+1:len(result_seq)]
            result_qual_with_inserts += result_qual[last_insert_pos_0based_wrt_result_seq+1:len(result_qual)]

            if total_inserts:
                LOGGER.debug("qname=" + self.qname + " total_insert_1mate_only=" + str(total_inserts) +
                             " total_insert_1mate_only_lowqual=" + str(total_insert_1mate_only_lowqual) +
                             " total_nonconflict_inserts=0" +
                             " total_conflict_inserts=0" +
                             " total_inserts=" + str(total_inserts))
            result_seq = result_seq_with_inserts
            result_qual = result_qual_with_inserts



        # Pad
        if do_pad_wrt_ref:
            left_pad_len = max(slice_start_wrt_ref_1based, self.get_seq_start_wrt_ref())  - 1
            right_pad_len = self.ref_len - min(self.get_seq_end_wrt_ref(), slice_end_wrt_ref_1based)
            padded_seq = (sam_constants.SEQ_PAD_CHAR * left_pad_len) + result_seq + (sam_constants.SEQ_PAD_CHAR * right_pad_len)
            padded_qual = (sam_constants.QUAL_PAD_CHAR * left_pad_len) + result_qual + (sam_constants.QUAL_PAD_CHAR * right_pad_len)

            result_seq = padded_seq
            result_qual = padded_qual
        elif do_pad_wrt_slice:
            left_pad_len = max(slice_start_wrt_ref_1based, self.get_seq_start_wrt_ref())  - slice_start_wrt_ref_1based
            right_pad_len = slice_end_wrt_ref_1based - min(self.get_seq_end_wrt_ref(), slice_end_wrt_ref_1based)
            padded_seq = (sam_constants.SEQ_PAD_CHAR * left_pad_len) + result_seq + (sam_constants.SEQ_PAD_CHAR * right_pad_len)
            padded_qual = (sam_constants.QUAL_PAD_CHAR * left_pad_len) + result_qual + (sam_constants.QUAL_PAD_CHAR * right_pad_len)

            result_seq = padded_seq
            result_qual = padded_qual


        return result_seq, result_qual


    def get_insert_dict(self):
        if not self.ref_pos_to_insert_seq_qual:
            self.__parse_cigar()
        return self.ref_pos_to_insert_seq_qual



    def get_seq_start_wrt_ref(self):
        """
        Gets the 1-based start position with respect to the reference of the unclipped portion of the sequence.
        :return:
        """
        return self.pos


    def get_seq_end_wrt_ref(self):
        """
        Gets the 1-based end position with respect to the reference of the unclipped portion of the sequence.
        :return:
        """
        if not self.seq_end_wrt_ref:
            self.seq_end_wrt_ref =  self.pos + self.get_ref_align_len() - 1
        return self.seq_end_wrt_ref


    def __parse_cigar(self):
        self.nopad_noinsert_seq = ''
        self.nopad_noinsert_qual = ''
        self.ref_pos_to_insert_seq_qual = {}
        self.ref_align_len = 0
        self.seq_align_len = 0
        tokens = sam_constants.CIGAR_RE.findall(self.cigar)

        pos_wrt_seq_0based = 0  # position with respect to sequence, 0based
        pos_wrt_ref_1based = self.pos  # position with respect to reference, 1based
        for token in tokens:
            length = int(token[:-1])
            # Matching sequence: carry it over
            if token[-1] == 'M' or token[-1] == 'X' or token[-1] == '=':
                self.nopad_noinsert_seq += self.seq[pos_wrt_seq_0based:(pos_wrt_seq_0based+length)]
                self.nopad_noinsert_qual += self.qual[pos_wrt_seq_0based:(pos_wrt_seq_0based+length)]
                pos_wrt_seq_0based += length
                pos_wrt_ref_1based += length
                self.ref_align_len += length
                self.seq_align_len += length
            # Deletion relative to reference: pad with gaps
            elif token[-1] == 'D' or token[-1] == 'P' or token[-1] == 'N':
                self.nopad_noinsert_seq += sam_constants.SEQ_PAD_CHAR*length
                self.nopad_noinsert_qual += sam_constants.QUAL_PAD_CHAR*length  # Assign fake placeholder score (Q=-1)
                self.ref_align_len += length
            # Insertion relative to reference: skip it (excise it)
            elif token[-1] == 'I':
                self.ref_pos_to_insert_seq_qual.update({pos_wrt_ref_1based-1:
                                                            (self.seq[pos_wrt_seq_0based:(pos_wrt_seq_0based+length)],
                                                             self.qual[pos_wrt_seq_0based:(pos_wrt_seq_0based+length)])})
                pos_wrt_seq_0based += length
                self.seq_align_len += length
            # Soft clipping leaves the sequence in the SAM - so we should skip it
            elif token[-1] == 'S':
                pos_wrt_seq_0based += length
            else:
                raise ValueError("Unable to handle CIGAR token: {} - quitting".format(token))
                sys.exit()


    def get_ref_align_len(self):
        """
        Returns the length of the alignment with respect to the reference.
        Each inserted base with respect to the reference counts as 0.  Each deleted base with respect to the reference counts as 1.
        :return:
        """
        if not self.ref_align_len:
            self.__parse_cigar()
        return self.ref_align_len


    def get_seq_align_len(self):
        """
        Returns the length of the alignment with respect to the read.
        Each deleted base with respect to the reference counts as 0.  Each inserted base with respect to the reference counts as 1.
        :return:
        """
        if not self.seq_align_len:
            self.__parse_cigar()
        return self.seq_align_len
