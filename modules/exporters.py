"""Module exporters.py
data export to files in txt and parquet format and draining of buffers

This module relies on classes in mimocorb.buffer_control
"""

import sys
import os
from mimocorb.buffer_control import rb_toTxtfile, rb_toParquetfile, rbDrain


def drain(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
    rd_to_null = rbDrain(source_list=source_list, config_dict=config_dict, **rb_info)
    rd_to_null()
    # print("\n ** drain: end seen")


def save_to_txt(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
    sv = rb_toTxtfile(source_list=source_list, config_dict=config_dict, **rb_info)
    sv()
    # print("\n ** save_to_txt: end seen")


def save_parquet(source_list=None, sink_list=None, observe_list=None, config_dict=None, **rb_info):
    sv = rb_toParquetfile(source_list=source_list, config_dict=config_dict, **rb_info)
    sv()


if __name__ == "__main__":
    print("Script: " + os.path.basename(sys.argv[0]))
    print("Python: ", sys.version, "\n".ljust(22, "-"))
    print("THIS IS A MODULE AND NOT MEANT FOR STANDALONE EXECUTION")
