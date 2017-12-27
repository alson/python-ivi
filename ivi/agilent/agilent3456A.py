"""

Python Interchangeable Virtual Instrument Library

Copyright (c) 2014-2017 Alex Forencich
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
from __future__ import print_function
import re
from collections import OrderedDict

from .. import ivi
from .. import dmm

TriggerSourceMapping = {
        'immediate': '1',
        'bus': '4',
        'external': '2',
        }
MeasurementFunctionMapping = {
        'dc_volts': '1',
        'ac_volts': '2',
        'ac_plus_dc_volts': '3',
        'two_wire_resistance': '4',
        'four_wire_resistance': '5',
        }
RangeMapping = {
        'dc_volts': OrderedDict([
            (0.1,    '2'),
            (1.0,    '3'),
            (10.0,   '4'),
            (100.0,  '5'),
            (1000.0, '6'),
            ]),
        'ac_volts': OrderedDict([
            (0.1,    '2'),
            (1.0,    '3'),
            (10.0,   '4'),
            (100.0,  '5'),
            (1000.0, '6'),
            ]),
        'ac_plus_dc_volts': OrderedDict([
            (0.1,    '2'),
            (1.0,    '3'),
            (10.0,   '4'),
            (100.0,  '5'),
            (1000.0, '6'),
            ]),
        'two_wire_resistance': OrderedDict([
            (0.1e3,  '2'),
            (1e3,    '3'),
            (10e3,   '4'),
            (100e3,  '5'),
            (1000e3, '6'),
            (10e6,   '7'),
            (100e6,  '8'),
            (1000e6, '9'),
            ]),
        'four_wire_resistance': OrderedDict([
            (0.1e3,  '2'),
            (1e3,    '3'),
            (10e3,   '4'),
            (100e3,  '5'),
            (1000e3, '6'),
            (10e6,   '7'),
            (100e6,  '8'),
            (1000e6, '9'),
            ]),
        'dc_current': OrderedDict([
            (0.03,    '1'),
            (3.0,     '2'),
            ]),
        'ac_current': OrderedDict([
            (0.03,    '1'),
            (3.0,     '2'),
            ]),
        }

class agilent3456A(ivi.Driver, dmm.Base, dmm.MultiPoint, dmm.SoftwareTrigger):
    """"HP 3456A DMM.

    This is an early GPIB implementation that pre-dates IEEE 488.2 (SCPI), so it
    is not a perfect fit to the IviDmm model.

    Not implemented:
    - Handling errors from the meter.
    - Variable integration interval (100 PLC).
    - Changing the resolution (6.5 digit).
    - The idle state as defined for IviDmm: unless the trigger source is
      immediate, after measurement complete it will return to the
      wait-for-trigger state without waiting for read/initiate. If the trigger
      source is immediate, any settings change may trigger a reading (the result
      of this reading is discarded).
    """
    _READINGS_MEMORY_SIZE = 350

    def __init__(self, *args, **kwargs):
        self.__dict__.setdefault('_instrument_id', '3456A')

        super(agilent3456A, self).__init__(*args, **kwargs)
        self._identity_description = "HP 3456A DMM"
        self._identity_identifier = "3456A"
        self._identity_revision = ""
        self._identity_vendor = ""
        self._identity_instrument_manufacturer = "HP"
        self._identity_instrument_model = "3456A"
        self._identity_instrument_firmware_revision = ""
        self._identity_specification_major_version = 3
        self._identity_specification_minor_version = 0
        self._identity_supported_instrument_models = ['3456A']

        self._trigger_source = 'immediate'

    def _initialize(self, resource = None, id_query = False, reset = False, **keywargs):
        "Opens an I/O session to the instrument."

        super(agilent3456A, self)._initialize(resource, id_query, reset, **keywargs)

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
                raise Exception("Instrument ID mismatch, expecting %s, got %s", id_check, id_short)

        # reset
        if reset:
            self._utility_reset()

    def _load_id_string(self):
        if self._driver_operation_simulate:
            self._identity_instrument_manufacturer = "Not available while simulating"
            self._identity_instrument_model = "Not available while simulating"
            self._identity_instrument_serial_number = "Not available while simulating"
            self._identity_instrument_firmware_revision = "Not available while simulating"

    def _utility_error_query(self):
        error_code = 0
        error_message = "No error"
        return (error_code, error_message)

    def _utility_reset(self):
        if not self._driver_operation_simulate:
            # DCV, auto range, single triggering, 6 digits displayed, 100 NPLC
            # integration, analog filter on
            self._clear()
            self._write("HA1F1R1T3W6STG100STI-1STD1STNFL1RS0")
            self.driver_operation.invalidate_all_attributes()

    def _utility_self_test(self):
        raise ivi.OperationNotSupportedException()

    def _measurement_abort(self):
        self._clear()
        pass

    def _parse_measurement_result(self, raw_result):
        matches = re.fullmatch(r'([+-][0-9.]{8}E[+-]\d)',
                raw_result)
        if not matches:
            raise ivi.UnexpectedResponseException(
                'Unexpected response: {0}'.format(raw_result))
        raw_value = matches.group(1)
        value = float(raw_value)
        return value

    def _measurement_initiate(self):
        if self._driver_operation_simulate:
            return
        if self._trigger_source == 'immediate':
            self._write('T3')

    def _measurement_fetch(self, max_time):
        if self._driver_operation_simulate:
            return
        raw_result = self._read()
        return self._parse_measurement_result(raw_result)

    def _measurement_read(self, max_time):
        self._measurement_initiate()
        return self._measurement_fetch(max_time)

    def _measurement_is_over_range(self, value):
        return value >= +1999999e+9

    def _measurement_is_under_range(self, value):
        return value <= -1999999e+9

    def _set_trigger_source(self, value):
        if value.lower() not in TriggerSourceMapping:
            raise ivi.ValueNotSupportedException()
        super(agilent3456A, self)._set_trigger_source(value)
        if self._driver_operation_simulate:
            return
        self._write('T{0}'.format(TriggerSourceMapping[value.lower()]))

    def _set_trigger_delay(self, value):
        value = float(value)
        self._set_trigger_delay_auto(False)
        super(agilent3456A, self)._set_trigger_delay(value)
        if self._driver_operation_simulate:
            return
        self._write('{0:0=+12E}STD'.format(value))

    def _set_trigger_delay_auto(self, value):
        value = bool(value)
        if value:
            self._set_trigger_delay(-1)
        super(agilent3456A, self)._set_trigger_delay_auto(value)

    def _set_measurement_function(self, value):
        if value.lower() not in MeasurementFunctionMapping:
            raise ivi.ValueNotSupportedException()
        super(agilent3456A, self)._set_measurement_function(value)
        self._write('F{0}'.format(MeasurementFunctionMapping[value.lower()]))

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
        super(agilent3456A, self)._set_range(value)
        if self._driver_operation_simulate:
            return
        self._write('R{0}'.format(raw_range))

    def _set_auto_range(self, value):
        if value.lower() not in ('on', 'off'):
            raise ivi.ValueNotSupportedException()
        super(agilent3456A, self)._set_auto_range(value)
        if self._driver_operation_simulate:
            return
        if value == 'on':
            self._write('R1')
        else:
            self._set_range(self._range)

    def _send_software_trigger(self):
        if self._driver_operation_simulate:
            return
        if self._trigger_source.lower() != 'bus':
            raise ivi.TriggerNotSoftwareException()
        self._trigger()

    def _set_trigger_measurement_complete_destination(self, value):
        value = str(value)
        if value.lower() != 'none':
            raise ivi.ValueNotSupportedException()
        super(agilent3456A, self)._set_trigger_measurement_complete_destination(value)

    def _set_trigger_multi_point_sample_count(self, value):
        value = int(value)
        if value == 0:
            value = self._READINGS_MEMORY_SIZE
        if not 1 <= value <= self._READINGS_MEMORY_SIZE:
            raise ivi.ValueNotSupportedException()
        super(agilent3456A, self)._set_trigger_multi_point_sample_count(value)
        self._write('{0}STN'.format(value))
        if self._utility_is_using_reading_storage:
            self._write('RS1')
        else:
            self._write('RS0')

    def _set_trigger_multi_point_sample_interval(self, value, skip_setup=False):
        value = int(value)
        if value != 0:
            raise ivi.ValueNotSupportedException()
        super(agilent3456A, self)._set_trigger_multi_point_sample_interval(value)

    def _set_trigger_multi_point_sample_trigger(self, value, skip_setup=False):
        value = str(value)
        if value.lower() != 'immediate':
            raise ivi.ValueNotSupportedException()
        super(agilent3456A, self)._set_trigger_multi_point_sample_trigger(value)

    def _set_trigger_multi_point_count(self, value, skip_setup=False):
        value = int(value)
        if value == 0:
            value = self._READINGS_MEMORY_SIZE
        if not 1 <= value <= self._READINGS_MEMORY_SIZE:
            raise ivi.ValueNotSupportedException()
        super(agilent3456A, self)._set_trigger_multi_point_count(value)
        if self._utility_is_using_reading_storage:
            self._write('RS1')
        else:
            self._write('RS0')

    def _utility_is_using_reading_storage(self):
        return self._trigger_multi_point_sample_count == \
                self._trigger_multi_point_count == 1

    def _trigger_multi_point_configure(self, trigger_count, sample_count, sample_trigger, sample_interval):
        self._set_trigger_multi_point_count(trigger_count)
        self._set_trigger_multi_point_sample_count(sample_count)
        self._set_trigger_multi_point_sample_trigger(sample_trigger)
        self._set_trigger_multi_point_sample_interval(sample_interval)

    def _measurement_fetch_multi_point(self, max_time, num_of_measurements = 0):
        if self._driver_operation_simulate:
            return
        if max_time != 0:
            raise ivi.ValueNotSupportedException()
        # num_of_measurements may be larger than _READING_MEMORY_SIZE, we will
        # return at most _READING_MEMORY_SIZE results anyway.
        if num_of_measurements == 0 \
                or num_of_measurements > self._READINGS_MEMORY_SIZE:
            num_of_measurements = self._READINGS_MEMORY_SIZE
        readings = []
        # The instrument has no seek instruction, so always read through the
        # entire memory, even if we do not want to save all of them.
        self._write('-{0:d}STR'.format(num_of_measurements))
        self._write('RER')
        raw_results = self._read().split(',')
        for raw_result in raw_results:
            readings.append(self._parse_measurement_result(raw_result))
        return readings

    def _measurement_read_multi_point(self, max_time, num_of_measurements = 0):
        if self._driver_operation_simulate:
            return
        self._measurement_initiate()
        self._measurement_fetch_multi_point(max_time, num_of_measurements)
