#!/usr/bin/env python
# -*- coding: utf-8 -*-

# #########################################################################
# Copyright (c) 2015, UChicago Argonne, LLC. All rights reserved.         #
#                                                                         #
# Copyright 2015. UChicago Argonne, LLC. This software was produced       #
# under U.S. Government contract DE-AC02-06CH11357 for Argonne National   #
# Laboratory (ANL), which is operated by UChicago Argonne, LLC for the    #
# U.S. Department of Energy. The U.S. Government has rights to use,       #
# reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR    #
# UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR        #
# ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is     #
# modified to produce derivative works, such modified software should     #
# be clearly marked, so as not to confuse it with the version available   #
# from ANL.                                                               #
#                                                                         #
# Additionally, redistribution and use in source and binary forms, with   #
# or without modification, are permitted provided that the following      #
# conditions are met:                                                     #
#                                                                         #
#     * Redistributions of source code must retain the above copyright    #
#       notice, this list of conditions and the following disclaimer.     #
#                                                                         #
#     * Redistributions in binary form must reproduce the above copyright #
#       notice, this list of conditions and the following disclaimer in   #
#       the documentation and/or other materials provided with the        #
#       distribution.                                                     #
#                                                                         #
#     * Neither the name of UChicago Argonne, LLC, Argonne National       #
#       Laboratory, ANL, the U.S. Government, nor the names of its        #
#       contributors may be used to endorse or promote products derived   #
#       from this software without specific prior written permission.     #
#                                                                         #
# THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS     #
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT       #
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS       #
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago     #
# Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,        #
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,    #
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;        #
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER        #
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT      #
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN       #
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         #
# POSSIBILITY OF SUCH DAMAGE.                                             #
# #########################################################################

"""
This application assumes there is a 'config.ini' file that contains parameters required to run the application:

'file' - a file that will be checked for attributes correctness and for data quality
'verification_type' - type of schema the file will be verified against
'schema' - name of a json file that defines mandatory elements in file structure

The application verifies given file according to schema configuration and starts new processes, each process performing specific quality calculations.

The results will be reported in a file (printed on screen for now)

"""

import sys
import h5py
from multiprocessing import Process, Queue
from configobj import ConfigObj

from structureVerifier import verify_structure
from common.qaulityChecks import Data, validate_mean_signal_intensity, validate_signal_intensity_standard_deviation, validate_voxel_based_SNR, validate_slice_based_SNR
from common.utilities import get_data


__author__ = "Barbara Frosik"
__copyright__ = "Copyright (c) 2016, UChicago Argonne, LLC."
__docformat__ = 'restructuredtext en'
__all__ = ['verify_data_quality',
           'cleanup']

config = ConfigObj('config.ini')
processes = {}
results = Queue()
interrupted = False

def verify_data_quality(file, function, process_id):
    """
    This method creates a new process that is associated with the "function" parameter.
    The created process is stored in global "processes" dictionary with the key "process_id" parameter.
    The process is started.
     
    Parameters
    ----------
    file : str
        File Name including path
    
    function : function
        Function that will be executed when process starts.

    process_id : int
        Unique process id assigned by calling method
        
    Returns
    -------
    None        
    """
    p = Process(target=function, args=(file, process_id, results,))
    processes[process_id] = p
    p.start()

def cleanup():
    """
    This method is called at the exit. If any process is still active it will be terminated.
     
    Parameters
    ----------
    None
        
    Returns
    -------
    None        
    """
    for process in processes.itervalues():
        process.terminate()

if __name__ == '__main__':
    """
    This is the main function called when the application starts. 
    It reads the configuration for the file to report on. When the file is found, it is verified for its structure, i.e. whether
    all tags are included, dimenstions are correct, etc. The content to check is configured in config.ini.

    The data in the file is validated by a sequence of validation methods.
    If there is any new result, the result is removed from the queue, corresponding process is terminated, and the result is 
    added to a report.
    
    The loop is interrupted when all expected processes produced results.
    
     
    Parameters
    ----------
    None

    Returns
    -------
    None        
    """
    numberverifiers = 2 # number of verification functions to call for each data file
    numresults = numberverifiers
    process_id = 0
    try:
        file = config['file']
        verify_structure(file)
    except KeyError:
        print ('config error: neither directory or file configured')
        sys.exit(-1)

    data = Data(file, get_data(file))
    process_id = process_id + 1
    verify_data_quality(data, validate_mean_signal_intensity, process_id)
    process_id = process_id + 1
    verify_data_quality(data, validate_signal_intensity_standard_deviation, process_id)

    while not interrupted:
        # checking the result queue and printing result
        # later the result will be passed to an EPICS process variable
        while not results.empty():
            res = results.get()
            pr = processes[res.process_id]
            pr.terminate()
            del processes[res.process_id]
            numresults = numresults -1
            print ('result: file name, result, quality id, error: ', res.file, res.res, res.quality_id, res.error)

        if numresults is 0:
            interrupted = True

    cleanup()

    print ('finished')

