# Copyright (C) 2020 Analog Devices, Inc.
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

from typing import Dict, List

from adi.context_manager import context_manager
from adi.rx_tx import rx_tx


def _map_to_dict(paths, ch):
    fddc, cddc, adc = ch.attrs["label"].value.split("->")
    if adc not in paths.keys():
        paths[adc] = {}
    if cddc not in paths[adc].keys():
        paths[adc][cddc] = {}
    if fddc not in paths[adc][cddc].keys():
        paths[adc][cddc][fddc] = {"channels": [ch._id]}
    else:
        paths[adc][cddc][fddc]["channels"].append(ch._id)
    return paths


def _sortconv(chans_names, noq=False, dds=False):
    tmpI = filter(lambda k: "_i" in k, chans_names)
    tmpQ = filter(lambda k: "_q" in k, chans_names)

    def ignoreadc(w):
        return int(w[len("voltage") : w.find("_")])

    def ignorealt(w):
        return int(w[len("altvoltage") :])

    chans_names_out = []
    if dds:
        filt = ignorealt
        tmpI = chans_names
        noq = True
    else:
        filt = ignoreadc

    tmpI = sorted(tmpI, key=filt)
    tmpQ = sorted(tmpQ, key=filt)
    for i in range(len(tmpI)):
        chans_names_out.append(tmpI[i])
        if not noq:
            chans_names_out.append(tmpQ[i])

    return chans_names_out


