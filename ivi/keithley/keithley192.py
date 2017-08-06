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
import warnings
import re
from collections import OrderedDict
import time

from .. import ivi
from .. import dmm

TriggerSourceMapping = {
        'imm': '5',
        'bus': '3',
        }
MeasurementFunctionMapping = {
        'dc_volts': '0',
        'two_wire_resistance': '2',
        'four_wire_resistance': '2',
        }
RangeMapping = {
        'dc_volts': OrderedDict([
            (0.2,    '1'),
            (2.0,    '2'),
            (20.0,   '3'),
            (200.0,  '4'),
            (2000.0, '5'),
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
        }

class keithley192(ivi.Driver, dmm.Base, dmm.MultiPoint, dmm.SoftwareTrigger,
        dmm.DeviceInfo):
    """"Keithley 192 DMM.

    This meter supports DCV, two and four-wire resistance and optionally ACV.
    No DC or AC current. It is an early GPIB implementation that pre-dates IEEE
    488.2 (SCPI), so it is not a perfect fit to the IviDmm model.

    Not implemented:
    - ACV measurements. This is an optional feature (option 1910 or 1920) and
      there appears to be no way to detect its presence except by attempting to
      switch to ACV (F1/F3) and checking for errors.
    - Handling errors from the meter.
    - Variable integration interval (100 ms) or digital filtering (filter 1).
    - Changing the resolution (6.5 digit).
    - The idle state as defined for IviDmm: unless the trigger source is
      immediate, after measurement complete it will return to the
      wait-for-trigger state without waiting for read/initiate. If the trigger
      source is immediate, any settings change may trigger a reading (the result
      of this reading is discarded).
    - Sample interval != 0 for MultiPoint. The meter only supports a fixed
      sampling interval of 35 ms.
    - For MultiPoint, the is no difference between trigger = bus, sample trigger
      = imm and trigger = imm, sample trigger = bus (because there is no idle
      state). It only supports the following combinations of trigger
      count, sample count:
        - 1, 1
        - 100, 1 (trigger/sample trigger: bus/imm, imm/bus)
        - 1, 100 (trigger/sample trigger: imm/imm, bus/imm, imm/bus)
    - _measurement_(fetch|read)_multi_point will always return data starting
      from the first reading stored in memory. So subsequent calls to
      fetch_multi_point will return the data that was already returned, plus
      possibly more data that was stored since the last invocation.
    - The max_time parameter for _measurement_(fetch|read)_multi_point can only
      be 0. This instrument appears to have no functional STB (does not reset
      after serial poll), so polling for buffer full is time-consuming (need to
      complete 100 reads).
    """
    _READINGS_MEMORY_SIZE = 100

    def __init__(self, *args, **kwargs):
        self.__dict__.setdefault('_instrument_id', '192')

        super(keithley192, self).__init__(*args, **kwargs)

        self._identity_description = "Keithley model 192 programmable DMM"
        self._identity_identifier = ""
        self._identity_revision = ""
        self._identity_vendor = ""
        self._identity_instrument_manufacturer = "Keithley"
        self._identity_instrument_model = ""
        self._identity_instrument_firmware_revision = ""
        self._identity_specification_major_version = 3
        self._identity_specification_minor_version = 0
        self._identity_supported_instrument_models = ['192']

        self._trigger_source = 'imm'
        self._advanced_aperture_time = 0.1
        self._advanced_aperture_time_units = 'seconds'

    def _initialize(self, resource = None, id_query = False, reset = False, **keywargs):
        "Opens an I/O session to the instrument."

        super(keithley192, self)._initialize(resource, id_query, reset, **keywargs)

        # interface clear
        if not self._driver_operation_simulate:
            self._clear()

        # This instrument does not support ID queries
        if id_query:
            warnings.warn("{0}: ID Query is not supported by this instrument".format(
                self._instrument_id))

        # reset
        if reset:
            self._utility_reset()

    def _utility_error_query(self):
        error_code = 0
        error_message = "No error"
        return (error_code, error_message)

    def _utility_reset(self):
        if not self._driver_operation_simulate:
            # Defaults according to the programming manual, except set for one
            # shot trigering on X
            # use _ask to clear the result of the measurement we may have triggered
            self._write("F0R5Z0T5S6W1Q0K0M0Y\nX")
            self.driver_operation.invalidate_all_attributes()

    def _utility_self_test(self):
        raise ivi.OperationNotSupportedException()

    def _write(self, data, encoding='utf-8', clear_data=True):
        """
        Unless clear_data=False, this will perform a read to clear any pending
        data if triggering set to trigger from X and the data ends with X.

        This is necessary because the only possible software triggers are GET
        (bus triggering), on any talk and on X.
        """
        print(data, "\n")
        if clear_data and data[-1] == 'X' \
                and self._trigger_source.lower() == 'imm':
            # Do immediate read to clear the result triggered by X when set to
            # immediate triggering.
            return super(keithley192, self)._ask(data, encoding=encoding)
        else:
            return super(keithley192, self)._write(data, encoding=encoding)

    def _measurement_abort(self):
        self._clear()
        pass

    def _parse_measurement_result(self, raw_result):
        matches = re.fullmatch(r'([OZN])(DCV|ACV|OHM)([+-][0-9.]{8}E[+-]\d)',
                raw_result)
        if not matches:
            raise ivi.UnexpectedResponseException(
                'Unexpected response: {0}'.format(raw_result))
        (overflow, function, raw_value) = matches.groups()
        value = float(raw_value)
        if overflow == 'O':
            if value < 0:
                return float('-inf')
            else:
                return float('+inf')

        # Could verify zero status and function
        return value

    def _measurement_initiate(self):
        if self._driver_operation_simulate:
            return
        # This resets the readings memory if enabled
        self._internal_setup_multi_point()
        self._write('X', clear_data=False)

    def _measurement_fetch(self):
        if self._driver_operation_simulate:
            return
        raw_result = self._read()
        return self._parse_measurement_result(raw_result)

    def _measurement_read(self):
        if self._driver_operation_simulate:
            return
        raw_result = self._ask('X')
        return self._parse_measurement_result(raw_result)

    def _measurement_is_over_range(self, value):
        return value == float('inf')

    def _measurement_is_under_range(self, value):
        return value == float('-inf')

    def _set_trigger_source(self, value):
        if value.lower() not in TriggerSourceMapping:
            raise ivi.ValueNotSupportedException()
        super(keithley192, self)._set_trigger_source(value)
        if self._driver_operation_simulate:
            return
        self._write('T{0}X'.format(TriggerSourceMapping[value.lower()]))

    def _set_measurement_function(self, value):
        if value.lower() not in MeasurementFunctionMapping:
            raise ivi.ValueNotSupportedException()
        super(keithley192, self)._set_measurement_function(value)
        self._write('F{0}X'.format(MeasurementFunctionMapping[value.lower()]))

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
        super(keithley192, self)._set_range(value)
        if self._driver_operation_simulate:
            return
        self._write('R{0}X'.format(raw_range))

    def _set_auto_range(self, value):
        if value.lower() not in ('on', 'off'):
            raise ivi.ValueNotSupportedException()
        super(keithley192, self)._set_auto_range(value)
        if self._driver_operation_simulate:
            return
        if value == 'on':
            self._write('R0X')
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
        super(keithley192, self)._set_trigger_measurement_complete_destination(value)

    def _set_trigger_multi_point_sample_count(self, value, skip_setup=False):
        value = int(value)
        # The meter has a fixed memory of 100 points
        if value not in (1, self._READINGS_MEMORY_SIZE):
            raise ivi.ValueNotSupportedException()
        if value == self._READINGS_MEMORY_SIZE \
                and self._trigger_multi_point_count == self._READINGS_MEMORY_SIZE:
            raise ivi.ValueNotSupportedException()
        super(keithley192, self)._set_trigger_multi_point_sample_count(value)
        if not skip_setup: self._internal_setup_multi_point()

    def _set_trigger_multi_point_sample_interval(self, value, skip_setup=False):
        value = int(value)
        if value != 0:
            raise ivi.ValueNotSupportedException()
        super(keithley192, self)._set_trigger_multi_point_sample_interval(value)
        if not skip_setup: self._internal_setup_multi_point()

    def _set_trigger_multi_point_sample_trigger(self, value, skip_setup=False):
        value = str(value)
        if value.lower() not in TriggerSourceMapping:
            raise ivi.ValueNotSupportedException()
        super(keithley192, self)._set_trigger_multi_point_sample_trigger(value)
        if not skip_setup: self._internal_setup_multi_point()

    def _set_trigger_multi_point_count(self, value, skip_setup=False):
        value = int(value)
        if value not in (1, self._READINGS_MEMORY_SIZE):
            raise ivi.ValueNotSupportedException()
        if value == self._READINGS_MEMORY_SIZE \
                and self._trigger_multi_point_sample_count == self._READINGS_MEMORY_SIZE:
            raise ivi.ValueNotSupportedException()
        super(keithley192, self)._set_trigger_multi_point_count(value)
        if not skip_setup: self._internal_setup_multi_point()

    def _internal_setup_multi_point(self):
        """
        Set the trigger settings based on this table:
        Trigger \ Sample trigger:
                    imm                             bus
            imm     T4(tc=1,sc=100)                 T2(tc=1,sc=100)/T3(tc=100,sc=1)
            bus     T2(tc=1,sc=100)/3(tc=100,sc=1)  not supported
        """
        if self._trigger_multi_point_sample_count == \
                self._trigger_multi_point_count == 1:
            # Disable MultiPoint if sample count and trigger count are both 1
            if not self._driver_operation_simulate:
                self._write('Q0T{0}'.format(
                    TriggerSourceMapping[self._trigger_source.lower()]))
            return
        if self._trigger_source.lower() \
                == self._trigger_multi_point_sample_trigger.lower() \
                == 'bus':
            raise ivi.ValueNotSupportedException()
        if self._trigger_source.lower() \
                == self._trigger_multi_point_sample_trigger.lower() \
                == 'imm' \
                and self._trigger_multi_point_count > 1:
            raise ivi.ValueNotSupportedException()
        if self._trigger_multi_point_count == self._READINGS_MEMORY_SIZE:
            trigger_last_bit = 1 # Single-shot on trigger
        else:
            trigger_last_bit = 0 # Continuous sampling on trigger
        if 'bus' in (self._trigger_source.lower(),
                self._trigger_multi_point_sample_trigger.lower()):
            trigger = TriggerSourceMapping['bus']
        else:
            trigger = TriggerSourceMapping['imm']
        trigger = str((int(trigger) & 0xfe) | trigger_last_bit)
        if self._driver_operation_simulate:
            return
        self._write('Q1T{0}'.format(trigger))

    def _trigger_multi_point_configure(self, trigger_count, sample_count, sample_trigger, sample_interval):
        self._set_trigger_multi_point_count(trigger_count, skip_setup=True)
        self._set_trigger_multi_point_sample_count(sample_count, skip_setup=True)
        self._set_trigger_multi_point_sample_trigger(sample_trigger,
                skip_setup=True)
        self._set_trigger_multi_point_sample_interval(sample_interval,
                skip_setup=True)
        # Apply the above settings
        self._internal_setup_multi_point()

    def _measurement_fetch_multi_point(self, max_time, num_of_measurements = 0):
        if self._driver_operation_simulate:
            return
        if max_time != 0:
            raise ivi.ValueNotSupportedException()
        if num_of_measurements == 0:
            num_of_measurements = self._READINGS_MEMORY_SIZE
        # num_of_measurements may be larger than _READING_MEMORY_SIZE, we will
        # return at most _READING_MEMORY_SIZE results anyway.
        readings = []
        start = time.time()
        # The instrument has no seek instruction, so always read through the
        # entire memory, even if we do not want to save all of them.
        for num in range(self._READINGS_MEMORY_SIZE):
            raw_result = self._read()
            # '0'*16 signifies an empty memory location (no reading stored yet)
            if raw_result != '0'*16 and num < num_of_measurements:
                readings.append(self._parse_measurement_result(raw_result))
        return readings

    def _measurement_read_multi_point(self, max_time, num_of_measurements = 0):
        if self._driver_operation_simulate:
            return
        self._measurement_initiate()
        self._measurement_fetch_multi_point(max_time, num_of_measurements)
