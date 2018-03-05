"""

Python Interchangeable Virtual Instrument Library

Copyright (c) 2014-2017 Alex Forencich
Copyright (c) 2018 Alson van der Meulen

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
from __future__ import print_function

import re
import time
from collections import OrderedDict

from .. import ivi
from .. import dmm

MeasurementFunctionMapping = {
        'dc_volts': 'VDC',
        'ac_volts': 'VAC',
        'two_wire_resistance': 'RTW',
        'four_wire_resistance': 'RFW',
        'dc_current': 'IDC',
        'ac_current': 'IAC',
        }
RangeMax = {
        'dc_volts': 300,
        'ac_volts': 300,
        'two_wire_resistance': 300e6,
        'four_wire_resistance': 3e6,
        'dc_current': 3,
        'ac_current': 3,
        }
ApertureTimeMapping = {
        'dc_volts': {
            0.005 : 4,
            0.02  : 3,
            0.2   : 2,
            2     : 1,
            },
        'ac_volts': {
            0.02  : 3,
            0.2   : 2,
            },
        'two_wire_resistance': {
            0.005 : 4,
            0.02  : 3,
            0.2   : 2,
            2     : 1,
            },
        'four_wire_resistance': {
            0.005 : 4,
            0.02  : 3,
            0.2   : 2,
            2     : 1,
            },
        'dc_current': {
            0.02  : 3,
            0.2   : 2,
            2     : 1,
            },
        'ac_current': {
            0.02  : 3,
            0.2   : 2,
            },
        }

class philipsPM2534(ivi.Driver, dmm.Base, dmm.DeviceInfo):
    """"Philips PM2534 DMM.

    This is an early GPIB implementation that pre-dates IEEE 488.2 (SCPI), so it
    is not a perfect fit to the IviDmm model.

    Not implemented:
    - Handling errors from the meter.
    - Trigger sources other than immediate. The meter will also trigger on GET,
      GPIB trigger and external trigger, but this is not configurable, and it
      will immediately arm the triggers after completing a measurement, skipping
      the idle state.
    """

    def __init__(self, *args, **kwargs):
        self.__dict__.setdefault('_instrument_id', 'PM2534')

        super(philipsPM2534, self).__init__(*args, **kwargs)
        self._identity_description = "Philips PM2534 System Multimeter"
        self._identity_identifier = "PM2534"
        self._identity_revision = ""
        self._identity_vendor = ""
        self._identity_instrument_manufacturer = "Philips"
        self._identity_instrument_model = ""
        self._identity_instrument_firmware_revision = ""
        self._identity_specification_major_version = 3
        self._identity_specification_minor_version = 0
        self._identity_supported_instrument_models = ['PM2534', 'PM2535']

        self._trigger_source = 'immediate'
        self._advanced_aperture_time = 0.2
        self._advanced_aperture_time_units = 'seconds'

        self._add_property('advanced.aperture_time',
                            self._get_advanced_aperture_time,
                            self._set_advanced_aperture_time,
                            )

    def _initialize(self, resource = None, id_query = False, reset = False, **keywargs):
        "Opens an I/O session to the instrument."

        super(philipsPM2534, self)._initialize(resource, id_query, reset, **keywargs)

        # interface clear
        if not self._driver_operation_simulate:
            self._clear()

        # This instrument does not support ID queries
        if id_query:
            self._load_id_string()
            id_ = self.identity.instrument_model
            id_check = self._instrument_id
            id_short = id_[:len(id_check)]
            if id_short != id_check:
                raise Exception("Instrument ID mismatch, expecting {0}, got {1}".format(
                        id_check, self.identity.instrument_model))

        # reset
        if reset:
            self._utility_reset()

    def _load_id_string(self):
        if self._driver_operation_simulate:
            self._identity_instrument_manufacturer = "Not available while simulating"
            self._identity_instrument_model = "Not available while simulating"
            self._identity_instrument_serial_number = "Not available while simulating"
            self._identity_instrument_firmware_revision = "Not available while simulating"
        else:
            id_ = self._ask("ID ?")
            self._identity_instrument_model = id_[:6]

    def _utility_error_query(self):
        error_code = 0
        error_message = "No error"
        return (error_code, error_message)

    def _utility_reset(self):
        if not self._driver_operation_simulate:
            # Set for start mode (triggered), 1s integration time, long output
            # mode, no program, no digital filter
            self._write("TRG B")
            self.driver_operation.invalidate_all_attributes()

    def _utility_self_test(self):
        raise ivi.OperationNotSupportedException()

    def _measurement_abort(self):
        self._clear()
        pass

    def _parse_measurement_result(self, raw_result):
        matches = re.fullmatch(r'([A-Z]{3}) +([O ]) *([+-]?[0-9.]{5,8}E[+-][0-9]{2})',
                raw_result)
        if not matches:
            raise ivi.UnexpectedResponseException('Unexpected response: {0}'.format(
                raw_result))
        (function, overflow, raw_value) = matches.groups()
        value = float(raw_value)
        if overflow == 'O':
            if value < 0:
                return float('-inf')
            else:
                return float('+inf')

        # Could verify function
        return value

    def _measurement_initiate(self):
        if self._driver_operation_simulate:
            return
        self._write('X')

    def _measurement_fetch(self, max_time):
        if self._driver_operation_simulate:
            return
        raw_result = self._read()
        return self._parse_measurement_result(raw_result)

    def _measurement_read(self, max_time):
        self._measurement_initiate()
        return self._measurement_fetch(max_time)

    def _measurement_is_over_range(self, value):
        return value == float('+inf')

    def _measurement_is_under_range(self, value):
        return value == float('-inf')

    def _set_trigger_source(self, value):
        if value.lower() != 'immediate':
            raise ivi.ValueNotSupportedException()
        super(philipsPM2534, self)._set_trigger_source(value)

    def _set_trigger_delay(self, value):
        value = float(value)
        if value > 0:
            raise ivi.ValueNotSupportedException()
        super(philipsPM2534, self)._set_trigger_delay(value)

    def _set_trigger_delay_auto(self, value):
        value = bool(value)
        if value:
            self._set_trigger_delay(0)
        super(philipsPM2534, self)._set_trigger_delay_auto(value)

    def _set_measurement_function(self, value):
        if value.lower() not in MeasurementFunctionMapping:
            raise ivi.ValueNotSupportedException()
        super(philipsPM2534, self)._set_measurement_function(value)
        self._write('FNC {0}'.format(MeasurementFunctionMapping[value.lower()]))

    def _set_range(self, value):
        value = float(value)
        if not abs(value) <= RangeMax[self._measurement_function]:
            raise ivi.ValueNotSupportedException()
        super(philipsPM2534, self)._set_range(value)
        if self._driver_operation_simulate:
            return
        self._write('RNG {0}'.format(abs(value)))

    def _set_auto_range(self, value):
        if value.lower() not in ('off', 'on'):
            raise ivi.ValueNotSupportedException()
        super(philipsPM2534, self)._set_auto_range(value)
        if self._driver_operation_simulate:
            return
        if value == 'on':
            self._write('RNG A')
        else:
            self._set_range(self._range)

    def _set_advanced_aperture_time(self, value):
        value = float(value)
        if not value in ApertureTimeMapping[self._measurement_function]:
            raise ivi.ValueNotSupportedException()
        self._write('MSP {0}'.format(
            ApertureTimeMapping[self._measurement_function][value]))
        self._advanced_aperture_time = value
