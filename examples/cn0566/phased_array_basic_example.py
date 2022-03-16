#!/usr/bin/env python3
#  Must use Python 3
# Copyright (C) 2022 Analog Devices, Inc.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#     - Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     - Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in
#       the documentation and/or other materials provided with the
#       distribution.
#     - Neither the name of Analog Devices, Inc. nor the names of its
#       contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#     - The use of this software may or may not infringe the patent rights
#       of one or more patent holders.  This license does not release you
#       from the requirement that you obtain separate licenses from these
#       patent holders to use this software.
#     - Use of the software either in source or binary form, must be run
#       on or directly connected to an Analog Devices Inc. component.
#
# THIS SOFTWARE IS PROVIDED BY ANALOG DEVICES "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, NON-INFRINGEMENT, MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED.
#
# IN NO EVENT SHALL ANALOG DEVICES BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, INTELLECTUAL PROPERTY
# RIGHTS, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
# THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Basic utility script for working with the CN0566 "Phaser" board. Accepts the following
command line arguments:

plot - plot beam pattern, rectangular element weighting. If cal files are present,
       they will be loaded.

cal - perform both gain and phase calibration, save to files.
"""

import matplotlib.pyplot as plt
import numpy as np
import os
from scipy import signal
import sys
import time
""" This is the CN0566 directory and files created inside it. For now sdr pll and beamformer class are inside 
    3 different python files and CN0566 directory has it's own __init__.py file. Later merge them to single or change
    according to pyadi requirements."""

if os.name == 'nt': # Assume running on Windows
    print("Running on Windows, connecting to phaser.local and pluto.local...")
    rpi_ip = "ip:phaser.local"  # IP address of the remote Raspberry Pi
#     rpi_ip = "ip:169.254.225.48" # Hard code an IP here
    sdr_ip = "ip:pluto.local" # Pluto IP, with modified IP address or not
elif os.name == 'posix':
    print("Running on Linux, assuming I'm on the Pi itself...")
    rpi_ip = "ip:localhost"  # Assume running locally on Raspberry Pi
    sdr_ip = "ip:192.168.2.1"  # Historical - assume default Pluto IP
else:
    print("Can't detect OS")

try:
    x = my_sdr.uri
    print("Pluto already connected")
except NameError:
    print("Pluto not connected, connecting...")
    from adi import ad9361
    my_sdr = ad9361(uri=sdr_ip)

time.sleep(0.5)

try:
    x = my_cn0566.uri
    print("cn0566 already connected")
except NameError:
    print("cn0566 not connected, connecting...")
    from adi.cn0566 import CN0566
    my_cn0566 = CN0566(uri=rpi_ip, rx_dev=my_sdr)
    
    
""" Configure SDR parameters.
    Current freq plan is Sig Freq = 10.492 GHz, antenna element spacing = 0.015m, Freq of pll is 12/2 GHz
    this is mixed down using mixer to get 10.492 - 6 = 4.492GHz which is freq of sdr.
    This frequency plan can be updated any time in example code
    e.g:- my_cn0566.frequency = 9000000000 etc"""
# configure sdr/pluto according to above-mentioned freq plan
# my_sdr._ctrl.debug_attrs["adi,frequency-division-duplex-mode-enable"].value = "1"
# my_sdr._ctrl.debug_attrs["adi,ensm-enable-txnrx-control-enable"].value = "0"  # Disable pin control so spi can move the states
# my_sdr._ctrl.debug_attrs["initialize"].value = "1"
my_sdr.rx_enabled_channels = [0, 1]  # enable Rx1 (voltage0) and Rx2 (voltage1)
my_sdr.gain_control_mode_chan1 = 'manual'  # We must be in manual gain control mode (otherwise we won't see
my_sdr.rx_hardwaregain_chan1 = 20
my_sdr._rxadc.set_kernel_buffers_count(1) # Super important - don't want to have to flush stale buffers
rx = my_sdr._ctrl.find_channel('voltage0')
rx.attrs['quadrature_tracking_en'].value = '1'  # set to '1' to enable quadrature tracking
my_sdr.sample_rate = int(30000000)  # Sampling rate
my_sdr.rx_buffer_size = int(4 * 256)
my_sdr.rx_rf_bandwidth = int(10e6)
# We must be in manual gain control mode (otherwise we won't see the peaks and nulls!)
my_sdr.gain_control_mode_chan0 = 'manual'
my_sdr.gain_control_mode_chan1 = 'manual'
my_sdr.rx_hardwaregain_chan0 = 20
my_sdr.rx_hardwaregain_chan1 = 20

my_sdr.rx_lo = int(2.2e9)  # 4495000000  # Recieve Freq
my_sdr.tx_lo = int(2.2e9)

my_sdr.filter="LTE20_MHz.ftr"  # MWT: Using this for now, may not be necessary.
rx_buffer_size = int(4 * 256)
my_sdr.rx_buffer_size = rx_buffer_size

my_sdr.tx_cyclic_buffer = True
my_sdr.tx_buffer_size = int(2**16)

my_sdr.tx_hardwaregain_chan0 = int(-6) # this is a negative number between 0 and -88
my_sdr.tx_hardwaregain_chan1 = int(-6) # Make sure the Tx channels are attenuated (or off) and their freq is far away from Rx

#my_sdr.dds_enabled = [1, 1, 1, 1] #DDS generator enable state
#my_sdr.dds_frequencies = [0.1e6, 0.1e6, 0.1e6, 0.1e6] #Frequencies of DDSs in Hz
#my_sdr.dds_scales = [1, 1, 0, 0] #Scale of DDS signal generators Ranges [0,1]
my_sdr.dds_single_tone(int(2e6), 0.9, 1) # sdr.dds_single_tone(tone_freq_hz, tone_scale_0to1, tx_channel)

""" Configure CN0566 parameters.
    ADF4159 and ADAR1000 array attributes are exposed directly, although normally
    accessed through other methods."""

# By default device_mode is "rx"
my_cn0566.configure(device_mode="rx")  # Configure adar in mentioned mode and also sets gain of all channel to 127

# HB100 measured frequency - 10492000000

# my_cn0566.SignalFreq = 10600000000 # Make this automatic in the future.
my_cn0566.SignalFreq = 10.497e9

# my_cn0566.frequency = (10492000000 + 2000000000) // 4 #6247500000//2

# Onboard source w/ external Vivaldi
my_cn0566.frequency = (int(my_cn0566.SignalFreq) + my_sdr.rx_lo) // 4 # PLL feedback via /4 VCO output
my_cn0566.freq_dev_step = 5690
my_cn0566.freq_dev_range = 0
my_cn0566.freq_dev_time = 0
my_cn0566.powerdown = 0
my_cn0566.ramp_mode = "disabled"

""" If you want to use previously calibrated values load_gain and load_phase values by passing path of previously
    stored values. If this is not done system will be working as uncalibrated system.
    These will fail gracefully and default to no calibration if files not present."""

my_cn0566.load_gain_cal('gain_cal_val.pkl')
my_cn0566.load_phase_cal('phase_cal_val.pkl')

""" This can be useful in Array size vs beam width experiment or beamtappering experiment. 
    Set the gain of outer channels to 0 and beam width will increase and so on."""
#my_beamformer.set_chan_gain(3, 120)  # set gain of Individual channel
#my_beamformer.set_all_gain(120)  # Set all gain to mentioned value, if not, set to 127 i.e. max gain

""" To set gain of all channels with different values.
    Here's where you would apply a window / taper function,
    but we're starting with rectangular / SINC1."""

