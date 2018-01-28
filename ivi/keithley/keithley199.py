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
        'immediate': '5',
        'bus': '3',
        'external': '7',
        }
MeasurementFunctionMapping = {
        'dc_volts': '0',
        'ac_volts': '1',
        'two_wire_resistance': '2',
        'four_wire_resistance': '2',
        'dc_current': '3',
        'ac_current': '4',
        }
RangeMapping = {
        'dc_volts': OrderedDict([
            (0.3,    '1'),
            (3.0,    '2'),
            (30.0,   '3'),
            (300.0,  '4'),
            ]),
        'ac_volts': OrderedDict([
            (0.3,    '1'),
            (3.0,    '2'),
            (30.0,   '3'),
            (300.0,  '4'),
            ]),
        'two_wire_resistance': OrderedDict([
            (0.3e3,  '1'),
            (3e3,    '2'),
            (30e3,   '3'),
            (300e3,  '4'),
            (3000e3, '5'),
            (30e6,   '6'),
            (300e6,  '7'),
            ]),
        'four_wire_resistance': OrderedDict([
            (0.3e3,  '1'),
            (3e3,    '2'),
            (30e3,   '3'),
            (300e3,  '4'),
            (3000e3, '5'),
            (30e6,   '6'),
            (300e6,  '7'),
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

class keithley199(ivi.Driver, dmm.Base, dmm.MultiPoint, dmm.SoftwareTrigger):
    """"Keithley 199 DMM.

    This is an early GPIB implementation that pre-dates IEEE 488.2 (SCPI), so it
    is not a perfect fit to the IviDmm model.

    Not implemented:
    - Handling errors from the meter.
    - Variable integration interval (1 PLC) or digital filtering.
    - Changing the resolution (5.5 digit).
    - The idle state as defined for IviDmm: unless the trigger source is
      immediate, after measurement complete it will return to the
      wait-for-trigger state without waiting for read/initiate. If the trigger
      source is immediate, any settings change may trigger a reading (the result
      of this reading is discarded).
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
    - Setting the trigger delay to a high value with source immediate may cause
      commands execution time to be increased by the trigger delay. It is
      suggested to set the trigger source to bus or external before setting a
      large delay, or set the large delay just before
      measurement.read()/initiate().
    - The max_time parameter for _measurement_(fetch|read)_multi_point can only
      be 0. This instrument appears to have no functional STB (does not reset
      after serial poll), so polling for buffer full is time-consuming (need to
      complete 100 reads).
    """
    _READINGS_MEMORY_SIZE = 500

    def __init__(self, *args, **kwargs):
        self.__dict__.setdefault('_instrument_id', '199')

        super(keithley199, self).__init__(*args, **kwargs)
        self._identity_description = "Keithley model 199 programmable DMM"
        self._identity_identifier = "199"
        self._identity_revision = ""
        self._identity_vendor = ""
        self._identity_instrument_manufacturer = "Keithley"
        self._identity_instrument_model = ""
        self._identity_instrument_firmware_revision = ""
        self._identity_specification_major_version = 3
        self._identity_specification_minor_version = 0
        self._identity_supported_instrument_models = ['199']

        self._trigger_source = 'immediate'

    def _initialize(self, resource = None, id_query = False, reset = False, **keywargs):
        "Opens an I/O session to the instrument."

        super(keithley199, self)._initialize(resource, id_query, reset, **keywargs)

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
        else:
            status = self._ask("U0X")
            self._identity_instrument_model = status[:3]

    def _utility_error_query(self):
        error_code = 0
        error_message = "No error"
        return (error_code, error_message)

    def _utility_reset(self):
        if not self._driver_operation_simulate:
            # Defaults according to the manual, except disable the internal
            # digital filter and one-shot triggering on X
            self._write("A1B0F0G0J0K0M0P0Q0I0R4S1T5W0Y3Z0X", clear_data=True)
            self.driver_operation.invalidate_all_attributes()

    def _utility_self_test(self):
        raise ivi.OperationNotSupportedException()

    def _write(self, data, encoding='utf-8', clear_data=False):
        """
        Unless clear_data=False, this will perform a read to clear any pending
        data if triggering set to trigger from X and the data ends with X.

        This is necessary because the only possible software triggers are GET
        (bus triggering), on any talk and on X.
        """
        print(data, "\n")
        if clear_data and data[-1] == 'X' \
                and self._trigger_source.lower() == 'immediate':
            # Do immediate read to clear the result triggered by X when set to
            # immediate triggering.
            return super(keithley199, self)._ask(data, encoding=encoding)
        else:
            return super(keithley199, self)._write(data, encoding=encoding)

    def _measurement_abort(self):
        self._clear()
        pass

    def _parse_measurement_result(self, raw_result):
        matches = re.fullmatch(r'([OZN])(DCV|ACV|DCI|ACI|OHM)([+-][0-9.]{8}E[+-]\d),B\d{3},C\d',
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
        self._write('X')

    def _measurement_fetch(self, max_time):
        if self._driver_operation_simulate:
            return
        raw_result = self._read()
        return self._parse_measurement_result(raw_result)

    def _measurement_read(self, max_time):
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
        super(keithley199, self)._set_trigger_source(value)
        if self._driver_operation_simulate:
            return
        self._write('T{0}X'.format(TriggerSourceMapping[value.lower()]),
                    clear_data=True)

    def _set_trigger_delay(self, value):
        value = float(value)
        if value > 999.999:
            raise ivi.ValueNotSupportedException()
        self._set_trigger_delay_auto(False)
        super(keithley199, self)._set_trigger_delay(value)
        if self._driver_operation_simulate:
            return
        self._write('W{0:d}X'.format(round(value * 1000)), clear_data=True)

    def _set_trigger_delay_auto(self, value):
        value = bool(value)
        if value:
            self._set_trigger_delay(0)
        super(keithley199, self)._set_trigger_delay_auto(value)

    def _set_measurement_function(self, value):
        if value.lower() not in MeasurementFunctionMapping:
            raise ivi.ValueNotSupportedException()
        super(keithley199, self)._set_measurement_function(value)
        print('M', value)
        self._write('F{0}X'.format(MeasurementFunctionMapping[value.lower()]),
                    clear_data=True)

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
        super(keithley199, self)._set_range(value)
        if self._driver_operation_simulate:
            return
        self._write('R{0}X'.format(raw_range), clear_data=True)

    def _set_auto_range(self, value):
        if value.lower() not in ('on', 'off'):
            raise ivi.ValueNotSupportedException()
        super(keithley199, self)._set_auto_range(value)
        if self._driver_operation_simulate:
            return
        if value == 'on':
            self._write('R0X', clear_data=True)
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
        super(keithley199, self)._set_trigger_measurement_complete_destination(value)

    def _set_trigger_multi_point_sample_count(self, value, skip_setup=False):
        value = int(value)
        if value == 0:
            value = self._READINGS_MEMORY_SIZE
        if not 1 <= value <= self._READINGS_MEMORY_SIZE:
            raise ivi.ValueNotSupportedException()
        super(keithley199, self)._set_trigger_multi_point_sample_count(value)
        if not skip_setup: self._internal_setup_multi_point()

    def _set_trigger_multi_point_sample_interval(self, value, skip_setup=False):
        value = int(value)
        if value != 0:
            raise ivi.ValueNotSupportedException()
        super(keithley199, self)._set_trigger_multi_point_sample_interval(value)
        if not skip_setup: self._internal_setup_multi_point()

    def _set_trigger_multi_point_sample_trigger(self, value, skip_setup=False):
        value = str(value)
        if value.lower() not in TriggerSourceMapping:
            raise ivi.ValueNotSupportedException()
        super(keithley199, self)._set_trigger_multi_point_sample_trigger(value)
        if not skip_setup: self._internal_setup_multi_point()

    def _set_trigger_multi_point_count(self, value, skip_setup=False):
        value = int(value)
        if value == 0:
            value = self._READINGS_MEMORY_SIZE
        if not 1 <= value <= self._READINGS_MEMORY_SIZE:
            raise ivi.ValueNotSupportedException()
        super(keithley199, self)._set_trigger_multi_point_count(value)
        if not skip_setup: self._internal_setup_multi_point()

    def _internal_setup_multi_point(self):
        """
        Set the trigger settings based on this table:
        Trigger |   Sample trigger |    Trigger setting
        imm         imm                 T4(tc=1,sc>1)
        imm         bus                 not supported
        imm         ext                 T6(tc=1,sc>1)/T7(tc>1,sc=1)
        bus         imm                 T2(tc=1,sc>1)/T3(tc>1,sc=1)
        bus         bus                 not supported
        bus         ext                 not supported
        ext         imm                 T6(tc=1,sc>1)/T7(tc>1,sc=1)
        ext         bus                 not supported
        ext         ext                 not supported
        """
        MultiPointTriggerMapping = {
                'imm' : {
                    'imm': 4,
                    'bus': 2,
                    'ext': 6,
                    },
                'bus': {
                    'imm': 2,
                    },
                'ext': {
                    'imm': 6,
                    },
                }
        if self._trigger_multi_point_sample_count == \
                self._trigger_multi_point_count == 1:
            # Disable MultiPoint if sample count and trigger count are both 1
            if not self._driver_operation_simulate:
                self._write('B0Q0I0T{0}'.format(
                    TriggerSourceMapping[self._trigger_source.lower()]),
                            clear_data=True)
            return
        if min(self._trigger_multi_point_sample_count,
                self._trigger_multi_point_count) > 1:
            raise ivi.ValueNotSupportedException()
        try:
            trigger = MultiPointTriggerMapping[self._trigger_source.lower()] \
                    [self._trigger_multi_point_sample_trigger.lower()]
        except KeyError:
            raise ivi.ValueNotSupportedException()
        if self._trigger_multi_point_count > 1:
            trigger_last_bit = 1 # Single-shot on trigger
        else:
            trigger_last_bit = 0 # Continuous sampling on trigger
        trigger = str((int(trigger) & 0xfe) | trigger_last_bit)
        if self._driver_operation_simulate:
            return
        self._write('Q1T{0}'.format(trigger), clear_data=True)

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
