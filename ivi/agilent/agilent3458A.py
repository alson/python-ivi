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
        'immediate': 'SGL',
        'bus': 'HOLD',
        'external': 'EXT',
        }
MeasurementFunctionMapping = {
        'dc_volts': ('DCV', None),
        'ac_volts': ('ACV', 'ANA'),
        'ac_volts_rndm': ('ACV', 'RNDM'),
        'ac_volts_sync': ('ACV', 'SYNC'),
        'dc_current': ('DCI', None),
        'ac_current': ('ACI', None),
        'ac_plus_dc_volts': ('ACDCV', None),
        'ac_plus_dc_volts_rndm': ('ACDCV', 'RNDM'),
        'ac_plus_dc_volts_sync': ('ACDCV', 'SYNC'),
        'ac_plus_dc_current': ('ACDCI', None),
        'two_wire_resistance': ('OHM', None),
        'four_wire_resistance': ('OHMF', None),
        'frequency': ('FREQ', None),
        'period': ('PER', None),
        'ac_cpl_direct': ('DSAC'),
        'dc_cpl_direct': ('DSDC'),
        'ac_cpl_sub': ('SSAC'),
        'dc_cpl_sub': ('SSDC'),
        }

class agilent3458A(ivi.Driver, dmm.Base, dmm.SoftwareTrigger):
    """"HP 3458A DMM.

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
        self.__dict__.setdefault('_instrument_id', '3458A')

        super(agilent3458A, self).__init__(*args, **kwargs)
        self._identity_description = "HP 3458A DMM"
        self._identity_identifier = "3458A"
        self._identity_revision = ""
        self._identity_vendor = ""
        self._identity_instrument_manufacturer = "HP"
        self._identity_instrument_model = "3458A"
        self._identity_instrument_firmware_revision = ""
        self._identity_specification_major_version = 3
        self._identity_specification_minor_version = 0
        self._identity_supported_instrument_models = ['3458A']

        self._trigger_source = 'immediate'

    def _initialize(self, resource = None, id_query = False, reset = False, **keywargs):
        "Opens an I/O session to the instrument."

        super(agilent3458A, self)._initialize(resource, id_query, reset, **keywargs)

        # interface clear
        if not self._driver_operation_simulate:
            self._clear()
            self._write('END ALWAYS')

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
            res = self._ask('ID?')
            # Is manufacturer ever different from HP, i.e. does it ever return
            # 'AGILENT3458A' or 'KEYSIGHT3458A'?
            self._identity_instrument_manufacturer = res[:2]
            self._identity_instrument_model = res[2:]
            self._set_cache_valid(True, 'identity_instrument_manufacturer')
            self._set_cache_valid(True, 'identity_instrument_model')

    def _utility_error_query(self):
        error_code = 0
        error_message = "No error"
        return (error_code, error_message)

    def _utility_reset(self):
        if not self._driver_operation_simulate:
            # DCV, auto range, single triggering, 9 digits displayed, 100 NPLC
            # integration
            self._clear()
            self._write('PRESET NORM; OFORMAT ASCII; TARM AUTO; TRIG SGL;' +
                    'NPLC 100; NRDGS 1,AUTO; MEM OFF; NDIG 9;' +
                    'DISP MSG,"                 "; DISP OFF')
            self.driver_operation.invalidate_all_attributes()

    def _utility_self_test(self):
        raise ivi.OperationNotSupportedException()

    def _measurement_abort(self):
        self._clear()
        pass

    def _parse_measurement_result(self, raw_result):
        try:
            value = float(raw_result.strip())
        except ValueError:
            raise ivi.UnexpectedResponseException(
                'Unexpected response: {0}'.format(raw_result))
        return value

    def _measurement_initiate(self):
        if self._driver_operation_simulate:
            return
        if self._trigger_source == 'immediate':
            self._write('TRIG SGL')

    def _measurement_fetch(self, max_time):
        if self._driver_operation_simulate:
            return
        raw_result = self._read()
        return self._parse_measurement_result(raw_result)

    def _measurement_read(self):
        self._measurement_initiate()
        return self._measurement_fetch()

    def _measurement_is_over_range(self, value):
        return value >= +1e38

    def _measurement_is_under_range(self, value):
        return value <= -1e38

    def _set_trigger_source(self, value):
        if value.lower() not in TriggerSourceMapping:
            raise ivi.ValueNotSupportedException()
        super(agilent3458A, self)._set_trigger_source(value)
        if self._driver_operation_simulate:
            return
        self._write('TRIG {0}'.format(TriggerSourceMapping[value.lower()]))

    def _set_trigger_delay(self, value):
        value = float(value)
        self._set_trigger_delay_auto(False)
        super(agilent3458A, self)._set_trigger_delay(value)
        if self._driver_operation_simulate:
            return
        self._write('DELAY {0:E}'.format(value))

    def _set_trigger_delay_auto(self, value):
        value = bool(value)
        if value:
            self._set_trigger_delay(-1)
        super(agilent3458A, self)._set_trigger_delay_auto(value)

    def _set_measurement_function(self, value):
        if value.lower() not in MeasurementFunctionMapping:
            raise ivi.ValueNotSupportedException()
        super(agilent3458A, self)._set_measurement_function(value)
        func, setacv = MeasurementFunctionMapping[value.lower()]
        self._write('FUNC {0}'.format(func))
        if setacv:
            self._write('SETACV {0}'.format(setacv))

    def _set_range(self, value):
        value = float(value)
        super(agilent3458A, self)._set_range(value)
        if self._driver_operation_simulate:
            return
        self._write('RANGE {0}'.format(value))

    def _set_auto_range(self, value):
        if value.lower() not in ('on', 'off', 'once'):
            raise ivi.ValueNotSupportedException()
        super(agilent3458A, self)._set_auto_range(value)
        if self._driver_operation_simulate:
            return
        self._write('ARANGE {0}'.format(value.upper()))

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
        super(agilent3458A, self)._set_trigger_measurement_complete_destination(value)
