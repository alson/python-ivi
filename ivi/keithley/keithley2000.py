"""

Python Interchangeable Virtual Instrument Library

Copyright (c) 2012-2017 Alex Forencich
Copyright (c) 2017 Alson van der Meulen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

from __future__ import division

import time
import struct
import math

from .. import ivi
from .. import dmm
from .. import swtch
from .. import scpi

MeasurementFunctionMapping = {
        'dc_volts': 'volt:dc',
        'ac_volts': 'volt:ac',
        'dc_current': 'curr:dc',
        'ac_current': 'curr:ac',
        'two_wire_resistance': 'res',
        'four_wire_resistance': 'fres',
        'frequency': 'freq',
        'period': 'per',
        'continuity': 'cont',
        'diode': 'diod'}

MeasurementRangeMapping = {
        'dc_volts': 'volt:dc:range',
        'ac_volts': 'volt:ac:range',
        'dc_current': 'curr:dc:range',
        'ac_current': 'curr:ac:range',
        'two_wire_resistance': 'res:range',
        'four_wire_resistance': 'fres:range'}

MeasurementAutoRangeMapping = {
        'dc_volts': 'volt:dc:range:auto',
        'ac_volts': 'volt:ac:range:auto',
        'dc_current': 'curr:dc:range:auto',
        'ac_current': 'curr:ac:range:auto',
        'two_wire_resistance': 'res:range:auto',
        'four_wire_resistance': 'fres:range:auto'}

MeasurementResolutionMapping = {
        'dc_volts': 'volt:dc:dig',
        'ac_volts': 'volt:ac:dig',
        'dc_current': 'curr:dc:dig',
        'ac_current': 'curr:ac:dig',
        'two_wire_resistance': 'res:dig',
        'four_wire_resistance': 'fres:dig'}

class keithley2000(scpi.dmm.Base, scpi.dmm.MultiPoint, scpi.dmm.SoftwareTrigger,
        swtch.Base):
    "Keithley 2000 IVI DMM driver"

    def __init__(self, *args, **kwargs):
        self.__dict__.setdefault('_instrument_id', 'MODEL 2000')
        self._channel_count = 1
        self._scanner_installed = False

        super(keithley2000, self).__init__(*args, **kwargs)

        self._memory_size = 5

        self._identity_description = "Keithley model 2000 IVI DMM driver"
        self._identity_identifier = ""
        self._identity_revision = ""
        self._identity_vendor = ""
        self._identity_instrument_manufacturer = "Keithley"
        self._identity_instrument_model = ""
        self._identity_instrument_firmware_revision = ""
        self._identity_specification_major_version = 4
        self._identity_specification_minor_version = 1
        self._identity_supported_instrument_models = ['MODEL 2000']
        self._real_init_channels()

    def _initialize(self, resource = None, id_query = False, reset = False, **keywargs):
        "Opens an I/O session to the instrument."

        super(keithley2000, self)._initialize(resource, id_query, reset, **keywargs)

        # interface clear
        if not self._driver_operation_simulate:
            self._clear()

        # check ID
        if id_query and not self._driver_operation_simulate:
            id_ = self.identity.instrument_model
            id_check = self._instrument_id
            id_short = id_[:len(id_check)]
            if id_short != id_check:
                raise Exception("Instrument ID mismatch, expecting %s, got %s", id_check, id_short)

        # reset
        if reset:
            self.utility.reset()

    def _load_id_string(self):
        super(keithley2000, self)._load_id_string()
        if not self._driver_operation_simulate:
            opts = self._ask('*OPT?')
            if '200X-SCAN' in opts:
                self._scanner_installed = True
                self._set_cache_valid(True, 'scanner_installed')
                self._init_channels()

    def _get_scanner_installed(self):
        if not self._get_cache_valid():
            self._load_id_string()
        return self._scanner_installed

    def _init_channels(self):
        # We need to access the instrument to determine channel count, but IVI
        # is not initialized when this method is called, so supply a stub and
        # substitute a _real_init_channels() that we call at the end of
        # __init__().
        pass

    def _real_init_channels(self):
        # Only do this if we have a scanner installed
        if not self._get_scanner_installed():
            return

        try:
            super(keithley2000, self)._init_channels()
        except AttributeError:
            pass

        self._channel_count = 10
        self._channel_name = list()
        self._int_channel_name = list()
        self._channel_characteristics_ac_current_carry_max = list()
        self._channel_characteristics_ac_current_switching_max = list()
        self._channel_characteristics_ac_power_carry_max = list()
        self._channel_characteristics_ac_power_switching_max = list()
        self._channel_characteristics_ac_voltage_max = list()
        self._channel_characteristics_bandwidth = list()
        self._channel_characteristics_impedance = list()
        self._channel_characteristics_dc_current_carry_max = list()
        self._channel_characteristics_dc_current_switching_max = list()
        self._channel_characteristics_dc_power_carry_max = list()
        self._channel_characteristics_dc_power_switching_max = list()
        self._channel_characteristics_dc_voltage_max = list()
        self._channel_is_configuration_channel = list()
        self._channel_is_source_channel = list()
        self._channel_characteristics_settling_time = list()
        self._channel_characteristics_wire_mode = list()
        self._init_single_channel("common", None)
        for i in range(self._channel_count):
            self._init_single_channel("channel%d" % (i+1), i+1)

        self.channels._set_list(self._channel_name)

    def _init_single_channel(self, name, int_name):
        self._channel_name.append(name)
        self._int_channel_name.append(int_name)
        self._channel_characteristics_ac_current_carry_max.append(1)
        self._channel_characteristics_ac_current_switching_max.append(1)
        self._channel_characteristics_ac_power_carry_max.append(62.5)
        self._channel_characteristics_ac_power_switching_max.append(62.5)
        self._channel_characteristics_ac_voltage_max.append(125)
        self._channel_characteristics_bandwidth.append(1e5)
        self._channel_characteristics_impedance.append(None)
        self._channel_characteristics_dc_current_carry_max.append(1)
        self._channel_characteristics_dc_current_switching_max.append(1)
        self._channel_characteristics_dc_power_carry_max.append(30)
        self._channel_characteristics_dc_power_switching_max.append(30)
        self._channel_characteristics_dc_voltage_max.append(110)
        self._channel_is_configuration_channel.append(False)
        self._channel_is_source_channel.append(False)
        self._channel_characteristics_settling_time.append(0.0025)
        self._channel_characteristics_wire_mode.append(2)

    def _get_resolution(self):
        # The DMM only supports specifying the resolution in digits, while the
        # IviDMM module requires resolution absolute. So we convert based on the
        # current range setting.
        if not self._driver_operation_simulate and not self._get_cache_valid():
            range_ = self.range
            func = self._get_measurement_function()
            if func in MeasurementResolutionMapping:
                cmd = MeasurementResolutionMapping[func]
                dig = int(self._ask("%s?" % (cmd)))
                # convert digits to absolute resolution
                abs_resolution = range_ * 10**(-dig+1)
                # round down to even power of 10
                abs_resolution = math.pow(10,
                        math.floor(math.log10(abs_resolution)))
                self._resolution = abs_resolution
                self._set_cache_valid()
        return self._resolution

    def _set_resolution(self, value):
        # The DMM only supports specifying the resolution in digits, while the
        # IviDMM module requires resolution absolute. So we convert based on the
        # current range setting.
        value = float(value)
        # round up to even power of 10
        value = math.pow(10, math.ceil(math.log10(value)))
        if not self._driver_operation_simulate:
            range_ = self.range
            func = self._get_measurement_function()
            if func in MeasurementResolutionMapping:
                # Convert absolute resolution resolution to digits
                dig = math.ceil(math.log10(range_ / value)+1)
                cmd = MeasurementResolutionMapping[func]
                self._write("%s %g" % (cmd, dig))
        self._resolution = value
        self._set_cache_valid()

    def _path_can_connect(self, channel1, channel2):
        channel1 = ivi.get_index(self._channel_name, channel1)
        channel2 = ivi.get_index(self._channel_name, channel2)
        if (channel1 != channel2) and ('common' in [self._channel_name[chan] for
            chan in (channel1, channel2)]):
            return True
        else:
            return False

    def _path_connect(self, channel1, channel2):
        channel1 = ivi.get_index(self._channel_name, channel1)
        channel2 = ivi.get_index(self._channel_name, channel2)
        if not self._path_can_connect(channel1, channel2):
            raise swtch.PathNotFoundException('{0} -> {1}'.format(channel1,
                channel2))
        src = [chan for chan in (channel1, channel2) if self._channel_name[chan]
                != 'common']
        if len(src) != 1:
            raise swtch.PathNotFoundException('{0} -> {1}'.format(channel1,
                channel2))
        self._write('ROUTE:CLOSE (@ {0})'.format(self._int_channel_name[src[0]]))

    def _path_disconnect(self, channel1, channel2):
        channel1 = ivi.get_index(self._channel_name, channel1)
        channel2 = ivi.get_index(self._channel_name, channel2)
        if not self._path_can_connect(channel1, channel2):
            raise swtch.PathNotFoundException('{0} -> {1}'.format(channel1,
                channel2))
        self._write('ROUTE:OPEN:ALL')

    def _path_disconnect_all(self):
        self._write('ROUTE:OPEN:ALL')

    def _path_wait_for_debounce(self, maximum_time):
        time.sleep(0.01)
