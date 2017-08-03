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

import time
import struct
import math

from .. import ivi
from .. import dmm
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

class keithley2000(scpi.dmm.Base, scpi.dmm.MultiPoint, scpi.dmm.SoftwareTrigger):
    "Keithley 2000 IVI DMM driver"

    def __init__(self, *args, **kwargs):
        self.__dict__.setdefault('_instrument_id', 'MODEL 2000')

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
                # Convert absolute resoltuion resolution to digits
                dig = math.ceil(math.log10(range_ / value)+1)
                cmd = MeasurementResolutionMapping[func]
                self._write("%s %g" % (cmd, dig))
        self._resolution = value
        self._set_cache_valid()
