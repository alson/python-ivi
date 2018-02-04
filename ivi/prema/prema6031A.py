"""

Python Interchangeable Virtual Instrument Library

Copyright (c) 2014-2017 Alex Forencich
Copyright (c) 2017-2018 Alson van der Meulen

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
        'dc_volts': 'VD',
        'ac_volts': 'VA',
        'ac_plus_dc_volts': 'VC',
        'two_wire_resistance': 'O2',
        'four_wire_resistance': 'O4',
        'dc_current': 'ID',
        'ac_current': 'IA',
        }
RangeMapping = {
        'dc_volts': OrderedDict([
            (0.2,    '1'),
            (2.0,    '2'),
            (20.0,   '3'),
            (200.0,  '4'),
            (1000.0, '5'),
            ]),
        'ac_volts': OrderedDict([
            (0.2,    '1'),
            (2.0,    '2'),
            (20.0,   '3'),
            (200.0,  '4'),
            (1000.0, '5'),
            ]),
        'ac_plus_dc_volts': OrderedDict([
            (0.2,    '1'),
            (2.0,    '2'),
            (20.0,   '3'),
            (200.0,  '4'),
            (1000.0, '5'),
            ]),
        'two_wire_resistance': OrderedDict([
            (0.2e3,  '1'),
            (2e3,    '2'),
            (20e3,   '3'),
            (200e3,  '4'),
            (2000e3, '5'),
            (20e6,   '6'),
            ]),
        'four_wire_resistance': OrderedDict([
            (0.2e3,  '1'),
            (2e3,    '2'),
            (20e3,   '3'),
            (200e3,  '4'),
            (2000e3, '5'),
            (20e6,   '6'),
            ]),
        'dc_current': OrderedDict([
            (2.0,     '5'),
            ]),
        'ac_current': OrderedDict([
            (2.0,     '5'),
            ]),
        }
ApertureTimeMapping = {
         .02: '0',
         .04: '1',
         .1 : '2',
         .2 : '3',
         .4 : '4',
         1  : '5',
         2  : '6',
         4  : '7',
         10 : '8',
         20 : '9',
         }

class prema6031A(ivi.Driver, dmm.Base, dmm.DeviceInfo):
    """"Prema 6031A DMM.

    This is an early GPIB implementation that pre-dates IEEE 488.2 (SCPI), so it
    is not a perfect fit to the IviDmm model.

    Not implemented:
    - Handling errors from the meter.
    - Variable integration interval (1 PLC) or digital filtering.
    - Trigger sources other than immediate. The meter will also trigger on GET,
      GPIB trigger and external trigger, but this is not configurable, and it
      will immediately arm the triggers after completing a measurement, skipping
      the idle state.
    """

    def __init__(self, *args, **kwargs):
        self.__dict__.setdefault('_instrument_id', '6031A')

        super(prema6031A, self).__init__(*args, **kwargs)
        self._identity_description = "Prema 6031A integrating digital multimeter"
        self._identity_identifier = "6031A"
        self._identity_revision = ""
        self._identity_vendor = ""
        self._identity_instrument_manufacturer = "Prema"
        self._identity_instrument_model = ""
        self._identity_instrument_firmware_revision = ""
        self._identity_specification_major_version = 3
        self._identity_specification_minor_version = 0
        self._identity_supported_instrument_models = ['6031A']

        self._trigger_source = 'immediate'
        self._advanced_aperture_time = 1.0
        self._advanced_aperture_time_units = 'seconds'

        self._add_property('advanced.aperture_time',
                            self._get_advanced_aperture_time,
                            self._set_advanced_aperture_time,
                            )

    def _initialize(self, resource = None, id_query = False, reset = False, **keywargs):
        "Opens an I/O session to the instrument."

        super(prema6031A, self)._initialize(resource, id_query, reset, **keywargs)

        # interface clear
        if not self._driver_operation_simulate:
            self._clear()

        # This instrument does not support ID queries
        if id_query:
            pass

        # reset
        if reset:
            self._utility_reset()

    def _utility_error_query(self):
        error_code = 0
        error_message = "No error"
        return (error_code, error_message)

    def _utility_reset(self):
        if not self._driver_operation_simulate:
            # Set for start mode (triggered), 1s integration time, long output
            # mode, no program, no digital filter
            self._write("P00F0T5D0Q0MOFL1S1")
            self.driver_operation.invalidate_all_attributes()

    def _utility_self_test(self):
        raise ivi.OperationNotSupportedException()

    def _measurement_abort(self):
        self._clear()
        pass

    def _parse_measurement_result(self, raw_result):
        raw_value = raw_result[:13]
        try:
            value = float(raw_value)
        except ValueError as e:
            if raw_value.strip() == 'ERROR 01':
                return float('inf')
            else:
                raise e
        return value

    def _measurement_initiate(self):
        if self._driver_operation_simulate:
            return
        self._write('S1')

    def _measurement_fetch(self, max_time):
        if self._driver_operation_simulate:
            return
        raw_result = self._read()
        return self._parse_measurement_result(raw_result)

    def _measurement_read(self, max_time):
        self._measurement_initiate()
        time.sleep(self._advanced_aperture_time)
        return self._measurement_fetch(max_time)

    def _measurement_is_out_of_range(self, value):
        return value == float('inf')

    def _measurement_is_over_range(self, value):
        raise ivi.OperationNotSupportedException

    def _measurement_is_under_range(self, value):
        raise ivi.OperationNotSupportedException

    def _set_trigger_source(self, value):
        if value.lower() != 'immediate':
            raise ivi.ValueNotSupportedException()
        super(prema6031A, self)._set_trigger_source(value)

    def _set_trigger_delay(self, value):
        value = float(value)
        if value > 0:
            raise ivi.ValueNotSupportedException()
        super(prema6031A, self)._set_trigger_delay(value)

    def _set_trigger_delay_auto(self, value):
        value = bool(value)
        if value:
            self._set_trigger_delay(0)
        super(prema6031A, self)._set_trigger_delay_auto(value)

    def _set_measurement_function(self, value):
        if value.lower() not in MeasurementFunctionMapping:
            raise ivi.ValueNotSupportedException()
        super(prema6031A, self)._set_measurement_function(value)
        self._write(MeasurementFunctionMapping[value.lower()])

    def _set_range(self, value):
        value = float(value)
        range_map = RangeMapping[self._measurement_function]
        raw_range = None
        # Use the fact that range_map is an OrderedDict to make sure we pick the
        # lowest suitable range.
        for k,v in range_map.items():
            if abs(value) <= k:
                raw_range = v
                break
        if not raw_range:
            raise ivi.ValueNotSupportedException()
        super(prema6031A, self)._set_range(value)
        if self._driver_operation_simulate:
            return
        self._write('R{0}'.format(raw_range))

    def _set_auto_range(self, value):
        AutoRangeMapping = {
                'off': 0,
                'on': 1,
                }
        if value.lower() not in AutoRangeMapping:
            raise ivi.ValueNotSupportedException()
        super(prema6031A, self)._set_auto_range(value)
        if self._driver_operation_simulate:
            return
        self._write('A{0}'.format(AutoRangeMapping[value.lower()]))

    def _set_advanced_aperture_time(self, value):
        value = float(value)
        if not value in ApertureTimeMapping:
            raise ivi.ValueNotSupportedException()
        self._write('T{0}'.format(ApertureTimeMapping[value]))
        self._advanced_aperture_time = value