class ad9081(rx_tx, context_manager):
    """ AD9081 Mixed-Signal Front End (MxFE) """

    _complex_data = True
    _rx_channel_names: List[str] = []
    _tx_channel_names: List[str] = []
    _tx_control_channel_names: List[str] = []
    _rx_coarse_ddc_channel_names: List[str] = []
    _tx_coarse_duc_channel_names: List[str] = []
    _rx_fine_ddc_channel_names: List[str] = []
    _tx_fine_duc_channel_names: List[str] = []
    _dds_channel_names: List[str] = []
    _device_name = ""

    _rx_attr_only_channel_names: List[str] = []
    _tx_attr_only_channel_names: List[str] = []

    _path_map: Dict[str, Dict[str, Dict[str, List[str]]]] = {}

    def __init__(self, uri=""):

        context_manager.__init__(self, uri, self._device_name)
        # Default device for attribute writes
        self._ctrl = self._ctx.find_device("axi-ad9081-rx-hpc")
        # Devices with buffers
        self._rxadc = self._ctx.find_device("axi-ad9081-rx-hpc")
        self._txdac = self._ctx.find_device("axi-ad9081-tx-hpc")

        # Get DDC and DUC mappings
        paths = {}

        for ch in self._rxadc.channels:
            if "label" in ch.attrs:
                paths = _map_to_dict(paths, ch)
        self._path_map = paths

        # Get data + DDS channels
        for ch in self._rxadc.channels:
            if ch.scan_element and not ch.output:
                self._rx_channel_names.append(ch._id)
        for ch in self._txdac.channels:
            if ch.scan_element:
                self._tx_channel_names.append(ch._id)
            else:
                self._dds_channel_names.append(ch._id)

        # Sort channel names
        self._rx_channel_names = _sortconv(self._rx_channel_names)
        self._tx_channel_names = _sortconv(self._tx_channel_names)
        self._dds_channel_names = _sortconv(self._dds_channel_names, dds=True)

        # Map unique attributes to channel properties
        self._rx_fine_ddc_channel_names = []
        self._rx_coarse_ddc_channel_names = []
        for converter in paths:
            for cdc in paths[converter]:
                channels = []
                for fdc in paths[converter][cdc]:
                    channels += paths[converter][cdc][fdc]["channels"]
                channels = [name for name in channels if "_i" in name]
                if "ADC" in converter:
                    self._rx_coarse_ddc_channel_names.append(channels[0])
                    self._rx_fine_ddc_channel_names += channels
                else:
                    self._tx_coarse_duc_channel_names.append(channels[0])
                    self._tx_fine_duc_channel_names += channels

        rx_tx.__init__(self)
        self.rx_buffer_size = 2 ** 16

    @property
    def path_map(self):
        """ path_map: Map of channelizers both coarse and fine to
            individual driver channel names
        """
        return self._path_map

    @property
    def rx_channel_nco_frequencies(self):
        """rx_channel_nco_frequencies: Receive path fine DDC NCO frequencies
        """
        return self._get_iio_attr_vec(
            self._rx_fine_ddc_channel_names, "channel_nco_frequency", False
        )

    @rx_channel_nco_frequencies.setter
    def rx_channel_nco_frequencies(self, value):
        self._set_iio_attr_vec(
            self._rx_fine_ddc_channel_names, "channel_nco_frequency", False, value
        )

    @property
    def rx_channel_nco_phases(self):
        """rx_channel_nco_phases: Receive path fine DDC NCO phases
        """
        return self._get_iio_attr_vec(
            self._rx_fine_ddc_channel_names, "channel_nco_phase", False
        )

    @rx_channel_nco_phases.setter
    def rx_channel_nco_phases(self, value):
        self._set_iio_attr_vec(
            self._rx_fine_ddc_channel_names, "channel_nco_phase", False, value,
        )

    @property
    def rx_main_nco_frequencies(self):
        """rx_main_nco_frequencies: Receive path coarse DDC NCO frequencies
        """
        return self._get_iio_attr_vec(
            self._rx_coarse_ddc_channel_names, "main_nco_frequency", False
        )

    @rx_main_nco_frequencies.setter
    def rx_main_nco_frequencies(self, value):
        self._set_iio_attr_vec(
            self._rx_coarse_ddc_channel_names, "main_nco_frequency", False, value,
        )

    @property
    def rx_main_nco_phases(self):
        """rx_main_nco_phases: Receive path coarse DDC NCO phases
        """
        return self._get_iio_attr_vec(
            self._rx_coarse_ddc_channel_names, "main_nco_phase", False
        )

    @rx_main_nco_phases.setter
    def rx_main_nco_phases(self, value):
        self._set_iio_attr_vec(
            self._rx_coarse_ddc_channel_names, "main_nco_phase", False, value,
        )

    @property
    def rx_test_mode(self):
        """rx_test_mode: NCO Test Mode """
        return self._get_iio_attr_str("voltage0_i", "test_mode", False)

    @rx_test_mode.setter
    def rx_test_mode(self, value):
        self._set_iio_attr(
            "voltage0_i", "test_mode", False, value,
        )

    @property
    def rx_nyquist_zone(self):
        """rx_nyquist_zone: ADC nyquist zone. Options are: odd, even """
        return self._get_iio_attr("voltage0_i", "nyquist_zone", False)

    @rx_nyquist_zone.setter
    def rx_nyquist_zone(self, value):
        self._set_iio_attr_str(
            "voltage0_i", "nyquist_zone", False, value,
        )

    @property
    def tx_channel_nco_frequencies(self):
        """tx_channel_nco_frequencies: Transmit path fine DUC NCO frequencies
        """
        return self._get_iio_attr_vec(
            self._tx_fine_duc_channel_names, "channel_nco_frequency", True
        )

    @tx_channel_nco_frequencies.setter
    def tx_channel_nco_frequencies(self, value):
        self._set_iio_attr_vec(
            self._tx_fine_duc_channel_names, "channel_nco_frequency", True, value
        )

    @property
    def tx_channel_nco_phases(self):
        """tx_channel_nco_phases: Transmit path fine DUC NCO phases
        """
        return self._get_iio_attr_vec(
            self._tx_fine_duc_channel_names, "channel_nco_phase", True
        )

    @tx_channel_nco_phases.setter
    def tx_channel_nco_phases(self, value):
        self._set_iio_attr_vec(
            self._tx_fine_duc_channel_names, "channel_nco_phase", True, value,
        )

    @property
    def tx_main_nco_frequencies(self):
        """tx_main_nco_frequencies: Transmit path coarse DUC NCO frequencies
        """
        return self._get_iio_attr_vec(
            self._tx_coarse_duc_channel_names, "main_nco_frequency", True
        )

    @tx_main_nco_frequencies.setter
    def tx_main_nco_frequencies(self, value):
        self._set_iio_attr_vec(
            self._tx_coarse_duc_channel_names, "main_nco_frequency", True, value,
        )

    @property
    def tx_main_nco_phases(self):
        """tx_main_nco_phases: Transmit path coarse DUC NCO phases
        """
        return self._get_iio_attr_vec(
            self._tx_coarse_duc_channel_names, "main_nco_phase", True
        )

    @tx_main_nco_phases.setter
    def tx_main_nco_phases(self, value):
        self._set_iio_attr_vec(
            self._tx_coarse_duc_channel_names, "main_nco_phase", True, value,
        )

    @property
    def tx_main_ffh_frequency(self):
        """tx_main_ffh_frequency: Transmitter fast frequency hop frequency. This will set
            The NCO frequency of the NCO selected from the bank defined by tx_main_ffh_index
        """
        return self._get_iio_attr("voltage0_i", "main_ffh_frequency", True)

    @tx_main_ffh_frequency.setter
    def tx_main_ffh_frequency(self, value):
        if self.tx_main_ffh_index == 0:
            raise Exception(
                "To set a FFH NCO bank frequency, tx_main_ffh_index must > 0"
            )
        self._set_iio_attr(
            "voltage0_i", "main_ffh_frequency", True, value,
        )

    @property
    def tx_main_ffh_index(self):
        """tx_main_ffh_index: Transmitter fast frequency hop NCO bank index
        """
        return self._get_iio_attr("voltage0_i", "main_ffh_index", True)

    @tx_main_ffh_index.setter
    def tx_main_ffh_index(self, value):
        self._set_iio_attr(
            "voltage0_i", "main_ffh_index", True, value,
        )

    @property
    def tx_main_ffh_mode(self):
        """tx_main_ffh_mode: Set hop transition mode of NCOs Options are:
            phase_continuous, phase_incontinuous, and phase_coherent
        """
        return self._get_iio_attr("voltage0_i", "main_ffh_mode", True)

    @tx_main_ffh_mode.setter
    def tx_main_ffh_mode(self, value):
        self._set_iio_attr(
            "voltage0_i", "main_ffh_mode", True, value,
        )

    @property
    def loopback_mode(self):
        """loopback_mode: Enable loopback mode RX->TX
        """
        return self._get_iio_dev_attr("loopback_mode")

    @loopback_mode.setter
    def loopback_mode(self, value):
        self._set_iio_dev_attr(
            "loopback_mode", value,
        )

    @property
    def rx_sampling_frequency(self):
        """rx_sampling_frequency: Sample rate after decimation"""
        return self._get_iio_attr("voltage0_i", "sampling_frequency", False)

    @property
    def adc_frequency(self):
        """adc_frequency: ADC frequency in Hz"""
        return self._get_iio_attr("voltage0_i", "adc_frequency", False)

    @property
    def tx_sampling_frequency(self):
        """tx_sampling_frequency: Sample rate before interpolation"""
        return self._get_iio_attr("voltage0_i", "sampling_frequency", True)

    @property
    def dac_frequency(self):
        """dac_frequency: DAC frequency in Hz"""
        return self._get_iio_attr("voltage0_i", "dac_frequency", True)