gain_list = [127, 127, 127, 127, 127, 127, 127, 127]
for i in range(0, len(gain_list)):
    my_cn0566.set_chan_gain(i, gain_list[i], apply_cal=True)

""" Averages decide number of time samples are taken to plot and/or calibrate system. By default it is 1."""
my_cn0566.Averages = 8

""" This instantiate calibration routine and perform gain and phase calibration. Note gain calibration should be always
    done 1st as phase calibration depends on gain cal values if not it throws error"""
# print("Calibrating Gain...")
# my_cn0566.gain_calibration()   # Start Gain Calibration
# print("Calibrating Phase...")
# my_cn0566.phase_calibration()  # Start Phase Calibration
# print("Done calibration")

""" This can be used to change the angle of center lobe i.e if we want to concentrate main lobe/beam at 45 degress"""
# my_beamformer.set_beam_angle(45)


# Really basic options - "plot" to plot continuously, "cal" to calibrate both gain and phase.
func = sys.argv[1] if len(sys.argv) >= 2 else "plot"

if func == "cal":
    input("Calibrating gain and phase - place antenna at mechanical boresight in front\
          of the aryay, then press enter...")
    print("Calibrating Gain, verbosely, then saving cal file...")
    my_cn0566.gain_calibration(verbose = True)   # Start Gain Calibration
    my_cn0566.save_gain_cal() # Default filename
    print("Calibrating Phase, verbosely, then saving cal file...")
    my_cn0566.phase_calibration(verbose = True)  # Start Phase Calibration
    my_cn0566.save_phase_cal() # Default filename
    print("Done calibration")

if func == "plot":
    do_plot = True
else:
    do_plot = False

while do_plot == True:
    try:
        start=time.time()
        my_cn0566.set_beam_phase_diff(0.0)
        time.sleep(0.25)
        data = my_sdr.rx()
        data = my_sdr.rx()
        ch0 = data[0]
        ch1 = data[1]
        f, Pxx_den0 = signal.periodogram(ch0[1:-1], 30000000, 'blackman', scaling='spectrum')
        f, Pxx_den1 = signal.periodogram(ch1[1:-1], 30000000, 'blackman', scaling='spectrum')
        
        plt.figure(1)
        plt.clf()
        plt.plot(np.real(ch0), color='red')
        plt.plot(np.imag(ch0), color='blue')
        plt.plot(np.real(ch1), color='green')
        plt.plot(np.imag(ch1), color='black')
        np.real
        plt.xlabel("data point")
        plt.ylabel("output code")
        plt.draw()
        
        plt.figure(2)
        plt.clf()
        plt.semilogy(f, Pxx_den0)
        plt.semilogy(f, Pxx_den1)
        plt.ylim([1e-5, 1e6])
        plt.xlabel("frequency [Hz]")
        plt.ylabel("PSD [V**2/Hz]")
        plt.draw()
        
        """ Plot the output based on experiment that you are performing"""
        print("Plotting...")
        
    
        plt.figure(3)
        plt.ion()
    #    plt.show()
        gain, angle, delta, diff_error, beam_phase, xf, max_gain, PhaseValues = my_cn0566.calculate_plot()
        print("Sweeping took this many seconds: " + str(time.time()-start))
    #    gain,  = my_cn0566.plot(plot_type="monopulse")
        plt.clf()
        plt.scatter(angle, gain, s=10)
        plt.scatter(angle, delta, s=10)
        plt.show()
        
        
        plt.pause(0.05)
        time.sleep(0.05)
        print("Total took this many seconds: " + str(time.time()-start))
    except KeyboardInterrupt:
        do_plot = False
        print("Exiting Loop")